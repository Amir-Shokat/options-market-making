"""Inventory-aware quoting around a model fair value.

Rules (from the coursework report, with the edge cases fixed):

* Normally we improve the best bid and best ask by one tick, but never quote through the
  fair value: bid <= fair - tick and ask >= fair + tick.
* If we are long more than ``threshold`` lots, we stop improving the bid and make the ask
  attractive (fair + tick) to sell inventory down. Short inventory is the mirror image.
* Volume grows with the edge available: ``min_vol`` per tick of distance between the fair
  value and the far side of the market (30 / 60 / 90 lots for 1 / 2 / 3 ticks), capped at
  ``max_vol``. If the fair value lies outside the market, only ``min_vol`` is quoted.
"""

from __future__ import annotations

import math


def _floor_tick(price: float, tick: float) -> float:
    return round(math.floor(round(price / tick, 9)) * tick, 10)


def _ceil_tick(price: float, tick: float) -> float:
    return round(math.ceil(round(price / tick, 9)) * tick, 10)


def compute_quotes(
    fair: float,
    best_bid: float,
    best_ask: float,
    position: int,
    threshold: int = 60,
    tick: float = 0.1,
) -> tuple[float, float] | None:
    """Return (bid, ask) prices, or None if no sensible two-sided quote exists."""
    max_bid = _floor_tick(fair - tick, tick)
    min_ask = _ceil_tick(fair + tick, tick)

    if position > threshold:          # too long: don't chase the bid, sell aggressively
        bid = min(best_bid, max_bid)
        ask = min_ask
    elif position < -threshold:       # too short: buy aggressively, don't chase the ask
        bid = max_bid
        ask = max(best_ask, min_ask)
    else:
        bid = min(best_bid + tick, max_bid)
        ask = max(best_ask - tick, min_ask)

    bid, ask = _floor_tick(bid, tick), _ceil_tick(ask, tick)
    if bid <= 0 or bid >= ask:
        return None
    return bid, ask


def quote_volume(
    fair: float,
    best_bid: float,
    best_ask: float,
    min_vol: int = 30,
    max_vol: int = 100,
    tick: float = 0.1,
) -> int:
    if not best_bid < fair < best_ask:
        return min_vol
    edge = max(fair - best_bid, best_ask - fair)
    ticks = max(1, int(round(edge / tick)))
    return int(min(max_vol, min_vol * ticks))
