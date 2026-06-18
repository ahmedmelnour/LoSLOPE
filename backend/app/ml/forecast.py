"""Short-term forecast via linear regression.

Fits a line to the recent window of tiltDev and soil (vs. elapsed minutes) for
a node, projects 15/30/60 min ahead, and computes an ML-based
time-to-critical by extrapolating when either signal crosses its threshold.
"""
from datetime import datetime

import numpy as np
from dateutil import parser as dtparser

from ..config import CRITICAL_TILT_DEV, CRITICAL_SOIL

HORIZONS = [15, 30, 60]      # minutes
MIN_POINTS = 4


def _minutes_axis(readings: list[dict]) -> np.ndarray:
    """Elapsed minutes from the first reading in the window."""
    times = [dtparser.isoparse(r["ts"]) for r in readings]
    t0 = times[0]
    return np.array([(t - t0).total_seconds() / 60.0 for t in times])


def _fit_line(x: np.ndarray, y: np.ndarray):
    """Return (slope, intercept). Falls back to flat line if degenerate."""
    if len(x) < 2 or np.allclose(x, x[0]):
        return 0.0, float(y[-1]) if len(y) else 0.0
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def _time_to_threshold(slope: float, current: float, threshold: float):
    """Minutes until a rising signal reaches threshold; None if not rising."""
    if current >= threshold:
        return 0.0
    if slope <= 1e-9:
        return None
    return (threshold - current) / slope


def forecast_node(readings: list[dict]) -> dict:
    """Compute projections + ML time-to-critical for one node's window."""
    if len(readings) < MIN_POINTS:
        return {"ready": False}

    x = _minutes_axis(readings)
    now_t = x[-1]

    tilt = np.array([float(r.get("tilt_dev") or 0.0) for r in readings])
    soil = np.array([float(r.get("soil") or 0.0) for r in readings])

    tilt_slope, tilt_b = _fit_line(x, tilt)
    soil_slope, soil_b = _fit_line(x, soil)

    tilt_now = tilt_slope * now_t + tilt_b
    soil_now = soil_slope * now_t + soil_b

    projections = []
    for h in HORIZONS:
        # Clamp to physically meaningful bounds: tilt >= 0, soil in [0, 100].
        tilt_p = max(0.0, tilt_slope * (now_t + h) + tilt_b)
        soil_p = min(100.0, max(0.0, soil_slope * (now_t + h) + soil_b))
        projections.append({
            "horizon_min": h,
            "tilt_dev": round(tilt_p, 3),
            "soil": round(soil_p, 3),
        })

    t_tilt = _time_to_threshold(tilt_slope, tilt_now, CRITICAL_TILT_DEV)
    t_soil = _time_to_threshold(soil_slope, soil_now, CRITICAL_SOIL)
    candidates = [t for t in (t_tilt, t_soil) if t is not None]
    ml_ttc = round(min(candidates), 1) if candidates else -1.0

    return {
        "ready": True,
        "tilt_slope": round(tilt_slope, 4),
        "soil_slope": round(soil_slope, 4),
        "projections": projections,
        "ml_ttc": ml_ttc,
    }
