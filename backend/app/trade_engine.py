import asyncio
import copy
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone

import httpx
import numpy as np
import websockets
from sqlalchemy import func, select, update

from app.config import settings
from app.crypto import decrypt
from app.database import SessionLocal
from app.live_signal import live_signal
from app.market_sync import MARKET_ERRORS, call
from app.models import DerivAccount, DerivConnection, Tick
from app.register_rules import fair_probability, lookback, mode_interval
from app.strategies import CATALOGUE, cycle_stakes, deriv_contract
from app.trade_models import Trade, TradingSettings

OTP_URL = "https://api.derivws.com/trading/v1/options/accounts/{account_id}/otp"
SETTLE_TIMEOUT = 90
STALE_OPEN_MINUTES = 10
MAX_FAILURES = 5
PRICE_TOLERANCE = 1.02

HARD_LIMITS = {
    "demo": {
        "max_stake": 100.0,
        "daily_loss_cap": 1000.0,
        "max_trades_per_hour": 600,
        "max_consecutive_losses": 50,
    },
    "real": {
        "max_stake": 5.0,
        "daily_loss_cap": 20.0,
        "max_trades_per_hour": 120,
        "max_consecutive_losses": 10,
    },
}


class TradingHalt(Exception):
    pass


def effective_limits(mode, row):
    hard = HARD_LIMITS[mode]
    return {key: min(getattr(row, key), hard[key]) for key in hard}


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class TickBuffer:
    def __init__(self, size):
        self.epoch = deque(maxlen=size)
        self.quote = deque(maxlen=size)
        self.digit = deque(maxlen=size)

    def add(self, epoch, quote, digit):
        self.epoch.append(int(epoch))
        self.quote.append(float(quote))
        self.digit.append(int(digit))

    @property
    def last_epoch(self):
        return self.epoch[-1] if self.epoch else 0

    def arrays(self):
        return (
            np.asarray(self.epoch, dtype=np.int64),
            np.asarray(self.quote, dtype=float),
            np.asarray(self.digit, dtype=np.int64),
        )


class BotSession:
    def __init__(self, collector, user_id, tenant_id, account, strategy_key, symbol, stake, martingale=None):
        entry = CATALOGUE[strategy_key]
        self.collector = collector
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.account_id = account.id
        self.deriv_account_id = account.deriv_account_id
        self.mode = "real" if account.account_type == "real" else "demo"
        self.currency = account.currency or "USD"
        self.strategy_key = strategy_key
        self.strategy_name = entry["name"]
        self.symbol = symbol
        self.base_stake = float(stake)
        self.martingale = martingale is not None
        self.multiplier = float(martingale["multiplier"]) if martingale else 1.0
        self.max_steps = int(martingale["max_steps"]) if martingale else 1
        self.on_cap = martingale["on_cap"] if martingale else "stop"
        self.step = 0
        self.cap_hits = 0
        self.spec = copy.deepcopy(entry["spec"])
        self.spec["symbols"] = [symbol]
        self.contract_type, self.barrier = deriv_contract(self.spec["contract"])
        self.fair = fair_probability(self.spec["contract"])
        self.buffer = TickBuffer(max(400, lookback(self.spec) + 150))
        self.interval = 2
        self.session_id = uuid.uuid4()
        self.status = "starting"
        self.message = "Starting."
        self.started_at = time.time()
        self.signals = 0
        self.trades = 0
        self.wins = 0
        self.losses = 0
        self.profit = 0.0
        self.streak = 0
        self.failures = 0
        self.req = 1000
        self.last_tick = None
        self.settling = False
        self.stop_requested = False
        self.task = None

    @property
    def running(self):
        return self.task is not None and not self.task.done()

    @property
    def stake(self):
        if not self.martingale:
            return self.base_stake
        return round(self.base_stake * self.multiplier**self.step, 2)

    def snapshot(self):
        return {
            "session_id": str(self.session_id),
            "status": self.status,
            "message": self.message,
            "strategy": self.strategy_key,
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "mode": self.mode,
            "stake": self.stake,
            "base_stake": self.base_stake,
            "martingale": self.martingale,
            "multiplier": self.multiplier,
            "step": self.step + 1,
            "max_steps": self.max_steps,
            "on_cap": self.on_cap,
            "cap_hits": self.cap_hits,
            "started_at": self.started_at,
            "signals": self.signals,
            "trades": self.trades,
            "wins": self.wins,
            "losses": self.losses,
            "profit": round(self.profit, 2),
            "streak": self.streak,
            "settling": self.settling,
            "last_tick": self.last_tick,
            "running": self.running,
        }

    async def ask(self, ws, payload):
        self.req += 1
        return await call(ws, payload, self.req)

    def register_failure(self, message):
        self.failures += 1
        self.message = message
        if self.failures >= MAX_FAILURES:
            raise TradingHalt(f"Stopped after repeated problems. Last: {message}")

    async def mark_stale(self):
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_OPEN_MINUTES)
        async with SessionLocal() as db:
            await db.execute(
                update(Trade)
                .where(
                    Trade.user_id == self.user_id,
                    Trade.status == "open",
                    Trade.created_at < cutoff,
                )
                .values(status="unknown", error="The result was never confirmed.")
            )
            await db.commit()

    async def warm_buffer(self):
        size = self.buffer.epoch.maxlen
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(Tick.epoch, Tick.quote, Tick.digit)
                    .where(Tick.symbol == self.symbol)
                    .order_by(Tick.epoch.desc())
                    .limit(size)
                )
            ).all()
        merged = {int(r[0]): (r[1], r[2]) for r in rows}
        for row in list(self.collector.buffer):
            if row["symbol"] == self.symbol:
                merged[int(row["epoch"])] = (row["quote"], row["digit"])
        for epoch in sorted(merged)[-size:]:
            quote, digit = merged[epoch]
            self.buffer.add(epoch, quote, digit)
        if len(self.buffer.epoch) >= 20:
            self.interval = mode_interval(np.asarray(self.buffer.epoch, dtype=np.int64))

    async def fetch_ws_url(self):
        async with SessionLocal() as db:
            account = await db.get(DerivAccount, self.account_id)
            if account is None:
                raise TradingHalt("The account is no longer linked.")
            connection = await db.get(DerivConnection, account.connection_id)
            if connection is None:
                raise TradingHalt("Your Deriv link was removed. Reconnect in Settings.")
            expired = connection.status != "active" or (
                connection.expires_at is not None
                and connection.expires_at <= datetime.now(timezone.utc)
            )
            if expired:
                raise TradingHalt("Your Deriv link has expired. Reconnect in Settings.")
            token = decrypt(connection.access_token_enc)
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(
                OTP_URL.format(account_id=self.deriv_account_id),
                headers={"Authorization": f"Bearer {token}", "Deriv-App-ID": settings.deriv_app_id},
            )
        if res.status_code in (401, 403):
            raise TradingHalt(
                "Deriv rejected the saved token. Reconnect in Settings and make sure the trade permission is granted."
            )
        if res.status_code >= 300:
            raise TradingHalt(f"Deriv would not open a trading session ({res.status_code}): {res.text[:200]}")
        payload = res.json()
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        url = data.get("url") if isinstance(data, dict) else None
        if not url:
            raise TradingHalt("Deriv did not return a trading session URL.")
        channel = "/ws/real" if self.mode == "real" else "/ws/demo"
        if channel not in url:
            raise TradingHalt("Deriv returned a session for a different account type. Refusing to trade.")
        return url

    async def check_limits(self):
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour_ago = now - timedelta(hours=1)
        async with SessionLocal() as db:
            row = await db.get(TradingSettings, self.user_id)
            account = await db.get(DerivAccount, self.account_id)
            realized = await db.scalar(
                select(func.coalesce(func.sum(Trade.profit), 0.0)).where(
                    Trade.user_id == self.user_id,
                    Trade.account_id == self.account_id,
                    Trade.created_at >= day_start,
                    Trade.profit.is_not(None),
                )
            )
            recent = await db.scalar(
                select(func.count(Trade.id)).where(
                    Trade.user_id == self.user_id,
                    Trade.account_id == self.account_id,
                    Trade.created_at >= hour_ago,
                )
            )
        if row is None:
            raise TradingHalt("Trading settings are missing.")
        if account is None:
            raise TradingHalt("The account is no longer linked.")
        mode = "real" if account.account_type == "real" else "demo"
        if mode != self.mode:
            raise TradingHalt("The account type changed. Stopping.")
        if mode == "real" and not row.live_enabled:
            raise TradingHalt("Live trading was switched off in Settings.")
        limits = effective_limits(mode, row)
        if self.stake > limits["max_stake"]:
            raise TradingHalt(f"Your stake is above the {limits['max_stake']:.2f} limit.")
        if realized <= -limits["daily_loss_cap"]:
            raise TradingHalt(f"Daily loss limit of {limits['daily_loss_cap']:.2f} reached (UTC day).")
        if self.martingale:
            remaining = sum(cycle_stakes(self.base_stake, self.multiplier, self.max_steps)[self.step :])
            if realized - remaining < -limits["daily_loss_cap"]:
                raise TradingHalt("The rest of this martingale cycle could break your daily loss limit. Stopped.")
        if self.streak >= limits["max_consecutive_losses"]:
            raise TradingHalt(f"{self.streak} losses in a row. Stopped.")
        if recent >= limits["max_trades_per_hour"]:
            self.message = "Hourly trade limit reached. Waiting."
            return False
        return True

    async def save_open(self, signal_epoch, payout, contract_id):
        trade = Trade(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            account_id=self.account_id,
            session_id=self.session_id,
            mode=self.mode,
            strategy=self.strategy_key,
            symbol=self.symbol,
            contract_type=self.contract_type,
            barrier=None if self.barrier is None else str(self.barrier),
            duration=self.spec["duration"],
            step=self.step + 1,
            stake=self.stake,
            payout=payout,
            fair_prob=self.fair,
            contract_id=str(contract_id),
            status="open",
            signal_epoch=signal_epoch,
        )
        try:
            async with SessionLocal() as db:
                db.add(trade)
                await db.commit()
        except Exception as exc:
            raise TradingHalt(
                f"Bought contract {contract_id} but could not record it ({exc!r}). Check your Deriv account."
            ) from exc
        return trade.id

    async def save_unknown(self, signal_epoch, payout, error):
        trade = Trade(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            account_id=self.account_id,
            session_id=self.session_id,
            mode=self.mode,
            strategy=self.strategy_key,
            symbol=self.symbol,
            contract_type=self.contract_type,
            barrier=None if self.barrier is None else str(self.barrier),
            duration=self.spec["duration"],
            step=self.step + 1,
            stake=self.stake,
            payout=payout,
            fair_prob=self.fair,
            status="unknown",
            signal_epoch=signal_epoch,
            error=error[:500],
        )
        try:
            async with SessionLocal() as db:
                db.add(trade)
                await db.commit()
        except Exception as exc:
            print(f"[trading] could not record unknown trade: {exc!r}")

    async def settle(self, ws, trade_id, contract_id):
        cid = int(contract_id) if str(contract_id).isdigit() else contract_id
        deadline = time.time() + SETTLE_TIMEOUT
        poc = {}
        done = False
        self.settling = True
        try:
            while time.time() < deadline and not done:
                reply = await self.ask(ws, {"proposal_open_contract": 1, "contract_id": cid})
                poc = reply.get("proposal_open_contract") or {}
                if poc.get("is_sold") in (1, True, "1") or poc.get("status") in ("won", "lost"):
                    done = True
                else:
                    await asyncio.sleep(1.0)
        finally:
            self.settling = False
        async with SessionLocal() as db:
            trade = await db.get(Trade, trade_id)
            if not done:
                trade.status = "unknown"
                trade.error = "The result was not confirmed in time."
                await db.commit()
                raise TradingHalt(
                    f"Could not confirm the result of contract {contract_id}. Check your Deriv account."
                )
            profit = number(poc.get("profit"))
            if profit is None:
                sell = number(poc.get("sell_price"))
                buy = number(poc.get("buy_price"))
                profit = (sell - buy) if sell is not None and buy is not None else 0.0
            status = poc.get("status")
            won = status == "won" if status in ("won", "lost") else profit > 0
            entry_time = number(poc.get("entry_tick_time"))
            trade.status = "won" if won else "lost"
            trade.profit = profit
            trade.entry_epoch = int(entry_time) if entry_time is not None else None
            trade.settled_at = datetime.now(timezone.utc)
            await db.commit()
        self.trades += 1
        self.profit += profit
        self.message = f"Last trade {'won' if won else 'lost'} {profit:+.2f}."
        if won:
            self.wins += 1
            self.streak = 0
            self.step = 0
            return
        self.losses += 1
        self.streak += 1
        if not self.martingale:
            return
        self.step += 1
        if self.step >= self.max_steps:
            self.cap_hits += 1
            self.step = 0
            if self.on_cap == "stop":
                raise TradingHalt(
                    f"Martingale cap reached: {self.max_steps} losses in a row. Stopped to cut losses."
                )
            self.message += f" Cap reached after {self.max_steps} losses. Back to the base stake."

    async def try_trade(self, ws, signal_epoch):
        if not await self.check_limits():
            return
        payload = {
            "proposal": 1,
            "amount": self.stake,
            "basis": "stake",
            "contract_type": self.contract_type,
            "currency": self.currency,
            "duration": self.spec["duration"],
            "duration_unit": "t",
            "underlying_symbol": self.symbol,
        }
        if self.barrier is not None:
            payload["barrier"] = str(self.barrier)
        reply = await self.ask(ws, payload)
        if reply.get("error"):
            self.register_failure(f"Quote refused: {reply['error'].get('message', 'error')}")
            return
        proposal = reply.get("proposal") or {}
        proposal_id = proposal.get("id")
        ask = number(proposal.get("ask_price"))
        payout = number(proposal.get("payout"))
        if not proposal_id or not ask or not payout:
            self.register_failure("The quote came back without a price.")
            return
        if ask > self.stake * PRICE_TOLERANCE or payout <= ask:
            self.register_failure("The quoted price was not acceptable. Skipped.")
            return
        try:
            bought = await self.ask(ws, {"buy": proposal_id, "price": ask})
        except Exception as exc:
            await self.save_unknown(signal_epoch, payout, f"Buy did not complete: {exc!r}")
            raise TradingHalt(
                "A buy request did not complete. Check your Deriv account before restarting."
            ) from exc
        if bought.get("error"):
            self.register_failure(f"Buy refused: {bought['error'].get('message', 'error')}")
            return
        info = bought.get("buy") or {}
        contract_id = info.get("contract_id")
        if contract_id is None:
            await self.save_unknown(signal_epoch, payout, "The buy response had no contract id.")
            raise TradingHalt(
                "A buy response had no contract id. Check your Deriv account before restarting."
            )
        self.failures = 0
        trade_id = await self.save_open(signal_epoch, payout, contract_id)
        await self.settle(ws, trade_id, contract_id)

    async def trade_loop(self, ws, queue):
        self.message = "Watching ticks and waiting for the strategy to trigger."
        while not self.stop_requested:
            try:
                first = await asyncio.wait_for(queue.get(), timeout=3)
            except asyncio.TimeoutError:
                if self.last_tick and time.time() - self.last_tick > 30:
                    self.message = "No live ticks are arriving. Waiting."
                continue
            batch = [first]
            while True:
                try:
                    batch.append(queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            fresh = [
                r
                for r in batch
                if r["symbol"] == self.symbol and r["epoch"] > self.buffer.last_epoch
            ]
            if not fresh:
                continue
            for r in fresh:
                self.buffer.add(r["epoch"], r["quote"], r["digit"])
            self.last_tick = time.time()
            epoch, quote, digit = self.buffer.arrays()
            if not live_signal(self.spec, epoch, quote, digit, self.interval):
                continue
            self.signals += 1
            await self.try_trade(ws, int(fresh[-1]["epoch"]))

    async def run(self):
        queue = self.collector.subscribe()
        try:
            await self.mark_stale()
            await self.warm_buffer()
            url = await self.fetch_ws_url()
            async with websockets.connect(url, ping_interval=20, open_timeout=30) as ws:
                self.status = "running"
                await self.trade_loop(ws, queue)
        except asyncio.CancelledError:
            if self.status != "halted":
                self.status = "stopped"
                self.message = "Stopped."
            raise
        except TradingHalt as halt:
            self.status = "halted"
            self.message = str(halt)
        except MARKET_ERRORS + (httpx.HTTPError,) as exc:
            self.status = "halted"
            self.message = f"Connection problem: {exc!r}"
        except Exception as exc:
            self.status = "halted"
            self.message = f"Unexpected error: {exc!r}"
        finally:
            self.collector.unsubscribe(queue)
            if self.status in ("starting", "running"):
                self.status = "stopped"
                self.message = "Stopped."


class BotManager:
    def __init__(self, collector):
        self.collector = collector
        self.sessions = {}

    def get(self, user_id):
        return self.sessions.get(user_id)

    def start(self, session):
        existing = self.sessions.get(session.user_id)
        if existing is not None and existing.running:
            raise RuntimeError("A bot is already running.")
        session.task = asyncio.create_task(session.run())
        self.sessions[session.user_id] = session

    async def stop(self, user_id):
        session = self.sessions.get(user_id)
        if session is None or not session.running:
            return session
        session.stop_requested = True
        session.message = "Stopping after the current trade."
        try:
            await asyncio.wait_for(asyncio.shield(session.task), timeout=45)
        except asyncio.TimeoutError:
            session.task.cancel()
            await asyncio.gather(session.task, return_exceptions=True)
        return session

    async def shutdown(self):
        active = [s for s in self.sessions.values() if s.running]
        for session in active:
            session.stop_requested = True
        if active:
            await asyncio.wait([s.task for s in active], timeout=20)
        for session in active:
            if session.running:
                session.task.cancel()
        await asyncio.gather(*[s.task for s in active], return_exceptions=True)