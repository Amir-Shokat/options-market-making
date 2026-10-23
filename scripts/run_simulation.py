"""Run the market maker on a simulated options exchange and plot delta, PnL and positions.

    python scripts/run_simulation.py --steps 2000 --model-vol 0.3 --market-vol 0.3
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from options_mm import MarketMaker, MarketMakerConfig, OptionSpec, SimulatedOptionsExchange


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--steps", type=int, default=2000)
    p.add_argument("--model-vol", type=float, default=0.3, help="volatility the market maker prices with")
    p.add_argument("--market-vol", type=float, default=0.3, help="volatility used by the simulated market")
    p.add_argument("--threshold", type=int, default=60)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", default="output")
    a = p.parse_args()

    options = [OptionSpec(f"{k.upper()}_{s}", k, s, 0.25) for k in ("call", "put") for s in (90, 100, 110)]
    ex = SimulatedOptionsExchange(options, sigma=a.market_vol, seed=a.seed)
    mm = MarketMaker(ex, MarketMakerConfig(sigma=a.model_vol, threshold=a.threshold))
    log = mm.run(a.steps)
    print(f"steps={a.steps} fills={len(ex.fills)} final PnL={log['pnl'].iloc[-1]:.2f} "
          f"|delta| p95={log['delta'].abs().quantile(0.95):.2f}")

    out = Path(a.out)
    out.mkdir(exist_ok=True)
    fig, ax = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    ax[0].plot(log["step"], log["delta"]); ax[0].set_title("Portfolio delta after hedging")
    ax[1].plot(log["step"], log["pnl"]); ax[1].set_title("PnL")
    for name in [o.instrument_id for o in options] + [ex.stock, ex.dual]:
        ax[2].plot(log["step"], log[name], lw=0.8, label=name)
    ax[2].set_title("Positions"); ax[2].legend(ncol=4, fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "simulation.png", dpi=120)
    print(f"Saved {out / 'simulation.png'}")


if __name__ == "__main__":
    main()
