import argparse
import asyncio
import json

import numpy as np
from scipy import stats
from sqlalchemy import select

from app.database import SessionLocal, engine
from app.register_rules import breakeven, fair_probability, find_trades, mode_interval, validate_spec
from app.trade_models import Trade
from backtest import load_symbols


def simulate(wins, base, multiplier, steps, ratio):
    step_n = np.zeros(steps, dtype=np.int64)
    step_w = np.zeros(steps, dtype=np.int64)
    step = 0
    staked = 0.0
    profit = 0.0
    peak = 0.0
    drawdown = 0.0
    cycles = 0
    caps = 0
    for won in wins.tolist():
        stake = base * multiplier**step
        staked += stake
        step_n[step] += 1
        if won:
            step_w[step] += 1
            profit += stake * (ratio - 1.0)
            step = 0
            cycles += 1
        else:
            profit -= stake
            step += 1
            if step == steps:
                caps += 1
                cycles += 1
                step = 0
        peak = max(peak, profit)
        drawdown = max(drawdown, peak - profit)
    return {
        "step_n": step_n,
        "step_w": step_w,
        "staked": staked,
        "profit": profit,
        "drawdown": drawdown,
        "cycles": cycles,
        "caps": caps,
    }


def print_steps(step_n, step_w, fair):
    for k in range(len(step_n)):
        n = int(step_n[k])
        if n == 0:
            print(f"  step {k + 1}: no trades")
            continue
        rate = step_w[k] / n
        p = stats.binomtest(int(step_w[k]), n, fair).pvalue
        print(f"  step {k + 1}: n={n:7} win rate {rate:7.2%} vs true odds {fair:.2%}  p={p:.3f}")


def run_history(args):
    with open(args.path, encoding="utf-8") as f:
        raw = json.load(f)
    for key in ("name", "source", "notes"):
        raw.pop(key, None)
    if args.symbols:
        raw["symbols"] = args.symbols
    spec = validate_spec(raw)
    ratio = 1.0 / breakeven(spec["contract"], spec["margin"])
    fair = fair_probability(spec["contract"])
    data = asyncio.run(load_symbols(spec["symbols"]))
    for symbol in spec["symbols"]:
        e, q, d = data[symbol]
        _, wins = find_trades(spec, e, q, d, mode_interval(e), 0)
        n = len(wins)
        if n < 1000:
            print(f"{symbol}: only {n} trades, too few")
            continue
        rate = float(wins.mean())
        flat = (wins.sum() * (ratio - 1.0) - (n - wins.sum())) / n
        sim = simulate(wins, args.base, args.multiplier, args.steps, ratio)
        theory = (1.0 - rate) ** args.steps
        print(f"\n== {symbol} ==")
        print(f"trades {n:,} | win rate {rate:.2%} | flat staking result per amount staked {flat:+.2%}")
        print(
            f"martingale base {args.base} x{args.multiplier} over {args.steps} steps: "
            f"{sim['cycles']:,} cycles, cap hit {sim['caps']:,} times ({sim['caps'] / sim['cycles']:.2%} of cycles, theory {theory:.2%})"
        )
        print_steps(sim["step_n"], sim["step_w"], fair)
        print(
            f"  staked {sim['staked']:,.0f} (flat would stake {n * args.base:,.0f}) | "
            f"profit {sim['profit']:+,.0f} | result per amount staked {sim['profit'] / sim['staked']:+.2%} | "
            f"worst drawdown {sim['drawdown']:,.0f}"
        )
    print(
        "\nIf martingale changed the odds, later steps would win more or less often than step 1. "
        "With four p-values, about one in five runs shows one below 0.05 by chance alone."
    )


async def fetch_trades(strategy):
    query = select(Trade.step, Trade.status, Trade.fair_prob, Trade.stake, Trade.payout, Trade.profit).where(
        Trade.mode == "demo", Trade.status.in_(("won", "lost"))
    )
    if strategy:
        query = query.where(Trade.strategy == strategy)
    async with SessionLocal() as db:
        rows = (await db.execute(query)).all()
    await engine.dispose()
    return rows


def run_trades(args):
    rows = asyncio.run(fetch_trades(args.strategy))
    if not rows:
        raise SystemExit("no settled demo trades found")
    top = max(r[0] for r in rows)
    print(f"{len(rows)} settled demo trades, deepest step {top}")
    for k in range(1, top + 1):
        group = [r for r in rows if r[0] == k]
        if not group:
            continue
        wins = sum(1 for r in group if r[1] == "won")
        fair = float(np.mean([r[2] for r in group if r[2] is not None]))
        p = stats.binomtest(wins, len(group), fair).pvalue
        print(f"  step {k}: n={len(group):6} win rate {wins / len(group):7.2%} vs true odds {fair:.2%}  p={p:.3f}")
    staked = sum(r[3] for r in rows)
    profit = sum(r[5] for r in rows if r[5] is not None)
    expected = sum(r[2] * r[4] - r[3] for r in rows if r[2] is not None and r[4] is not None)
    print(
        f"staked {staked:,.2f} | actual {profit:+,.2f} ({profit / staked:+.2%} per amount staked) | "
        f"expected with no edge {expected:+,.2f} ({expected / staked:+.2%})"
    )


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="source", required=True)
    history = sub.add_parser("history")
    history.add_argument("path")
    history.add_argument("--symbols", nargs="+")
    history.add_argument("--base", type=float, default=1.0)
    history.add_argument("--multiplier", type=float, default=2.0)
    history.add_argument("--steps", type=int, default=4)
    trades = sub.add_parser("trades")
    trades.add_argument("--strategy", default=None)
    args = parser.parse_args()
    if args.source == "history":
        if args.steps < 2:
            raise SystemExit("steps must be at least 2")
        run_history(args)
    else:
        run_trades(args)


if __name__ == "__main__":
    main()