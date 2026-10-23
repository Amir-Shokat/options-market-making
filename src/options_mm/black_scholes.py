"""Black-Scholes-Merton prices and Greeks for European options on a non-dividend stock.

S: spot, K: strike, T: time to expiry in years, r: continuously compounded rate,
sigma: annualised volatility. At or after expiry (T <= 0) the intrinsic value is returned.
"""

from __future__ import annotations

import math

from scipy.stats import norm


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> tuple[float, float]:
    if S <= 0 or K <= 0 or sigma <= 0:
        raise ValueError("S, K and sigma must be positive")
    vol_sqrt_t = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / vol_sqrt_t
    return d1, d1 - vol_sqrt_t


def call_value(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0:
        return max(S - K, 0.0)
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)


def put_value(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0:
        return max(K - S, 0.0)
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def call_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0:
        return 1.0 if S > K else 0.0
    return float(norm.cdf(_d1_d2(S, K, T, r, sigma)[0]))


def put_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Put delta = call delta - 1 (always between -1 and 0)."""
    return call_delta(S, K, T, r, sigma) - 1.0


def gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0:
        return 0.0
    d1, _ = _d1_d2(S, K, T, r, sigma)
    return float(norm.pdf(d1) / (S * sigma * math.sqrt(T)))


def vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Sensitivity to a 1.00 (100 vol-point) change in sigma."""
    if T <= 0:
        return 0.0
    d1, _ = _d1_d2(S, K, T, r, sigma)
    return float(S * norm.pdf(d1) * math.sqrt(T))
