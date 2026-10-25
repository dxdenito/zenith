import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.collector import Collector
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.market_sync import sync_symbols
from app.models import Symbol
from app.routers import accounts, auth, markets, trading
from app.trade_engine import BotManager


async def initial_sync():
    try:
        async with SessionLocal() as db:
            if await db.scalar(select(Symbol.symbol).limit(1)) is None:
                count = await sync_symbols(db)
                print(f"[markets] synced {count} symbols")
    except Exception as exc:
        print(f"[markets] initial symbol sync failed: {exc!r}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    collector = Collector()
    app.state.collector = collector
    app.state.bots = BotManager(collector)
    tasks = [
        asyncio.create_task(initial_sync()),
        asyncio.create_task(collector.run()),
    ]
    yield
    await app.state.bots.shutdown()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await engine.dispose()


app = FastAPI(title="Zenith API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(markets.router)
app.include_router(trading.router)


@app.get("/health")
async def health():
    return {"status": "ok"}