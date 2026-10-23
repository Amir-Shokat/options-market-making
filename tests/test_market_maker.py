import pytest

from options_mm import MarketMaker, MarketMakerConfig, OptionSpec, SimulatedOptionsExchange


def make_exchange(seed=0, **kw):
    options = [OptionSpec(f"{k}_{s}", k, s, 0.25) for k in ("call", "put") for s in (90, 100, 110)]
    return SimulatedOptionsExchange(options, seed=seed, **kw)


@pytest.fixture(scope="module")
def run():
    ex = make_exchange(seed=3)
    log = MarketMaker(ex, MarketMakerConfig(sigma=0.3)).run(1500)
    return ex, log


def test_positions_respect_limits(run):
    ex, log = run
    for name in ex.positions:
        assert log[name].abs().max() <= 100


def test_book_stays_delta_hedged(run):
    _, log = run
    assert log["delta"].abs().quantile(0.95) <= 5


def test_earns_the_spread_when_model_matches_market(run):
    ex, log = run
    assert len(ex.fills) > 100
    assert log["pnl"].iloc[-1] > 0


def test_limit_order_rejected_if_it_could_breach_limit():
    ex = make_exchange()
    ex.positions["call_100"] = 90
    assert ex.insert_order("call_100", 1.0, 20, "bid", "limit") == 0
    assert ex.resting["call_100"] == []
