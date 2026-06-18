"""Live feed simulator — streams fresh readings to /api/ingest so the
dashboard shows live, online nodes. Handy for demos and for exercising the
WebSocket path without the physical hardware.

    python simulate.py                # all seeded nodes, 1 reading / 3s
    python simulate.py --interval 1   # faster
    python simulate.py --escalate 3   # drive node 3 toward CRITICAL

Stop with Ctrl+C.
"""
import argparse
import json
import math
import random
import time
import urllib.request

BASE = "http://127.0.0.1:8000"

state = {}  # node_id -> dict of last values


def level_for(tilt_dev, soil, vib):
    if tilt_dev >= 6 or soil >= 80 or vib >= 6:
        return 3
    if tilt_dev >= 3 or soil >= 60 or vib >= 3:
        return 2
    if tilt_dev >= 1 or soil >= 40 or vib >= 1:
        return 1
    return 0


def post(payload):
    req = urllib.request.Request(
        f"{BASE}/api/ingest", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=4) as r:
        return json.load(r)


def get_nodes():
    with urllib.request.urlopen(f"{BASE}/api/nodes", timeout=4) as r:
        return [n["id"] for n in json.load(r)]


def step(node_id, t, escalate):
    s = state.setdefault(node_id, {
        "tilt": random.uniform(0.2, 0.7), "soil": random.uniform(25, 45),
        "seq": 0, "prev_tilt": 0.0, "prev_soil": 0.0,
    })
    drift = 0.04 if escalate else 0.0
    s["prev_tilt"], s["prev_soil"] = s["tilt"], s["soil"]
    s["tilt"] = max(0.0, s["tilt"] + math.sin(t / 6.0) * 0.012 + drift + random.uniform(-0.01, 0.012))
    s["soil"] = min(100.0, max(0.0, s["soil"] + (0.5 if escalate else 0.0) + random.uniform(-0.4, 0.5)))
    # Convert per-step deltas to a realistic per-minute rate.
    tilt_rate = max(0.0, abs(s["tilt"] - s["prev_tilt"]) * 6.0)
    soil_rate = (s["soil"] - s["prev_soil"]) * 6.0
    vib = max(0, int(random.gauss(2 if escalate else 0.3, 1.0)))
    lvl = level_for(s["tilt"], s["soil"], vib)
    ttc = round((6 - s["tilt"]) / tilt_rate, 1) if tilt_rate > 0.02 and s["tilt"] < 6 else -1.0
    s["seq"] += 1
    return {
        "id": node_id, "seq": s["seq"],
        "tiltDev": round(s["tilt"], 3), "tiltRate": round(tilt_rate, 3),
        "soil": round(s["soil"], 2), "soilRate": round(soil_rate, 3),
        "vib": vib, "ttc": ttc, "lvl": lvl,
        "rssi": round(random.uniform(-105, -72), 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--escalate", type=int, default=None,
                    help="node id to drive toward CRITICAL")
    args = ap.parse_args()

    nodes = get_nodes()
    print(f"Simulating nodes {nodes} every {args.interval}s (Ctrl+C to stop)")
    t = 0
    while True:
        for nid in nodes:
            payload = step(nid, t, escalate=(nid == args.escalate))
            try:
                r = post(payload)
                print(f"node {nid}: lvl={payload['lvl']} risk={r['risk']:.0f} "
                      f"anom={r['anomaly']:.2f}")
            except Exception as e:
                print(f"node {nid}: POST failed — {e}")
        t += 1
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
