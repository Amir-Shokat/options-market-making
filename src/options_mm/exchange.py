"""A simulated exchange for one stock (two listings) and its options.

It reproduces the part of Optiver's Optibook interface the market maker uses
(order books, positions, PnL, limit/IOC orders, deleting orders), so the strategy can be
run and tested without access to the course exchange.

Market model
------------
* The stock mid follows a geometric Brownian motion.
* Other market participants quote each option around its Black-Scholes value at the
  *market* volatility, with a random spread of a few ticks.
* Random market orders arrive each step. A taker buying an option lifts the best ask; if
  our ask is at least as good as the market's, we are filled (ties are split 50/50).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .black_scholes import call_value, put_value


@dataclass(frozen=True)
class PriceLevel:
    price: float
    volume: int


@dataclass(frozen=True)
class OrderBook:
    instrument_id: str
    bids: list[PriceLevel] = field(default_factory=list)
    asks: list[PriceLevel] = field(default_factory=list)

    @property
    def mid(self) -> float | None:
        if not self.bids or not self.asks:
            return None
        return (self.bids[0].price + self.asks[0].price) / 2


@dataclass(frozen=True)
class OptionSpec:
    instrument_id: str
    kind: str        # "call" or "put"
    strike: float
    expiry: float    # in years from the start of the simulation


@dataclass
class _Order:
    side: str
    price: float
    volume: int


class SimulatedOptionsExchange:
    def __init__(
        self,
        options: list[OptionSpec],
        stock: str = "STOCK",
        dual: str = "STOCK_DUAL",
        s0: float = 100.0,
        sigma: float = 0.3,
        r: float = 0.03,
        dt: float = 1 / (252 * 390),
        stock_half_spread: tuple[float, float] = (0.05, 0.15),
        option_spread_ticks: tuple[int, int] = (2, 6),
        taker_rate: float = 0.6,
        taker_size: tuple[int, int] = (5, 30),
        position_limit: int = 100,
        tick: float = 0.1,
        seed: int | None = 0,
    ) -> None:
        self.options = {o.instrument_id: o for o in options}
        self.stock, self.dual = stock, dual
        self.spot = s0
        self.sigma, self.r, self.dt = sigma, r, dt
        self.stock_half_spread = stock_half_spread
        self.option_spread_ticks = option_spread_ticks
        self.taker_rate = taker_rate
        self.taker_size = taker_size
        self.position_limit = position_limit
        self.tick = tick
        self.rng = np.random.default_rng(seed)
        self.time = 0.0
        self.step_index = 0
        self.cash = 0.0
        self.positions = {name: 0 for name in [stock, dual, *self.options]}
        self.resting: dict[str, list[_Order]] = {name: [] for name in self.options}
        self.fills: list[tuple[int, str, str, float, int]] = []
        self._books: dict[str, OrderBook] = {}
        self._build_books()

    # -- market model -------------------------------------------------------------------
    def time_to_expiry(self, instrument_id: str) -> float:
        return max(self.options[instrument_id].expiry - self.time, 0.0)

    def market_value(self, instrument_id: str) -> float:
        o = self.options[instrument_id]
        fn = call_value if o.kind == "call" else put_value
        return fn(self.spot, o.strike, self.time_to_expiry(instrument_id), self.r, self.sigma)

    def _round(self, price: float) -> float:
        return round(round(price / self.tick) * self.tick, 10)

    def _build_books(self) -> None:
        primary, dual = self.stock_half_spread
        for name, half in ((self.stock, primary), (self.dual, dual)):
            depth = 200 if name == self.stock else 40
            self._books[name] = OrderBook(
                name,
                [PriceLevel(self._round(self.spot - half), depth)],
                [PriceLevel(self._round(self.spot + half), depth)],
            )
        lo, hi = self.option_spread_ticks
        for name in self.options:
            fair = self.market_value(name)
            half = int(self.rng.integers(lo, hi + 1)) * self.tick / 2
            bid = max(self.tick, self._round(fair - half))
            ask = max(bid + self.tick, self._round(fair + half))
            self._books[name] = OrderBook(name, [PriceLevel(bid, 50)], [PriceLevel(ask, 50)])

    def _match_takers(self) -> None:
        for name, orders in self.resting.items():
            book = self._books[name]
            for taker_side in ("buy", "sell"):
                if self.rng.random() > self.taker_rate:
                    continue
                size = int(self.rng.integers(self.taker_size[0], self.taker_size[1] + 1))
                if taker_side == "buy":   # lifts asks: ours compete with the market's best ask
                    ours = sorted((o for o in orders if o.side == "ask"), key=lambda o: o.price)
                    best_market = book.asks[0].price
                else:
                    ours = sorted((o for o in orders if o.side == "bid"), key=lambda o: -o.price)
                    best_market = book.bids[0].price
                for order in ours:
                    if size == 0 or order.volume == 0:
                        continue
                    better = order.price < best_market if order.side == "ask" else order.price > best_market
                    tie = order.price == best_market
                    if not (better or (tie and self.rng.random() < 0.5)):
                        continue
                    qty = min(size, order.volume, self._room(name, order.side))
                    if qty <= 0:
                        continue
                    self._fill(name, order.side, order.price, qty)
                    order.volume -= qty
                    size -= qty
            self.resting[name] = [o for o in orders if o.volume > 0]

    def step(self) -> None:
        """Let takers trade against our resting quotes, then move the market one step."""
        self._match_takers()
        shock = self.rng.normal()
        self.spot *= math.exp((self.r - 0.5 * self.sigma**2) * self.dt + self.sigma * math.sqrt(self.dt) * shock)
        self.time += self.dt
        self.step_index += 1
        self._build_books()

    # -- accounting ---------------------------------------------------------------------
    def _room(self, name: str, side: str) -> int:
        pos = self.positions[name]
        return self.position_limit - pos if side == "bid" else self.position_limit + pos

    def _fill(self, name: str, side: str, price: float, qty: int) -> None:
        sign = 1 if side == "bid" else -1
        self.positions[name] += sign * qty
        self.cash -= sign * qty * price
        self.fills.append((self.step_index, name, side, price, qty))

    # -- Optibook-style API -------------------------------------------------------------
    def get_instruments(self) -> dict[str, OptionSpec]:
        return dict(self.options)

    def get_last_price_book(self, instrument_id: str) -> OrderBook:
        return self._books[instrument_id]

    def get_positions(self) -> dict[str, int]:
        return dict(self.positions)

    def get_pnl(self) -> float:
        value = sum(pos * self._books[name].mid for name, pos in self.positions.items())
        return self.cash + value

    def delete_orders(self, instrument_id: str) -> None:
        self.resting[instrument_id] = []

    def insert_order(self, instrument_id: str, price: float, volume: int, side: str,
                     order_type: str = "limit") -> int:
        """Limit orders rest until takers arrive; IOC orders trade against the book now.

        Returns the volume filled immediately. Orders that could breach the position
        limit are rejected, as on Optibook.
        """
        volume = int(volume)
        if side not in ("bid", "ask"):
            raise ValueError(f"invalid side {side!r}")
        if volume <= 0 or volume > self._room(instrument_id, side):
            return 0
        if order_type == "limit":
            self.resting[instrument_id].append(_Order(side, price, volume))
            return 0
        if order_type != "ioc":
            raise ValueError(f"invalid order type {order_type!r}")
        book = self._books[instrument_id]
        level = book.asks[0] if side == "bid" else book.bids[0]
        crosses = price >= level.price if side == "bid" else price <= level.price
        if not crosses:
            return 0
        qty = min(volume, level.volume)
        self._fill(instrument_id, side, level.price, qty)
        return qty
