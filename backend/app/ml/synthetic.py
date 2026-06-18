"""Synthetic training-sample generator.

Real landslide data is scarce, so we manufacture labelled samples spanning the
engineering threshold ranges for each alert level. This gives the risk
classifier sensible behaviour on day one, before any real readings exist.

Feature order matches features.FEATURES:
    [tilt_dev, tilt_rate, soil, soil_rate, vib]
"""
import numpy as np

# (low, high) ranges per feature, per alert level 0..3.
_RANGES = {
    0: {  # NORMAL
        "tilt_dev": (0.0, 1.0), "tilt_rate": (0.0, 0.10),
        "soil": (0.0, 40.0), "soil_rate": (0.0, 0.5), "vib": (0, 1),
    },
    1: {  # WATCH
        "tilt_dev": (1.0, 3.0), "tilt_rate": (0.10, 0.30),
        "soil": (40.0, 60.0), "soil_rate": (0.5, 1.0), "vib": (1, 3),
    },
    2: {  # WARNING
        "tilt_dev": (3.0, 6.0), "tilt_rate": (0.30, 0.80),
        "soil": (60.0, 80.0), "soil_rate": (1.0, 2.0), "vib": (3, 6),
    },
    3: {  # CRITICAL
        "tilt_dev": (6.0, 15.0), "tilt_rate": (0.80, 3.0),
        "soil": (80.0, 100.0), "soil_rate": (2.0, 5.0), "vib": (6, 15),
    },
}

_ORDER = ["tilt_dev", "tilt_rate", "soil", "soil_rate", "vib"]


def generate(n_per_class: int = 400, seed: int = 42):
    """Return (X, y) synthetic feature matrix and labels."""
    rng = np.random.default_rng(seed)
    X, y = [], []
    for lvl, ranges in _RANGES.items():
        for _ in range(n_per_class):
            row = []
            for feat in _ORDER:
                lo, hi = ranges[feat]
                val = rng.uniform(lo, hi)
                if feat == "vib":
                    val = round(val)
                row.append(val)
            X.append(row)
            y.append(lvl)
    return np.array(X, dtype=float), np.array(y, dtype=int)
