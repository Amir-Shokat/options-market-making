"""Delta hedging with a primary and a secondary (dual) listing of the same stock."""

from __future__ import annotations


def plan_delta_hedge(
    option_delta: float,
    positions: dict[str, int],
    listings: tuple[str, ...],
    position_limit: int = 100,
) -> list[tuple[str, str, int]]:
    """Return the stock orders that bring the total delta as close to zero as possible.

    The stock has delta 1, so the total delta is the option delta plus the stock held in
    all listings. The primary (first) listing is used first because it is more liquid;
    the remainder goes to the next listing when the primary is at its limit.
    Returns a list of (instrument, side, volume).
    """
    stock = sum(positions.get(name, 0) for name in listings)
    needed = -int(round(option_delta + stock))   # signed shares to trade
    orders = []
    for name in listings:
        if needed == 0:
            break
        pos = positions.get(name, 0)
        if needed > 0:
            volume = min(needed, position_limit - pos)
            side = "bid"
        else:
            volume = min(-needed, position_limit + pos)
            side = "ask"
        if volume > 0:
            orders.append((name, side, volume))
            needed -= volume if side == "bid" else -volume
    return orders
