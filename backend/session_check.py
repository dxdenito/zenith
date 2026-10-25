import argparse
import asyncio
import json

import numpy as np
from scipy import stats

from app.register_rules import breakeven, fair_probability, find_trades, mode_interval, validate_spec
from backtest import load_symbols


def run_sessions(epochs, wins, base, multiplier, steps, ratio, target, window):
    n = len(wins)
    out = []
    i = 0
    while i < n:
        started = int(epochs[i])
        block_end = (started // window + 1) * window
        profit = 0.0
        staked = 0.0
        step = 0
        trades = 0
        kind = "time"
        while i < n:
            stake = base * multiplier**step
            staked += stake
            if wins[i]:
                profit += stake * (ratio - 1.0)
                step = 0
            else:
                profit -= stake
                step += 1
            trades += 1
            i += 1
            if step == steps:
                kind = "cap"
                break
            if step == 0:
                if profit >= target:
                    kind = "target"
                    break
                if int(epochs[i - 1]) >= block_end:
                    break
        out.append((kind, profit, trades, int(epochs[i - 1]) - started, staked))
        while i < n and int(epochs[i]) < block_end:
            i += 1
    return out


def longest_run(flags):
    best = 0
    run = 0
    for flag in flags:
        run = run + 1 if flag else 0
        best = max(best, run)
    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument("--base", type=float, default=1.0)
    parser.add_argument("--multiplier", type=float, default=2.0)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--target", type=float, default=5.0)
    parser.add_argument("--window", type=int, default=3600)
    parser.add_argument("--min-trades", type=int, default=30)
    args = parser.parse_args()

    with open(args.path, encoding="utf-8") as f:
        raw = json.load(f)
    for key in ("name", "source", "notes"):
        raw.pop(key, None)
    if args.symbols:
        raw["symbols"] = args.symbols
    spec = validate_spec(raw)
    ratio = 1.0 / breakeven(spec["contract"], spec["margin"])
    cost = 1.0 - fair_probability(spec["contract"]) * ratio
    data = asyncio.run(load_symbols(spec["symbols"]))

    for symbol in spec["symbols"]:
        e, q, d = data[symbol]
        epochs, wins = find_trades(spec, e, q, d, mode_interval(e), 0)
        sessions = run_sessions(
            epochs, wins, args.base, args.multiplier, args.steps, ratio, args.target, args.window
        )
        kept = [s for s in sessions if s[0] != "time" or s[2] >= args.min_trades]
        dropped = len(sessions) - len(kept)
        if len(kept) < 30:
            print(f"{symbol}: only {len(kept)} usable sessions")
            continue
        kinds = [s[0] for s in kept]
        profit = np.array([s[1] for s in kept])
        trades = np.array([s[2] for s in kept])
        seconds = np.array([s[3] for s in kept])
        staked = np.array([s[4] for s in kept])
        total = len(kept)
        expected = -cost * staked.mean()
        t = stats.ttest_1samp(profit, 0.0)
        curve = np.cumsum(profit)
        drawdown = float((np.maximum.accumulate(curve) - curve).max())

        print(f"\n== {symbol} ==")
        print(
            f"{total:,} one-hour sessions ({dropped} thin-data hours dropped) | base {args.base} "
            f"x{args.multiplier}, {args.steps} steps, target +{args.target}"
        )
        for kind in ("target", "cap", "time"):
            mask = np.array([k == kind for k in kinds])
            if not mask.any():
                continue
            print(
                f"  ended by {kind:6}: {mask.sum():5} ({mask.mean():6.1%}) | avg result {profit[mask].mean():+7.2f} "
                f"| avg {trades[mask].mean():5.1f} trades, {seconds[mask].mean() / 60:5.1f} min"
            )
        print(f"  sessions with a profit: {(profit > 0).mean():.1%}")
        print(
            f"  average per session {profit.mean():+.2f} (no-edge expectation {expected:+.2f}) | "
            f"t-test vs zero p={t.pvalue:.4f}"
        )
        print(
            "  result percentiles 5/25/50/75/95: "
            + " ".join(f"{np.percentile(profit, p):+.1f}" for p in (5, 25, 50, 75, 95))
        )
        print(f"  best {profit.max():+.1f} | worst {profit.min():+.1f}")
        print(
            f"  running through every session in order: total {curve[-1]:+,.0f}, "
            f"worst drawdown {drawdown:,.0f}, longest run of losing sessions {longest_run(profit < 0)}"
        )
        print(f"  one session an hour for a day would average {profit.mean() * 24:+.1f}")


if __name__ == "__main__":
    main()