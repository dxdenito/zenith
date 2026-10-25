import asyncio

from sqlalchemy import text

from app.database import engine


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE trades ADD COLUMN IF NOT EXISTS step INTEGER NOT NULL DEFAULT 1"))
    await engine.dispose()
    print("trades.step ready")


asyncio.run(main())