import argparse
import asyncio
import json

import numpy as np
from sqlalchemy import select

from app.database import SessionLocal, engine
from app.ml_engine import load_cutoff
from app.models import Tick
from app.register_rules import binom_p, breakeven, find_trades, mode_interval, validate_spec

MIN_TRADES = 100


async def load_symbols(symbols):
    out = {}
    async with SessionLocal() as db:
        for symbol in symbols:
            rows = (
                await db.execute(
                    select(Tick.epoch, Tick.quote, Tick.digit)
                    .where(Tick.symbol == symbol)
                    .order_by(Tick.epoch)
                )
            ).all()
            if len(rows) < 5000:
                raise SystemExit(f"{symbol}: only {len(rows)} ticks stored")
            e, q, d = zip(*rows)
            out[symbol] = (
                np.asarray(e, dtype=np.int64),
                np.asarray(q, dtype=float),
                np.asarray(d, dtype=np.int64),
            )
    await engine.dispose()
    return out


def passes_fdr(p_values):
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    m = len(p)
    limit = 0.05 * np.arange(1, m + 1) / m
    below = np.flatnonzero(p[order] <= limit)
    passed = np.zeros(m, dtype=bool)
    if below.size:
        passed[order[: below.max() + 1]] = True
    return passed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--windows", nargs="+", type=int, default=[100])
    args = parser.parse_args()

    runs = []
    for path in args.paths:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        label = raw.pop("name", path)
        raw.pop("source", None)
        raw.pop("notes", None)
        raw.pop("window", None)
        for window in args.windows:
            runs.append((f"{label} N={window}", validate_spec({**raw, "window": window})))

    symbols = sorted({s for _, spec in runs for s in spec["symbols"]})
    data = asyncio.run(load_symbols(symbols))
    cutoffs = {s: load_cutoff(s, data[s][0]) for s in symbols}

    table = []
    for label, spec in runs:
        be = breakeven(spec["contract"], spec["margin"])
        wd = nd = wh = nh = 0
        for symbol in spec["symbols"]:
            e, q, d = data[symbol]
            t_epoch, t_win = find_trades(spec, e, q, d, mode_interval(e), 0)
            disc = t_epoch < cutoffs[symbol]
            nd += int(disc.sum())
            wd += int(t_win[disc].sum())
            nh += int((~disc).sum())
            wh += int(t_win[~disc].sum())
        p = binom_p(wd, nd, be) if nd >= MIN_TRADES else 1.0
        table.append({"label": label, "be": be, "wd": wd, "nd": nd, "wh": wh, "nh": nh, "p": p})

    passed = passes_fdr([r["p"] for r in table])
    survivors = 0
    for r, flag in zip(table, passed):
        rate_d = r["wd"] / r["nd"] if r["nd"] else 0.0
        line = (
            f"{r['label']:48} disc n={r['nd']:6} {rate_d:7.2%} vs needs {r['be']:6.2%} p={r['p']:.4f} | "
        )
        if r["nd"] < MIN_TRADES:
            line += "too few trades"
        elif flag:
            rate_h = r["wh"] / r["nh"] if r["nh"] else 0.0
            p_h = binom_p(r["wh"], r["nh"], r["be"]) if r["nh"] else 1.0
            ok = p_h < 0.05 and rate_h > r["be"]
            survivors += int(ok)
            line += f"passed correction | hold n={r['nh']} {rate_h:7.2%} p={p_h:.3f}  {'SURVIVES' if ok else ''}"
        else:
            line += "hold not run"
        print(line)

    print(f"\nwindows tested: {len(table)} | passed correction: {int(passed.sum())} | survived holdout: {survivors}")
    print("Anything that survives is a lead to register and forward-test, not proof.")


if __name__ == "__main__":
    main()