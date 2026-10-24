import asyncio
import json

import websockets

URL = "wss://api.derivws.com/trading/v1/options/ws/public"

CASES = [
    ("DIGITEVEN", 1, None),
    ("DIGITODD", 1, None),
    ("DIGITOVER", 1, "4"),
    ("DIGITUNDER", 1, "5"),
    ("CALL", 5, None),
    ("PUT", 5, None),
]


async def call(ws, payload, req_id):
    await ws.send(json.dumps({**payload, "req_id": req_id}))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
        if msg.get("req_id") == req_id:
            return msg


async def main():
    async with websockets.connect(URL, ping_interval=20) as ws:
        req = 0
        for kind, duration, barrier in CASES:
            reply = None
            for field in ("underlying_symbol", "symbol"):
                req += 1
                payload = {
                    "proposal": 1,
                    "amount": 10,
                    "basis": "stake",
                    "contract_type": kind,
                    "currency": "USD",
                    "duration": duration,
                    "duration_unit": "t",
                    field: "R_100",
                }
                if barrier is not None:
                    payload["barrier"] = barrier
                reply = await call(ws, payload, req)
                if not reply.get("error"):
                    break
            print(kind, barrier or "", json.dumps(reply)[:500])
            print()


asyncio.run(main())