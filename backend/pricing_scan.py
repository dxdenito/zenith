import argparse
import asyncio
import csv
import time
import socket

import numpy as np
import websockets
from sqlalchemy import select

from app.database import SessionLocal, engine
from app.market_sync import PUBLIC_URL, call
from app.ml_features import contiguous_span
from app.models import Tick


def digit_fair(kind, barrier):
    if kind in ("DIGITEVEN", "DIGITODD"):
        return 0.5
    if kind == "DIGITOVER":
        return (9 - barrier) / 10
    if kind == "DIGITUNDER":
        return barrier / 10
    if kind == "DIGITMATCH":
        return 0.1
    return 0.9


def contract_grid(digit_durations, rf_durations):
    grid = []
    for d in digit_durations:
        grid.append(("DIGITEVEN", None, d))
        grid.append(("DIGITODD", None, d))
        for b in range(0, 9):
            grid.append(("DIGITOVER", b, d))
        for b in range(1, 10):
            grid.append(("DIGITUNDER", b, d))
    for b in range(10):
        grid.append(("DIGITMATCH", b, 1))
        grid.append(("DIGITDIFF", b, 1))
    for d in rf_durations:
        grid.append(("CALL", None, d))
        grid.append(("PUT", None, d))
    return grid


async def rise_fall_fair(symbol, durations):
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(Tick.epoch, Tick.quote).where(Tick.symbol == symbol).order_by(Tick.epoch)
            )
        ).all()
    if len(rows) < 5000:
        return {}
    epoch = np.asarray([r[0] for r in rows], dtype=np.int64)
    quote = np.asarray([r[1] for r in rows], dtype=float)
    values, counts = np.unique(np.diff(epoch), return_counts=True)
    interval = int(values[np.argmax(counts)])
    n = len(epoch)
    out = {}
    for h in durations:
        ok = contiguous_span(epoch, interval, 0, h)
        up = np.zeros(n, dtype=bool)
        down = np.zeros(n, dtype=bool)
        up[: n - h] = quote[h:] > quote[: n - h]
        down[: n - h] = quote[h:] < quote[: n - h]
        out[("CALL", h)] = float(up[ok].mean())
        out[("PUT", h)] = float(down[ok].mean())
    return out


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def quote(ws, payload, counter, pause):
    reply = {}
    for attempt in range(4):
        counter[0] += 1
        reply = await call(ws, payload, counter[0])
        await asyncio.sleep(pause)
        message = (reply.get("error") or {}).get("message", "")
        if "rate limit" not in message.lower():
            return reply
        wait = 20 * (attempt + 1)
        print(f"rate limited, waiting {wait}s", flush=True)
        await asyncio.sleep(wait)
    return reply

async def scan(symbols, stake, digit_durations, rf_durations, pause):
    grid = contract_grid(digit_durations, rf_durations)
    rows = []
    counter = [1]
    stamp = int(time.time())
    async with websockets.connect(
        PUBLIC_URL, ping_interval=20, open_timeout=30, family=socket.AF_INET
    ) as ws:
        for symbol in symbols:
            fair_rf = await rise_fall_fair(symbol, rf_durations)
            errors = {}
            shown = False
            for kind, barrier, duration in grid:
                payload = {
                    "proposal": 1,
                    "amount": stake,
                    "basis": "stake",
                    "contract_type": kind,
                    "currency": "USD",
                    "duration": duration,
                    "duration_unit": "t",
                    "underlying_symbol": symbol,
                }
                if barrier is not None:
                    payload["barrier"] = str(barrier)
                reply = await quote(ws, payload, counter, pause)
                if reply.get("error"):
                    message = reply["error"].get("message", "error")
                    errors[message] = errors.get(message, 0) + 1
                    continue
                proposal = reply.get("proposal") or {}
                payout = number(proposal.get("payout"))
                ask = number(proposal.get("ask_price"))
                if not payout or not ask:
                    key = "quote had no payout or ask_price"
                    errors[key] = errors.get(key, 0) + 1
                    if not shown:
                        print(f"{symbol}: example quote without price fields, keys: {sorted(proposal)}")
                        shown = True
                    continue
                ratio = payout / ask
                if kind in ("CALL", "PUT"):
                    fair = fair_rf.get((kind, duration))
                else:
                    fair = digit_fair(kind, barrier)
                rows.append(
                    {
                        "scanned_at": stamp,
                        "symbol": symbol,
                        "contract": kind,
                        "barrier": barrier,
                        "duration": duration,
                        "ratio": ratio,
                        "needs": 1.0 / ratio,
                        "fair": fair,
                        "margin": None if fair is None else 1.0 - fair * ratio,
                    }
                )
            for message, count in errors.items():
                print(f"{symbol}: {count} requests refused: {message}")
            print(f"{symbol}: {sum(1 for r in rows if r['symbol'] == symbol)} quotes collected", flush=True)
    await engine.dispose()
    return rows

def line(r):
    barrier = "-" if r["barrier"] is None else str(r["barrier"])
    fair = "    -" if r["fair"] is None else f"{r['fair']:6.2%}"
    margin = "    -" if r["margin"] is None else f"{r['margin']:+6.2%}"
    return (
        f"{r['symbol']:9} {r['contract']:11} barrier {barrier:>1} {r['duration']:>2}t  "
        f"pays x{r['ratio']:.4f}  needs {r['needs']:6.2%}  fair {fair}  margin {margin}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("symbols", nargs="+")
    parser.add_argument("--stake", type=float, default=10.0)
    parser.add_argument("--digit-durations", nargs="+", type=int, default=[1, 2, 5])
    parser.add_argument("--rf-durations", nargs="+", type=int, default=[5, 10])
    parser.add_argument("--pause", type=float, default=0.5)
    parser.add_argument("--out", default="pricing_scan.csv")
    args = parser.parse_args()

    rows = asyncio.run(scan(args.symbols, args.stake, args.digit_durations, args.rf_durations, args.pause))
    if not rows:
        raise SystemExit("no quotes came back")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    measured = [r for r in rows if r["margin"] is not None]

    print("\n== Margin by contract type (all symbols, barriers, durations) ==")
    kinds = {}
    for r in measured:
        kinds.setdefault(r["contract"], []).append(r["margin"])
    for kind, values in sorted(kinds.items()):
        print(
            f"{kind:11} n={len(values):4}  min {min(values):+6.2%}  "
            f"median {float(np.median(values)):+6.2%}  max {max(values):+6.2%}"
        )

    print("\n== Cheapest 15 (lowest margin) ==")
    for r in sorted(measured, key=lambda r: r["margin"])[:15]:
        print(line(r))

    print("\n== Most expensive 8 ==")
    for r in sorted(measured, key=lambda r: -r["margin"])[:8]:
        print(line(r))

    negative = [r for r in measured if r["margin"] <= 0]
    if negative:
        print(f"\n== {len(negative)} quotes with margin at or below zero ==")
        for r in negative:
            print(line(r))
    else:
        print("\nNo quote had a margin at or below zero.")

    unmeasured = [r for r in rows if r["margin"] is None]
    if unmeasured:
        print(f"\n{len(unmeasured)} rise/fall quotes have no margin because that symbol has too few stored ticks; their break-even is still shown in {args.out}")
    print(f"\nfull table saved to {args.out}")


if __name__ == "__main__":
    main()