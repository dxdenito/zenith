import asyncio
import json

import websockets
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.database import SessionLocal
from app.market_sync import MARKET_ERRORS, PUBLIC_URL
from app.models import Symbol, Tick

RECONCILE_SECONDS = 10
FLUSH_SECONDS = 1
BACKFILL_COUNT = 5000
BATCH_SIZE = 2000
BUFFER_LIMIT = 50000


class Collector:
    def __init__(self):
        self.enabled: set[str] = set()
        self.subscribed: dict[str, str | None] = {}
        self.backfills: dict[int, str] = {}
        self.buffer: list[dict] = []
        self.req = 100
        self.healthy = False
        self.stats = {"connected": False, "ticks": 0, "last_epoch": None}
        self.listeners: set[asyncio.Queue] = set()

    def next_req(self) -> int:
        self.req += 1
        return self.req

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.listeners.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.listeners.discard(queue)

    def publish(self, row: dict) -> None:
        for queue in self.listeners:
            try:
                queue.put_nowait(row)
            except asyncio.QueueFull:
                continue

    async def load_enabled(self) -> set[str]:
        async with SessionLocal() as db:
            rows = await db.scalars(
                select(Symbol.symbol).where(Symbol.collect.is_(True), Symbol.active.is_(True))
            )
            return set(rows.all())

    def add(self, symbol: str, epoch, quote, pip, live: bool = False) -> None:
        try:
            decimals = int(round(float(pip)))
        except (TypeError, ValueError):
            decimals = 2
        price = float(quote)
        text = f"{price:.{decimals}f}"
        row = {"symbol": symbol, "epoch": int(epoch), "quote": price, "digit": int(text[-1])}
        self.buffer.append(row)
        if live:
            self.publish(row)
        self.stats["ticks"] += 1
        latest = self.stats["last_epoch"]
        self.stats["last_epoch"] = int(epoch) if latest is None else max(latest, int(epoch))

    def handle(self, msg: dict) -> None:
        if msg.get("error"):
            print(f"[collector] api error: {msg['error'].get('message')}")
            return
        kind = msg.get("msg_type")
        if kind == "tick":
            tick = msg["tick"]
            symbol = tick["symbol"]
            sub_id = (msg.get("subscription") or {}).get("id")
            if symbol in self.subscribed and sub_id and self.subscribed[symbol] is None:
                self.subscribed[symbol] = sub_id
            if symbol in self.enabled:
                self.add(symbol, tick["epoch"], tick["quote"], tick.get("pip_size"), live=True)
            self.healthy = True
        elif kind == "history":
            symbol = self.backfills.pop(msg.get("req_id"), None)
            if symbol and symbol in self.enabled:
                data = msg.get("history") or {}
                for epoch, price in zip(data.get("times", []), data.get("prices", [])):
                    self.add(symbol, epoch, price, msg.get("pip_size"))

    async def flush(self) -> None:
        if not self.buffer:
            return
        rows, self.buffer = self.buffer, []
        try:
            async with SessionLocal() as db:
                for start in range(0, len(rows), BATCH_SIZE):
                    chunk = rows[start : start + BATCH_SIZE]
                    await db.execute(insert(Tick).values(chunk).on_conflict_do_nothing())
                await db.commit()
        except Exception as exc:
            print(f"[collector] write failed: {exc!r}")
            self.buffer = (rows + self.buffer)[-BUFFER_LIMIT:]

    async def flusher(self) -> None:
        while True:
            await asyncio.sleep(FLUSH_SECONDS)
            await self.flush()

    async def reconcile(self, ws) -> None:
        while True:
            wanted = await self.load_enabled()
            self.enabled = wanted
            for symbol in sorted(wanted - set(self.subscribed)):
                self.subscribed[symbol] = None
                await ws.send(
                    json.dumps({"ticks": symbol, "subscribe": 1, "req_id": self.next_req()})
                )
                req = self.next_req()
                self.backfills[req] = symbol
                await ws.send(
                    json.dumps(
                        {
                            "ticks_history": symbol,
                            "count": BACKFILL_COUNT,
                            "end": "latest",
                            "style": "ticks",
                            "req_id": req,
                        }
                    )
                )
                print(f"[collector] subscribed {symbol}")
            for symbol in set(self.subscribed) - wanted:
                sub_id = self.subscribed.pop(symbol)
                if sub_id:
                    await ws.send(json.dumps({"forget": sub_id, "req_id": self.next_req()}))
                print(f"[collector] stopped {symbol}")
            await asyncio.sleep(RECONCILE_SECONDS)

    async def session(self) -> None:
        async with websockets.connect(PUBLIC_URL, ping_interval=20, ping_timeout=20) as ws:
            print("[collector] connected")
            self.stats["connected"] = True
            self.subscribed.clear()
            self.backfills.clear()
            tasks = [
                asyncio.create_task(self.reconcile(ws)),
                asyncio.create_task(self.flusher()),
            ]
            try:
                async for raw in ws:
                    self.handle(json.loads(raw))
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                await self.flush()

    async def run(self) -> None:
        delay = 2
        while True:
            self.healthy = False
            try:
                await self.session()
            except asyncio.CancelledError:
                raise
            except MARKET_ERRORS as exc:
                print(f"[collector] connection lost: {exc!r}")
            except Exception as exc:
                print(f"[collector] error: {exc!r}")
            self.stats["connected"] = False
            delay = 2 if self.healthy else min(delay * 2, 60)
            await asyncio.sleep(delay)