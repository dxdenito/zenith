import asyncio
import uuid

import jwt
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.cookies import ACCESS_COOKIE
from app.database import SessionLocal, get_db
from app.deps import current_user
from app.market_sync import MARKET_ERRORS, sync_symbols
from app.models import Symbol, Tick, User
from app.security import read_token

router = APIRouter(prefix="/markets", tags=["markets"])

FAMILIES = {
    "even_odd": {"DIGITEVEN", "DIGITODD"},
    "over_under": {"DIGITOVER", "DIGITUNDER"},
    "rise_fall": {"CALL", "PUT"},
}


class SymbolOut(BaseModel):
    symbol: str
    name: str
    submarket: str | None
    pip_decimals: int
    is_open: bool
    is_suspended: bool
    collect: bool
    families: list[str]


class CollectIn(BaseModel):
    collect: bool


class TickOut(BaseModel):
    epoch: int
    quote: float
    digit: int


def to_out(row: Symbol) -> SymbolOut:
    types = {t for t in row.contract_types.split(",") if t}
    return SymbolOut(
        symbol=row.symbol,
        name=row.name,
        submarket=row.submarket,
        pip_decimals=row.pip_decimals,
        is_open=row.is_open,
        is_suspended=row.is_suspended,
        collect=row.collect,
        families=[name for name, needed in FAMILIES.items() if needed <= types],
    )


def require_owner(user: User) -> None:
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Only the space owner can change this.")


@router.get("/symbols", response_model=list[SymbolOut])
async def list_symbols(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(Symbol).where(Symbol.active.is_(True)).order_by(Symbol.submarket, Symbol.name)
        )
    ).all()
    return [to_out(r) for r in rows]


@router.post("/symbols/sync")
async def sync(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    require_owner(user)
    try:
        count = await sync_symbols(db)
    except MARKET_ERRORS:
        raise HTTPException(status_code=502, detail="Could not reach Deriv market data.")
    return {"synced": count}


@router.patch("/symbols/{symbol}", response_model=SymbolOut)
async def set_collect(
    symbol: str,
    payload: CollectIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    require_owner(user)
    row = await db.get(Symbol, symbol)
    if row is None or not row.active:
        raise HTTPException(status_code=404, detail="Symbol not found.")
    row.collect = payload.collect
    await db.commit()
    return to_out(row)


@router.get("/symbols/{symbol}/ticks", response_model=list[TickOut])
async def recent_ticks(
    symbol: str,
    limit: int = Query(300, ge=1, le=2000),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Symbol, symbol)
    if row is None or not row.active:
        raise HTTPException(status_code=404, detail="Symbol not found.")
    rows = (
        await db.execute(
            select(Tick.epoch, Tick.quote, Tick.digit)
            .where(Tick.symbol == symbol)
            .order_by(Tick.epoch.desc())
            .limit(limit)
        )
    ).all()
    return [TickOut(epoch=e, quote=q, digit=d) for e, q, d in reversed(rows)]


@router.get("/status")
async def status(
    request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    collector = request.app.state.collector
    rows = (
        await db.execute(
            select(Tick.symbol, func.count(), func.max(Tick.epoch)).group_by(Tick.symbol)
        )
    ).all()
    return {
        "connected": collector.stats["connected"],
        "received": collector.stats["ticks"],
        "symbols": [{"symbol": s, "ticks": c, "latest": e} for s, c, e in rows],
    }


@router.websocket("/stream")
async def stream(ws: WebSocket):
    if ws.headers.get("origin") not in settings.cors_list:
        await ws.close(code=1008)
        return
    try:
        user_id = uuid.UUID(read_token(ws.cookies.get(ACCESS_COOKIE, ""), "access"))
    except (jwt.PyJWTError, ValueError):
        await ws.close(code=1008)
        return
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        await ws.close(code=1008)
        return

    await ws.accept()
    collector = ws.app.state.collector
    queue = collector.subscribe()
    wanted: set[str] = set()

    async def reader():
        try:
            while True:
                data = await ws.receive_json()
                symbols = data.get("symbols") if isinstance(data, dict) else None
                if isinstance(symbols, list):
                    wanted.clear()
                    wanted.update(str(s) for s in symbols[:20])
        except (WebSocketDisconnect, ValueError, RuntimeError):
            return

    async def writer():
        try:
            while True:
                tick = await queue.get()
                if tick["symbol"] in wanted:
                    await ws.send_json({"type": "tick", **tick})
        except (WebSocketDisconnect, RuntimeError):
            return

    tasks = [asyncio.create_task(reader()), asyncio.create_task(writer())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        collector.unsubscribe(queue)