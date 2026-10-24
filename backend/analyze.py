import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.analysis_engine import analyze, build_series, finalize, omnibus, quality
from app.database import SessionLocal, engine
from app.models import Tick


def day(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d")


async def load(symbol: str):
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(Tick.epoch, Tick.quote, Tick.digit)
                .where(Tick.symbol == symbol)
                .order_by(Tick.epoch)
            )
        ).all()
    if len(rows) < 5000:
        raise SystemExit(f"{symbol}: only {len(rows)} ticks stored, need at least 5000")
    epoch, quote, digit = zip(*rows)
    return build_series(symbol, epoch, quote, digit)


def line(r) -> str:
    flag = "SURVIVES" if r.survives else ("passed correction" if r.survives_fdr else "")
    return (
        f"{r.symbol:8} {r.name:38} "
        f"disc {r.rate_disc:7.2%} p={r.p_disc:.4f} | "
        f"hold {r.rate_hold:7.2%} p={r.p_hold:.3f} | "
        f"needs {r.breakeven:6.2%}  {flag}"
    )


async def main(symbols, margin, duration, mode):
    results = []
    for symbol in symbols:
        s = await load(symbol)
        q = quality(s)
        print(f"\n== {symbol} ==")
        print(
            f"ticks {q['ticks']:,} | {day(q['from'])} to {day(q['to'])} | "
            f"one tick per {q['interval_s']}s | contiguous {q['contiguous_pct']:.1f}% | "
            f"gaps {q['gaps']:,} | largest gap {q['largest_gap_s']:,}s"
        )
        for label, values in omnibus(s).items():
            print(
                f"  {label:9} digit uniformity p={values['uniformity_p']:.3f} | "
                f"digit dependence p={values['dependence_p']:.3f}"
            )
        results += analyze(s, margin, duration, mode)
    await engine.dispose()

    finalize(results)
    total = len(results)
    nominal = sum(r.p_disc < 0.05 for r in results)
    corrected = sum(r.survives_fdr for r in results)
    survivors = [r for r in results if r.survives]

    print("\n== Summary ==")
    print(f"tests run: {total}")
    print(f"looked significant in discovery (p<0.05): {nominal}  (about {total * 0.05:.0f} expected by luck alone)")
    print(f"passed multiple-testing correction: {corrected}")
    print(f"also held up on holdout and beat break-even: {len(survivors)}")
    print(f"assumed house margin {margin:.1%}, rise/fall duration {duration} ticks")

    print("\n== Closest to something (lowest p in discovery) ==")
    for r in sorted(results, key=lambda r: r.p_disc)[:12]:
        print(line(r))

    if survivors:
        print("\n== Survivors ==")
        for r in survivors:
            print(line(r))
        print("\nTreat these as leads to re-test on fresh data, not as proven edges.")
    else:
        print("\nNo test survived correction and the holdout. On this data these markets show no usable edge.")


parser = argparse.ArgumentParser()
parser.add_argument("symbols", nargs="+")
parser.add_argument("--margin", type=float, default=0.03)
parser.add_argument("--duration", type=int, default=5)
parser.add_argument("--mode", choices=["patterns", "time"], default="patterns")
args = parser.parse_args()
asyncio.run(main(args.symbols, args.margin, args.duration, args.mode))