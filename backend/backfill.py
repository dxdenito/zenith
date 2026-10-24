import argparse
import asyncio
import time

import websockets
from sqlalchemy import func, select

from app.collector import Collector
from app.database import SessionLocal, engine
from app.market_sync import PUBLIC_URL, call
from app.models import Tick

WINDOW = 4900


async def run(symbol: str, target: int) -> None:
    collector = Collector()
    end = int(time.time())
    total = 0
    empty = 0
    req = 1
    async with websockets.connect(PUBLIC_URL, ping_interval=20) as ws:
        while total < target:
            req += 1
            start = end - WINDOW
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
                break
            history = reply.get("history") or {}
            times = history.get("times", [])
            prices = history.get("prices", [])
            if times:
                empty = 0
                for epoch, price in zip(times, prices):
                    collector.add(symbol, epoch, price, reply.get("pip_size"))
                await collector.flush()
                total += len(times)
                print(f"{symbol}: {total} ticks fetched, back to epoch {min(times)}")
            else:
                empty += 1
                if empty >= 3:
                    print("no data further back, stopping")
                    break
            end = start - 1
            await asyncio.sleep(0.25)

    async with SessionLocal() as db:
        stored = await db.scalar(select(func.count()).where(Tick.symbol == symbol))
    print(f"{symbol}: {stored} ticks now stored")
    await engine.dispose()


parser = argparse.ArgumentParser()
parser.add_argument("symbol")
parser.add_argument("--target", type=int, default=100000)
args = parser.parse_args()
asyncio.run(run(args.symbol, args.target))