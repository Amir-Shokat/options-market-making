import pytest

from options_mm import compute_quotes, plan_delta_hedge, quote_volume


@pytest.mark.parametrize("position", [-100, -61, 0, 30, 61, 100])
@pytest.mark.parametrize("fair", [36.75, 36.4, 37.3, 35.0, 39.0])
def test_quotes_never_cross_fair_value(fair, position):
    quotes = compute_quotes(fair, 36.4, 37.2, position, threshold=60, tick=0.1)
    if quotes is None:
        return
    bid, ask = quotes
    assert bid < fair < ask
    assert bid < ask


def test_neutral_inventory_pennies_both_sides():
    assert compute_quotes(36.8, 36.4, 37.2, 0) == (36.5, 37.1)


def test_long_inventory_skews_to_selling():
    bid, ask = compute_quotes(36.8, 36.4, 37.2, position=80)
    assert bid == 36.4            # no longer improving the bid
    assert ask == pytest.approx(36.9)   # one tick above fair


def test_short_inventory_skews_to_buying():
    bid, ask = compute_quotes(36.8, 36.4, 37.2, position=-80)
    assert bid == pytest.approx(36.7)
    assert ask == 37.2


def test_fair_at_best_bid_does_not_produce_a_losing_bid():
    # original code would bid best_bid + 0.1, i.e. above fair
    bid, ask = compute_quotes(36.4, 36.4, 37.2, 0)
    assert bid <= 36.3


@pytest.mark.parametrize("gap,expected", [(0.1, 30), (0.2, 60), (0.3, 90), (0.6, 100)])
def test_volume_scales_with_edge(gap, expected):
    fair = 36.0
    assert quote_volume(fair, fair - gap, fair + 0.05, min_vol=30) == expected


def test_volume_minimum_when_fair_outside_market():
    assert quote_volume(40.0, 36.4, 37.2, min_vol=30) == 30


def test_hedge_uses_primary_then_dual():
    orders = plan_delta_hedge(-150.0, {"S": 0, "SD": 0}, ("S", "SD"), position_limit=100)
    assert orders == [("S", "bid", 100), ("SD", "bid", 50)]


def test_hedge_sells_when_long_delta():
    orders = plan_delta_hedge(40.4, {"S": 10, "SD": 0}, ("S", "SD"))
    assert orders == [("S", "ask", 50)]


def test_hedge_noop_when_flat():
    assert plan_delta_hedge(-10.2, {"S": 10, "SD": 0}, ("S", "SD")) == []
