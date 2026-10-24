import asyncio
import json

import websockets

URL = "wss://api.derivws.com/trading/v1/options/ws/public"


async def call(ws, payload, req_id):
    await ws.send(json.dumps({**payload, "req_id": req_id}))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
        if msg.get("req_id") == req_id:
            return msg


async def main():
    async with websockets.connect(URL, ping_interval=20) as ws:
        reply = await call(ws, {"active_symbols": "brief"}, 1)
        print("active_symbols reply keys:", sorted(reply.keys()))
        if reply.get("error"):
            print("error:", reply["error"])
            return
        symbols = reply.get("active_symbols", [])
        print("symbol count:", len(symbols))
        print("markets:", sorted({str(s.get("market")) for s in symbols}))
        synthetic = [s for s in symbols if "synthetic" in str(s.get("market", ""))]
        print("synthetic count:", len(synthetic))
        if not synthetic:
            print("first symbol raw:", json.dumps(symbols[:1], indent=2))
            return
        print("sample symbol:", json.dumps(synthetic[0], indent=2))
        names = [s.get("underlying_symbol") for s in synthetic]
        print("synthetic symbols:", names)
        print("submarkets:", sorted({str(s.get("submarket")) for s in synthetic}))
        pick = "R_100" if "R_100" in names else names[0]
        print("probing:", pick)

        history = await call(
            ws, {"ticks_history": pick, "count": 5, "end": "latest", "style": "ticks"}, 2
        )
        print("history keys:", sorted(history.keys()))
        print(json.dumps(history, indent=2)[:900])

        contracts = await call(ws, {"contracts_for": pick}, 3)
        print("contracts_for keys:", sorted(contracts.keys()))
        if contracts.get("error"):
            print("contracts_for error:", contracts["error"])
        else:
            available = (contracts.get("contracts_for") or {}).get("available", [])
            print("contract types:", sorted({str(c.get("contract_type")) for c in available}))

        await ws.send(json.dumps({"ticks": pick, "subscribe": 1, "req_id": 4}))
        seen = 0
        while seen < 3:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            if "tick" in msg or msg.get("error"):
                print("tick message:", json.dumps(msg))
                seen += 1


asyncio.run(main())