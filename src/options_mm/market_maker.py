"""The market-making loop: quote every option, then delta-hedge with the stock."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .black_scholes import call_delta, call_value, put_delta, put_value
from .hedging import plan_delta_hedge
from .quoting import compute_quotes, quote_volume


@dataclass
class MarketMakerConfig:
    sigma: float = 0.3             # our volatility estimate (the course exchange used a given value)
    r: float = 0.03
    threshold: int = 60            # inventory level at which quotes are skewed
    min_vol: int = 30
    max_vol: int = 100
    position_limit: int = 100
    tick: float = 0.1


class MarketMaker:
    def __init__(self, exchange, config: MarketMakerConfig | None = None):
        self.exchange = exchange
        self.config = config or MarketMakerConfig()
        self.log: list[dict] = []

    def _value_and_delta(self, option, spot: float, T: float) -> tuple[float, float]:
        c = self.config
        if option.kind == "call":
            return call_value(spot, option.strike, T, c.r, c.sigma), call_delta(spot, option.strike, T, c.r, c.sigma)
        return put_value(spot, option.strike, T, c.r, c.sigma), put_delta(spot, option.strike, T, c.r, c.sigma)

    def option_delta(self, spot: float) -> float:
        positions = self.exchange.get_positions()
        total = 0.0
        for name, option in self.exchange.get_instruments().items():
            _, delta = self._value_and_delta(option, spot, self.exchange.time_to_expiry(name))
            total += positions[name] * delta
        return total

    def update_quotes(self, spot: float) -> None:
        cfg = self.config
        for name, option in self.exchange.get_instruments().items():
            self.exchange.delete_orders(name)
            fair, _ = self._value_and_delta(option, spot, self.exchange.time_to_expiry(name))
            book = self.exchange.get_last_price_book(name)
            best_bid, best_ask = book.bids[0].price, book.asks[0].price
            position = self.exchange.get_positions()[name]
            quotes = compute_quotes(fair, best_bid, best_ask, position, cfg.threshold, cfg.tick)
            if quotes is None:
                continue
            bid, ask = quotes
            volume = quote_volume(fair, best_bid, best_ask, cfg.min_vol, cfg.max_vol, cfg.tick)
            # quote the largest size that cannot breach the limit, instead of skipping the side
            bid_vol = min(volume, cfg.position_limit - position)
            ask_vol = min(volume, cfg.position_limit + position)
            if bid_vol > 0:
                self.exchange.insert_order(name, bid, bid_vol, "bid", "limit")
            if ask_vol > 0:
                self.exchange.insert_order(name, ask, ask_vol, "ask", "limit")

    def hedge(self, spot: float) -> float:
        ex = self.exchange
        listings = (ex.stock, ex.dual)
        for name, side, volume in plan_delta_hedge(self.option_delta(spot), ex.get_positions(),
                                                   listings, self.config.position_limit):
            book = ex.get_last_price_book(name)
            price = book.asks[0].price if side == "bid" else book.bids[0].price
            ex.insert_order(name, price, volume, side, "ioc")
        positions = ex.get_positions()
        return self.option_delta(spot) + sum(positions[n] for n in listings)

    def on_tick(self) -> None:
        book = self.exchange.get_last_price_book(self.exchange.stock)
        spot = book.mid
        self.update_quotes(spot)
        delta = self.hedge(spot)
        self.log.append({
            "step": self.exchange.step_index, "spot": spot, "delta": delta,
            "pnl": self.exchange.get_pnl(), **self.exchange.get_positions(),
        })

    def run(self, n_steps: int) -> pd.DataFrame:
        for _ in range(n_steps):
            self.on_tick()
            self.exchange.step()
        return pd.DataFrame(self.log)
