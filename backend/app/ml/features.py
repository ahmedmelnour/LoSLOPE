"""Shared feature definitions for the ML models."""

# The 5-dimensional sensor feature vector used by anomaly + risk models.
FEATURES = ["tilt_dev", "tilt_rate", "soil", "soil_rate", "vib"]


def reading_to_vector(r: dict) -> list[float]:
    """Extract the model feature vector from a reading row/dict.

    Accepts both DB column names (tilt_dev) and packet keys (tiltDev).
    """
    def g(snake: str, camel: str) -> float:
        v = r.get(snake)
        if v is None:
            v = r.get(camel)
        return float(v) if v is not None else 0.0

    return [
        g("tilt_dev", "tiltDev"),
        g("tilt_rate", "tiltRate"),
        g("soil", "soil"),
        g("soil_rate", "soilRate"),
        g("vib", "vib"),
    ]
