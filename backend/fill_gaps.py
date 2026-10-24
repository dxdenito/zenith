import argparse
import asyncio
import time

import numpy as np
import websockets
from sqlalchemy import select

from app.collector import Collector
from app.database import SessionLocal, engine
from app.market_sync import PUBLIC_URL, call
from app.models import Tick

WINDOW = 4900


async def stored_epochs(symbol):
    async with SessionLocal() as db:
        rows = (
            await db.execute(select(Tick.epoch).where(Tick.symbol == symbol).order_by(Tick.epoch))
        ).scalars().all()
    return np.asarray(rows, dtype=np.int64)


def find_holes(epochs, now):
    diffs = np.diff(epochs)
    values, counts = np.unique(diffs, return_counts=True)
    interval = int(values[np.argmax(counts)])
    holes = [(int(epochs[i]), int(epochs[i + 1])) for i in np.flatnonzero(diffs > interval)]
    if now - int(epochs[-1]) > 5 * interval:
        holes.append((int(epochs[-1]), now + 1))
    return interval, holes


async def fill(ws, collector, symbol, holes, req):
    fetched = 0
    for number, (a, b) in enumerate(holes, 1):
        start = a + 1
        while start < b:
            end = min(start + WINDOW - 1, b - 1)
            req += 1
            reply = await call(
                ws,
                {
                    "ticks_history": symbol,
                    "start": str(start),
                    "end": str(end),
                    "count": 5000,
                    "style": "ticks",
                },
                req,
            )
            if reply.get("error"):
                print("error:", reply["error"].get("message"))
                return fetched, req
            history = reply.get("history") or {}
            for epoch, price in zip(history.get("times", []), history.get("prices", [])):
                if a < epoch < b:
                    collector.add(symbol, epoch, price, reply.get("pip_size"))
                    fetched += 1
            await collector.flush()
            start = end + 1
            await asyncio.sleep(0.25)
        if number % 10 == 0:
            print(f"{symbol}: {number}/{len(holes)} holes done, {fetched:,} ticks added")
    return fetched, req


async def run(symbols):
    now = int(time.time())
    req = 1
    async with websockets.connect(PUBLIC_URL, ping_interval=20) as ws:
        collector = Collector()
        for symbol in symbols:
            epochs = await stored_epochs(symbol)
            if len(epochs) < 100:
                print(f"{symbol}: not enough stored ticks to find holes")
                continue
            interval, holes = find_holes(epochs, now)
            missing = sum(max((b - a) // interval - 1, 0) for a, b in holes)
            print(f"{symbol}: {len(holes)} holes, about {missing:,} ticks missing ({missing * interval / 86400:.1f} days)")
            fetched, req = await fill(ws, collector, symbol, holes, req)
            print(f"{symbol}: {fetched:,} ticks added")
    await engine.dispose()


parser = argparse.ArgumentParser()
parser.add_argument("symbols", nargs="+")
args = parser.parse_args()
asyncio.run(run(args.symbols))