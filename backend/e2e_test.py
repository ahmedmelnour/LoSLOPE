"""Quick end-to-end check: WS subscribe -> POST /api/ingest -> receive broadcast."""
import asyncio
import json
import urllib.request

import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws"


def post_ingest(payload):
    req = urllib.request.Request(
        f"{BASE}/api/ingest", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


async def main():
    payload = {"id": 3, "seq": 9999, "tiltDev": 7.2, "tiltRate": 1.4,
               "soil": 88.0, "soilRate": 3.1, "vib": 8, "ttc": 4.0, "lvl": 3, "rssi": -91}
    async with websockets.connect(WS) as ws:
        resp = post_ingest(payload)
        print("HTTP response:", json.dumps(resp, indent=2))
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(msg)
        print("WS broadcast type:", data["type"])
        print("WS broadcast node:", data["data"]["node_id"],
              "risk:", data["data"]["risk"], "anomaly:", data["data"]["anomaly"])

    # Also verify status + overview endpoints.
    with urllib.request.urlopen(f"{BASE}/api/nodes/3/status") as r:
        st = json.load(r)
    print("Node 3 online:", st["online"], "ml risk:", st["risk"]["risk"],
          "ml_ttc:", st["forecast"].get("ml_ttc"))


asyncio.run(main())
