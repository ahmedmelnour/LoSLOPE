"""Seed the database with demo nodes (Malaysian slope coordinates near UTM)
and synthetic historical readings so the dashboard looks populated immediately.

Run from the backend/ directory:
    python seed.py
"""
import math
import random
from datetime import datetime, timedelta, timezone

from app import db
from app.config import LEVEL_NAMES

random.seed(7)

# Demo field nodes near UTM Skudai, Johor, Malaysia (hilly campus terrain).
DEMO_NODES = [
    {"id": 1, "name": "N1 - Library Slope",   "latitude": 1.5587, "longitude": 103.6370,
     "install_date": "2026-01-15", "notes": "Cut slope behind PSZ library."},
    {"id": 2, "name": "N2 - FKE Embankment",  "latitude": 1.5601, "longitude": 103.6452,
     "install_date": "2026-01-20", "notes": "Road embankment near FKE."},
    {"id": 3, "name": "N3 - Hostel Hillside", "latitude": 1.5648, "longitude": 103.6321,
     "install_date": "2026-02-02", "notes": "Residential college hillside."},
    {"id": 4, "name": "N4 - Sports Complex",  "latitude": 1.5559, "longitude": 103.6418,
     "install_date": "2026-02-10", "notes": "Drainage slope by the stadium."},
]


def level_for(tilt_dev, soil, vib):
    """Mirror firmware threshold logic to assign an alert level."""
    if tilt_dev >= 6 or soil >= 80 or vib >= 6:
        return 3
    if tilt_dev >= 3 or soil >= 60 or vib >= 3:
        return 2
    if tilt_dev >= 1 or soil >= 40 or vib >= 1:
        return 1
    return 0


def make_series(node_id, hours=6, every_sec=30, escalate=False):
    """Generate a realistic reading series for one node."""
    n = int(hours * 3600 / every_sec)
    start = datetime.now(timezone.utc) - timedelta(hours=hours)

    base_tilt = random.uniform(0.1, 0.6)
    base_soil = random.uniform(20, 45)
    rows = []
    for i in range(n):
        ts = start + timedelta(seconds=i * every_sec)
        frac = i / n
        # Gentle diurnal-ish wobble + optional escalation toward the end.
        wobble = math.sin(i / 25.0) * 0.15
        tilt_dev = max(0.0, base_tilt + wobble + (frac ** 2 * 7 if escalate else frac * 0.4))
        soil = min(100.0, base_soil + frac * (45 if escalate else 12)
                   + random.uniform(-1.5, 1.5))
        tilt_rate = max(0.0, (tilt_dev - rows[-1]["tilt_dev"]) / (every_sec / 60.0)) if rows else 0.0
        soil_rate = ((soil - rows[-1]["soil"]) / (every_sec / 60.0)) if rows else 0.0
        vib = max(0, int(random.gauss(0.3 + frac * (5 if escalate else 0.5), 0.8)))
        lvl = level_for(tilt_dev, soil, vib)
        # Crude linear TTC like the firmware would compute.
        ttc = round((6 - tilt_dev) / tilt_rate, 1) if tilt_rate > 0.01 and tilt_dev < 6 else -1.0
        rows.append({
            "node_id": node_id, "seq": i, "ts": ts.isoformat(),
            "tilt_dev": round(tilt_dev, 3), "tilt_rate": round(tilt_rate, 3),
            "soil": round(soil, 2), "soil_rate": round(soil_rate, 3),
            "vib": vib, "ttc": ttc, "lvl": lvl,
            "rssi": round(random.uniform(-110, -70), 1),
            "anomaly": None, "risk": None,
        })
    return rows


def main():
    db.init_db()
    # Insert nodes (replace existing demo nodes).
    for node in DEMO_NODES:
        if db.get_node(node["id"]):
            db.delete_node(node["id"])
        db.create_node(node)

    total = 0
    for node in DEMO_NODES:
        # Node 3 escalates into a CRITICAL scenario for a richer demo.
        escalate = node["id"] == 3
        rows = make_series(node["id"], hours=6, every_sec=30, escalate=escalate)
        for r in rows:
            db.insert_reading(r)
        total += len(rows)
        worst = max(r["lvl"] for r in rows)
        print(f"  node {node['id']}: {len(rows)} readings, worst={LEVEL_NAMES[worst]}")

    print(f"Seeded {len(DEMO_NODES)} nodes and {total} readings.")
    print("Now train the ML models:  python -c \"from app.ml import pipeline; pipeline.retrain()\"")


if __name__ == "__main__":
    main()
