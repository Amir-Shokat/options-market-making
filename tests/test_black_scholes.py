import math

import pytest

from options_mm import call_delta, call_value, gamma, put_delta, put_value, vega

S, K, T, r, sigma = 100.0, 95.0, 0.5, 0.03, 0.25


def test_known_value():
    # Hull-style textbook example: S=42, K=40, T=0.5, r=10%, sigma=20% -> c=4.76, p=0.81
    assert call_value(42, 40, 0.5, 0.10, 0.20) == pytest.approx(4.76, abs=0.01)
    assert put_value(42, 40, 0.5, 0.10, 0.20) == pytest.approx(0.81, abs=0.01)


def test_put_call_parity():
    lhs = call_value(S, K, T, r, sigma) - put_value(S, K, T, r, sigma)
    assert lhs == pytest.approx(S - K * math.exp(-r * T), rel=1e-10)


def test_delta_bounds_and_relation():
    assert 0 < call_delta(S, K, T, r, sigma) < 1
    assert -1 < put_delta(S, K, T, r, sigma) < 0
    assert call_delta(S, K, T, r, sigma) - put_delta(S, K, T, r, sigma) == pytest.approx(1.0)


def test_delta_matches_finite_difference():
    h = 1e-4
    fd = (call_value(S + h, K, T, r, sigma) - call_value(S - h, K, T, r, sigma)) / (2 * h)
    assert call_delta(S, K, T, r, sigma) == pytest.approx(fd, rel=1e-5)


def test_gamma_and_vega_match_finite_difference():
    h = 1e-3
    fd_gamma = (call_delta(S + h, K, T, r, sigma) - call_delta(S - h, K, T, r, sigma)) / (2 * h)
    assert gamma(S, K, T, r, sigma) == pytest.approx(fd_gamma, rel=1e-4)
    fd_vega = (call_value(S, K, T, r, sigma + h) - call_value(S, K, T, r, sigma - h)) / (2 * h)
    assert vega(S, K, T, r, sigma) == pytest.approx(fd_vega, rel=1e-4)


def test_expiry_gives_intrinsic_value():
    assert call_value(110, 100, 0, r, sigma) == 10
    assert put_value(110, 100, 0, r, sigma) == 0
    assert call_delta(110, 100, 0, r, sigma) == 1.0


def test_invalid_inputs():
    with pytest.raises(ValueError):
        call_value(-1, K, T, r, sigma)
