from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import current_user
from app.models import ActiveAccount, DerivAccount, DerivConnection, Symbol, User
from app.strategies import (
    CATALOGUE,
    DISCLAIMER_POINTS,
    DISCLAIMER_VERSION,
    LIVE_CONFIRMATION,
    MARTINGALE_MODES,
    contract_label,
    cycle_stakes,
    deriv_contract,
    martingale_preview,
    session_preview,
)
from app.trade_engine import HARD_LIMITS, BotSession, effective_limits
from app.trade_models import Trade, TradingSettings

router = APIRouter(prefix="/trading", tags=["trading"])

LIMIT_KEYS = ("max_stake", "daily_loss_cap", "max_trades_per_hour", "max_consecutive_losses")


class SettingsIn(BaseModel):
    max_stake: float | None = Field(default=None, gt=0)
    daily_loss_cap: float | None = Field(default=None, gt=0)
    max_trades_per_hour: int | None = Field(default=None, ge=1)
    max_consecutive_losses: int | None = Field(default=None, ge=1)
    live_enabled: bool | None = None
    confirm_text: str | None = None


class AckIn(BaseModel):
    version: str


class MartingaleIn(BaseModel):
    multiplier: float = Field(ge=1.1, le=3.0)
    max_steps: int = Field(ge=2, le=6)
    on_cap: str = Field(pattern="^(stop|reset)$")


class SessionIn(BaseModel):
    target: float = Field(gt=0)
    window_minutes: int = Field(ge=5, le=1440)
    on_target: str = Field(pattern="^(rest|stop)$")


class StartIn(BaseModel):
    strategy: str
    symbol: str
    stake: float = Field(gt=0)
    martingale: MartingaleIn | None = None
    session: SessionIn | None = None


async def get_settings(db: AsyncSession, user: User) -> TradingSettings:
    row = await db.get(TradingSettings, user.id)
    if row is None:
        row = TradingSettings(user_id=user.id, tenant_id=user.tenant_id)
        db.add(row)
        await db.flush()
    return row


async def active_account(db: AsyncSession, user: User) -> DerivAccount | None:
    active = await db.get(ActiveAccount, user.id)
    if active is None:
        return None
    return await db.scalar(
        select(DerivAccount)
        .join(DerivConnection, DerivAccount.connection_id == DerivConnection.id)
        .where(
            DerivAccount.id == active.account_id,
            DerivAccount.tenant_id == user.tenant_id,
            DerivConnection.tenant_id == user.tenant_id,
            DerivConnection.user_id == user.id,
        )
    )


def settings_out(row: TradingSettings, user: User) -> dict:
    return {
        "live_enabled": row.live_enabled,
        "acknowledged": row.acknowledged_version == DISCLAIMER_VERSION,
        "max_stake": row.max_stake,
        "daily_loss_cap": row.daily_loss_cap,
        "max_trades_per_hour": row.max_trades_per_hour,
        "max_consecutive_losses": row.max_consecutive_losses,
        "hard_limits": HARD_LIMITS,
        "can_enable_live": user.role == "owner",
        "live_confirmation": LIVE_CONFIRMATION,
    }


def trade_out(t: Trade) -> dict:
    return {
        "id": str(t.id),
        "created_at": t.created_at,
        "settled_at": t.settled_at,
        "mode": t.mode,
        "strategy": t.strategy,
        "symbol": t.symbol,
        "contract_type": t.contract_type,
        "barrier": t.barrier,
        "duration": t.duration,
        "step": t.step,
        "stake": t.stake,
        "payout": t.payout,
        "status": t.status,
        "profit": t.profit,
        "signal_epoch": t.signal_epoch,
        "entry_epoch": t.entry_epoch,
        "error": t.error,
    }


def stats_for(rows: list[Trade]) -> dict:
    settled = [t for t in rows if t.status in ("won", "lost") and t.profit is not None]
    n = len(settled)
    wins = sum(1 for t in settled if t.status == "won")
    paid = sum(t.payout or 0.0 for t in settled)
    staked = sum(t.stake for t in settled)
    expected = sum(
        (t.fair_prob or 0.0) * (t.payout or 0.0) - t.stake for t in settled if t.fair_prob is not None
    )
    return {
        "trades": n,
        "wins": wins,
        "losses": n - wins,
        "win_rate": wins / n if n else None,
        "profit": round(sum(t.profit for t in settled), 2),
        "expected_profit": round(expected, 2),
        "breakeven": staked / paid if paid else None,
    }


@router.get("/disclaimer")
async def disclaimer(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    row = await get_settings(db, user)
    await db.commit()
    return {
        "version": DISCLAIMER_VERSION,
        "points": DISCLAIMER_POINTS,
        "acknowledged": row.acknowledged_version == DISCLAIMER_VERSION,
    }


@router.post("/acknowledge")
async def acknowledge(
    payload: AckIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if payload.version != DISCLAIMER_VERSION:
        raise HTTPException(status_code=409, detail="The disclaimer changed. Reload and read it again.")
    row = await get_settings(db, user)
    row.acknowledged_version = DISCLAIMER_VERSION
    row.acknowledged_at = datetime.now(timezone.utc)
    await db.commit()
    return settings_out(row, user)


@router.get("/settings")
async def read_settings(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    row = await get_settings(db, user)
    await db.commit()
    return settings_out(row, user)


@router.patch("/settings")
async def update_settings(
    payload: SettingsIn,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await get_settings(db, user)
    ceiling = HARD_LIMITS["demo"]
    for key in LIMIT_KEYS:
        value = getattr(payload, key)
        if value is None:
            continue
        if value > ceiling[key]:
            raise HTTPException(status_code=422, detail=f"{key} cannot be above {ceiling[key]}.")
        setattr(row, key, value)
    switched_off = False
    if payload.live_enabled is True:
        if user.role != "owner":
            raise HTTPException(status_code=403, detail="Only the workspace owner can enable live trading.")
        if row.acknowledged_version != DISCLAIMER_VERSION:
            raise HTTPException(status_code=403, detail="Accept the risk disclaimer first.")
        if payload.confirm_text != LIVE_CONFIRMATION:
            raise HTTPException(status_code=422, detail=f"Type {LIVE_CONFIRMATION} to confirm.")
        row.live_enabled = True
    elif payload.live_enabled is False:
        switched_off = row.live_enabled
        row.live_enabled = False
    await db.commit()
    if switched_off:
        running = request.app.state.bots.get(user.id)
        if running is not None and running.running and running.mode == "real":
            await request.app.state.bots.stop(user.id)
    return settings_out(row, user)


@router.get("/strategies")
async def strategies(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    symbols = (
        await db.scalars(
            select(Symbol).where(
                Symbol.collect.is_(True), Symbol.active.is_(True), Symbol.is_suspended.is_(False)
            )
        )
    ).all()
    out = []
    for entry in CATALOGUE.values():
        needed, _ = deriv_contract(entry["spec"]["contract"])
        usable = [
            {"symbol": s.symbol, "name": s.name}
            for s in symbols
            if needed in (s.contract_types or "").split(",")
        ]
        out.append(
            {
                "key": entry["key"],
                "name": entry["name"],
                "summary": entry["summary"],
                "tested": entry["tested"],
                "contract": contract_label(entry["spec"]),
                "break_even": round(entry["break_even"] * 100, 2),
                "margin": round(entry["spec"]["margin"] * 100, 2),
                "symbols": usable,
            }
        )
    return out


@router.get("/martingale/preview")
async def preview_martingale(
    strategy: str,
    stake: float = Query(gt=0),
    multiplier: float = Query(ge=1.1, le=3.0),
    max_steps: int = Query(ge=2, le=6),
    target: float | None = Query(default=None, gt=0),
    user: User = Depends(current_user),
):
    entry = CATALOGUE.get(strategy)
    if entry is None:
        raise HTTPException(status_code=404, detail="Unknown strategy.")
    out = martingale_preview(entry, stake, multiplier, max_steps)
    out["session"] = None
    if target is not None:
        if target > 100 * stake:
            raise HTTPException(status_code=422, detail="The target is too large for this stake.")
        out["session"] = session_preview(entry, stake, multiplier, max_steps, target)
    return out


@router.post("/start")
async def start(
    payload: StartIn,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await get_settings(db, user)
    await db.commit()
    if row.acknowledged_version != DISCLAIMER_VERSION:
        raise HTTPException(status_code=403, detail="Read and accept the risk disclaimer first.")
    account = await active_account(db, user)
    if account is None:
        raise HTTPException(status_code=409, detail="Connect a Deriv account first.")
    mode = "real" if account.account_type == "real" else "demo"
    if mode == "real" and not row.live_enabled:
        raise HTTPException(
            status_code=403,
            detail="Live trading is switched off. Switch to a demo account, or enable it in Settings.",
        )
    entry = CATALOGUE.get(payload.strategy)
    if entry is None:
        raise HTTPException(status_code=404, detail="Unknown strategy.")
    symbol = await db.get(Symbol, payload.symbol)
    needed, _ = deriv_contract(entry["spec"]["contract"])
    if (
        symbol is None
        or not symbol.active
        or symbol.is_suspended
        or not symbol.collect
        or needed not in (symbol.contract_types or "").split(",")
    ):
        raise HTTPException(status_code=422, detail="That market cannot run this strategy.")
    collector = request.app.state.collector
    if payload.symbol not in collector.enabled:
        raise HTTPException(
            status_code=409, detail="That market is not streaming yet. Add it on the Markets page first."
        )
    limits = effective_limits(mode, row)
    if payload.stake > limits["max_stake"]:
        raise HTTPException(
            status_code=422, detail=f"Stake is above your {mode} limit of {limits['max_stake']:.2f}."
        )
    martingale = None
    if payload.martingale is not None:
        if mode not in MARTINGALE_MODES:
            raise HTTPException(status_code=403, detail="Martingale is only available on demo accounts.")
        martingale = payload.martingale.model_dump()
        stakes = cycle_stakes(payload.stake, martingale["multiplier"], martingale["max_steps"])
        if max(stakes) > limits["max_stake"]:
            raise HTTPException(
                status_code=422,
                detail=f"The largest martingale stake ({max(stakes):.2f}) is above your {mode} limit of {limits['max_stake']:.2f}.",
            )
        if sum(stakes) > limits["daily_loss_cap"]:
            raise HTTPException(
                status_code=422,
                detail=f"A full losing cycle costs {sum(stakes):.2f}, above your daily loss limit of {limits['daily_loss_cap']:.2f}.",
            )
    session_cfg = None
    if payload.session is not None:
        if martingale is None:
            raise HTTPException(
                status_code=422,
                detail="A session target needs martingale staking so each session has a defined worst case.",
            )
        session_cfg = payload.session.model_dump()
        if session_cfg["target"] > 100 * payload.stake:
            raise HTTPException(status_code=422, detail="The target is too large for this stake.")
    bots = request.app.state.bots
    bot = BotSession(
        collector,
        user.id,
        user.tenant_id,
        account,
        payload.strategy,
        payload.symbol,
        payload.stake,
        martingale,
        session_cfg,
    )
    try:
        bots.start(bot)
    except RuntimeError:
        raise HTTPException(status_code=409, detail="A bot is already running. Stop it first.")
    return bot.snapshot()


@router.post("/stop")
async def stop(request: Request, user: User = Depends(current_user)):
    session = await request.app.state.bots.stop(user.id)
    return {"session": session.snapshot() if session else None}


@router.get("/status")
async def status(
    request: Request, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    session = request.app.state.bots.get(user.id)
    account = await active_account(db, user)
    return {
        "session": session.snapshot() if session else None,
        "account_type": account.account_type if account else None,
    }


@router.get("/trades")
async def trades(
    limit: int = Query(50, ge=1, le=500),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await active_account(db, user)
    if account is None:
        return {"trades": [], "stats": stats_for([])}
    rows = (
        await db.scalars(
            select(Trade)
            .where(Trade.user_id == user.id, Trade.account_id == account.id)
            .order_by(Trade.created_at.desc())
            .limit(1000)
        )
    ).all()
    return {"trades": [trade_out(t) for t in rows[:limit]], "stats": stats_for(list(rows))}