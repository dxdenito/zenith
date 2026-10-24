import argparse
import asyncio
import time
from datetime import datetime, timezone

import numpy as np

from app.analysis_engine import SPLIT, build_series
from app.ml_engine import evaluate_series, finalize_ml, load_cutoff, synthetic


def stamp(epoch) -> str:
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


async def load_all(symbols):
    from sqlalchemy import select

    from app.database import SessionLocal, engine
    from app.models import Tick

    out = []
    for symbol in symbols:
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(Tick.epoch, Tick.quote, Tick.digit)
                    .where(Tick.symbol == symbol)
                    .order_by(Tick.epoch)
                )
            ).all()
        if len(rows) < 5000:
            await engine.dispose()
            raise SystemExit(f"{symbol}: only {len(rows)} ticks stored, need at least 5000")
        epoch, quote, digit = zip(*rows)
        out.append(build_series(symbol, epoch, quote, digit))
    await engine.dispose()
    return out


def freshness(s):
    diffs = np.diff(s.epoch)
    broken = diffs != s.interval
    missing_days = float((diffs[broken] - s.interval).sum()) / 86400
    span_days = float(s.epoch[-1] - s.epoch[0]) / 86400
    age = (time.time() - s.epoch[-1]) / 60
    print(f"\n== {s.symbol} ==")
    print(
        f"ticks {len(s.epoch):,} | {stamp(s.epoch[0])} to {stamp(s.epoch[-1])} UTC | "
        f"newest tick {age:.1f} min old | gaps {int(broken.sum()):,} | "
        f"missing {missing_days:.1f} of {span_days:.1f} days"
    )
    if age > 5:
        print("  WARNING: the newest stored tick is stale; nothing is currently writing ticks for this symbol")

def show(r) -> str:
    flag = "SURVIVES" if r.survives else ("passed correction" if r.survives_fdr else "")
    hold = (
        f"hold {r.rate_hold:6.2%} vs {r.be_hold:6.2%} n={r.n_hold} p={r.p_hold:.3f}"
        if r.survives_fdr
        else "hold not run"
    )
    return (
        f"{r.symbol:8} {r.target:18} {r.model:9} disc {r.rate_disc:6.2%} vs needs {r.be_disc:6.2%} "
        f"n={r.n_disc:6} p={r.p_disc:.4f} gain={r.gain * 1e4:+.2f}e-4 | {hold}  {flag}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("symbols", nargs="*")
    parser.add_argument("--models", nargs="+", choices=["logistic", "hgb"], default=["logistic", "hgb"])
    parser.add_argument("--barriers", nargs="*", type=int, default=list(range(9)))
    parser.add_argument("--margin", type=float, default=0.03)
    parser.add_argument("--duration", type=int, default=5)
    parser.add_argument("--control", type=float, default=None)
    parser.add_argument("--ticks", type=int, default=330000)
    args = parser.parse_args()

    if args.control is not None:
        epoch, quote, digit = synthetic(args.ticks, args.control)
        series = [build_series("CTRL", epoch, quote, digit)]
        cutoffs = {"CTRL": int(epoch[int(SPLIT * args.ticks)])}
        print(
            f"CONTROL: synthetic ticks, even after three odds in a row with probability {args.control:.2f}; "
            "every other test is pure noise"
        )
    else:
        if not args.symbols:
            parser.error("give at least one symbol, or use --control")
        series = asyncio.run(load_all(args.symbols))
        cutoffs = {s.symbol: load_cutoff(s.symbol, s.epoch) for s in series}

    items = []
    for s in series:
        if args.control is None:
            freshness(s)
        print(f"discovery before {stamp(cutoffs[s.symbol])} UTC, holdout from there on")
        items += evaluate_series(s, cutoffs[s.symbol], args.models, args.barriers, args.margin, args.duration)

    results = finalize_ml(items)
    total = len(results)
    nominal = sum(r.p_disc < 0.05 for r in results)
    corrected = sum(r.survives_fdr for r in results)
    survivors = [r for r in results if r.survives]

    print("\n== Summary ==")
    print(f"tests run: {total}")
    print(f"looked significant in discovery (p<0.05): {nominal}  (about {total * 0.05:.0f} expected by luck alone)")
    print(f"passed multiple-testing correction: {corrected}")
    print(f"also held up on holdout and beat break-even: {len(survivors)}")
    print(f"assumed house margin {args.margin:.1%}, rise/fall duration {args.duration} ticks")

    print("\n== Closest to something (lowest p in discovery) ==")
    for r in sorted(results, key=lambda r: r.p_disc)[:12]:
        print(show(r))

    if survivors:
        print("\n== Survivors ==")
        for r in survivors:
            print(show(r))
        print("\nTreat these as leads to re-test on fresh data, not as proven edges.")
    else:
        print("\nNo model survived correction and the holdout.")


main()