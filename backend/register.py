import argparse
import asyncio
import json
import time
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import func, or_, select

from app.database import Base, SessionLocal, engine
from app.models import Symbol, Tick
from app.register_models import Hypothesis
from app.register_rules import (
    binom_p,
    breakeven,
    canonical,
    find_trades,
    forward_trades,
    mode_interval,
    spec_hash,
    validate_spec,
)

LOOKBACK_SECONDS = 7200
ESTIMATE_DAYS = 3


def stamp(epoch) -> str:
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


async def load_window(db, symbol, since):
    rows = (
        await db.execute(
            select(Tick.epoch, Tick.quote, Tick.digit)
            .where(Tick.symbol == symbol, Tick.epoch >= since)
            .order_by(Tick.epoch)
        )
    ).all()
    if not rows:
        return None
    e, q, d = zip(*rows)
    return np.asarray(e, dtype=np.int64), np.asarray(q, dtype=float), np.asarray(d, dtype=np.int64)


async def firing_estimate(db, spec, now):
    per_hour = 0.0
    for symbol in spec["symbols"]:
        window = await load_window(db, symbol, now - ESTIMATE_DAYS * 86400)
        if window is None or len(window[0]) < 100:
            continue
        e, q, d = window
        interval = mode_interval(e)
        t_epoch, _ = find_trades(spec, e, q, d, interval, 0)
        hours = len(e) * interval / 3600
        per_hour += len(t_epoch) / hours
    return per_hour


def verdict_line(row, alpha) -> str:
    rate = row.wins / row.trades
    roi = rate / row.breakeven - 1.0
    passed = row.p_value < alpha and rate > row.breakeven
    tag = "PASS (a lead to demo-test, not proof)" if passed else "FAIL"
    return (
        f"#{row.id} {row.name}: {row.wins}/{row.trades} = {rate:.2%} vs break-even {row.breakeven:.2%} | "
        f"ROI {roi:+.2%} per trade | p={row.p_value:.4f} vs alpha {alpha:.4f} | {tag}"
    )


async def cmd_init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("hypotheses table ready")


async def cmd_add(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise SystemExit("the file must contain a JSON object")
    name = raw.pop("name", None)
    source = raw.pop("source", "")
    notes = raw.pop("notes", "")
    if not isinstance(name, str) or not name.strip():
        raise SystemExit("the rule needs a non-empty name")
    try:
        spec = validate_spec(raw)
    except ValueError as exc:
        raise SystemExit(f"invalid rule: {exc}")
    digest = spec_hash(spec)
    async with SessionLocal() as db:
        known = set((await db.execute(select(Symbol.symbol))).scalars())
        missing = [s for s in spec["symbols"] if s not in known]
        if missing:
            raise SystemExit(f"unknown symbols: {', '.join(missing)}")
        clash = (
            await db.execute(
                select(Hypothesis).where(or_(Hypothesis.spec_hash == digest, Hypothesis.name == name))
            )
        ).scalars().first()
        if clash:
            raise SystemExit(f"already registered as #{clash.id} '{clash.name}'")
        now = int(time.time())
        row = Hypothesis(
            name=name,
            source=str(source),
            notes=str(notes),
            spec=canonical(spec),
            spec_hash=digest,
            registered_epoch=now,
            target_trades=spec["target_trades"],
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        total = (await db.execute(select(func.count(Hypothesis.id)))).scalar_one()
        per_hour = await firing_estimate(db, spec, now)
    print(f"registered #{row.id} '{row.name}' at {stamp(now)} UTC")
    print(f"hash {digest[:16]} | break-even {breakeven(spec['contract'], spec['margin']):.2%}")
    print(f"needs {row.target_trades} trades after this moment; with {total} rules registered a pass needs p < {0.05 / total:.4f}")
    if per_hour > 0:
        print(f"recent data suggests about {per_hour:.0f} trades per hour of streaming, so about {row.target_trades / per_hour:.1f} hours of ticks")
    else:
        print("could not estimate how often the trigger fires from stored ticks")


async def cmd_list():
    async with SessionLocal() as db:
        rows = (await db.execute(select(Hypothesis).order_by(Hypothesis.id))).scalars().all()
    if not rows:
        print("no rules registered")
    for r in rows:
        print(f"#{r.id:<3} {r.status:10} {r.name:40} registered {stamp(r.registered_epoch)} UTC | target {r.target_trades} trades")


async def cmd_show(rule_id):
    async with SessionLocal() as db:
        total = (await db.execute(select(func.count(Hypothesis.id)))).scalar_one()
        row = (await db.execute(select(Hypothesis).where(Hypothesis.id == rule_id))).scalars().first()
    if row is None:
        raise SystemExit(f"no rule #{rule_id}")
    print(f"#{row.id} {row.name} [{row.status}]")
    print(f"source: {row.source or '-'}")
    print(f"notes: {row.notes or '-'}")
    print(f"registered {stamp(row.registered_epoch)} UTC | hash {row.spec_hash}")
    print(json.dumps(json.loads(row.spec), indent=2))
    if row.status == "concluded":
        print(verdict_line(row, 0.05 / max(total, 1)))


async def cmd_run(ids):
    async with SessionLocal() as db:
        total = (await db.execute(select(func.count(Hypothesis.id)))).scalar_one()
        query = select(Hypothesis).order_by(Hypothesis.id)
        if ids:
            query = query.where(Hypothesis.id.in_(ids))
        rows = (await db.execute(query)).scalars().all()
        alpha = 0.05 / max(total, 1)
        if not rows:
            print("no rules to run")
        now = time.time()
        for row in rows:
            if row.status == "concluded":
                print(verdict_line(row, alpha))
                continue
            spec = json.loads(row.spec)
            data = {}
            for symbol in spec["symbols"]:
                window = await load_window(db, symbol, row.registered_epoch - LOOKBACK_SECONDS)
                if window is not None:
                    data[symbol] = window
            ep, win = forward_trades(spec, data, row.registered_epoch)
            count = len(ep)
            if count < row.target_trades:
                cover = []
                for symbol, (e, _, _) in data.items():
                    if len(e) < 20:
                        continue
                    after = int((e > row.registered_epoch).sum())
                    cover.append(f"{symbol} {after * mode_interval(e) / 3600:.1f}h")
                elapsed = (now - row.registered_epoch) / 3600
                print(
                    f"#{row.id} {row.name}: {count}/{row.target_trades} trades, no verdict until the target is reached | "
                    f"ticks since registration: {', '.join(cover) or 'none'} of {elapsed:.1f}h elapsed"
                )
                continue
            first = win[: row.target_trades]
            wins = int(first.sum())
            be = breakeven(spec["contract"], spec["margin"])
            row.trades = int(row.target_trades)
            row.wins = wins
            row.breakeven = be
            row.p_value = binom_p(wins, row.target_trades, be)
            row.status = "concluded"
            row.concluded_epoch = int(ep[row.target_trades - 1])
            await db.commit()
            print(verdict_line(row, alpha))


async def dispatch(args):
    try:
        if args.command == "init":
            await cmd_init()
        elif args.command == "add":
            await cmd_add(args.path)
        elif args.command == "list":
            await cmd_list()
        elif args.command == "show":
            await cmd_show(args.id)
        else:
            await cmd_run(args.ids)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    add = sub.add_parser("add")
    add.add_argument("path")
    sub.add_parser("list")
    show = sub.add_parser("show")
    show.add_argument("id", type=int)
    run = sub.add_parser("run")
    run.add_argument("ids", nargs="*", type=int)
    asyncio.run(dispatch(parser.parse_args()))


if __name__ == "__main__":
    main()