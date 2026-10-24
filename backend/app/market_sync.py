import asyncio
import json
import math

import websockets
from websockets.exceptions import WebSocketException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Symbol

PUBLIC_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
WANTED = {"DIGITEVEN", "DIGITODD", "DIGITOVER", "DIGITUNDER", "CALL", "PUT"}
DEFAULT_COLLECT = {"R_100", "R_50", "1HZ100V"}


class MarketError(Exception):
    pass


MARKET_ERRORS = (
    MarketError,
    OSError,
    asyncio.TimeoutError,
    WebSocketException,
)


def decimals(pip) -> int:
    try:
        value = float(pip)
    except (TypeError, ValueError):
        return 2
    if value <= 0 or value >= 1:
        return 0
    return max(0, round(-math.log10(value)))


async def call(ws, payload: dict, req_id: int) -> dict:
    await ws.send(json.dumps({**payload, "req_id": req_id}))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
        if msg.get("req_id") == req_id:
            return msg


async def sync_symbols(db: AsyncSession) -> int:
    async with websockets.connect(PUBLIC_URL, ping_interval=20) as ws:
        reply = await call(ws, {"active_symbols": "brief"}, 1)
        if reply.get("error"):
            raise MarketError(str(reply["error"]))
        items = [
            s
            for s in reply.get("active_symbols", [])
            if s.get("market") == "synthetic_index" and s.get("underlying_symbol")
        ]
        found = []
        for number, item in enumerate(items, start=2):
            contracts = await call(ws, {"contracts_for": item["underlying_symbol"]}, number)
            available = (contracts.get("contracts_for") or {}).get("available", [])
            types = sorted({c.get("contract_type") for c in available} & WANTED)
            found.append((item, types))

    existing = {row.symbol: row for row in (await db.scalars(select(Symbol))).all()}
    seen = set()
    for item, types in found:
        code = item["underlying_symbol"]
        seen.add(code)
        row = existing.get(code)
        if row is None:
            row = Symbol(symbol=code, collect=code in DEFAULT_COLLECT)
            db.add(row)
        row.name = item.get("underlying_symbol_name") or code
        row.submarket = item.get("submarket")
        row.pip_decimals = decimals(item.get("pip_size"))
        row.is_open = bool(item.get("exchange_is_open", 1))
        row.is_suspended = bool(item.get("is_trading_suspended", 0))
        row.contract_types = ",".join(types)
        row.active = True
    for code, row in existing.items():
        if code not in seen:
            row.active = False
    await db.commit()
    return len(seen)