"""Central configuration for the LoSLOPE backend."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass  # dotenv optional; env vars still work without it


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# --- Paths -----------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "loslope.db"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

# Built frontend (served by FastAPI when present, e.g. behind a tunnel).
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"

# --- HiveMQ / MQTT ---------------------------------------------------------
# The backend subscribes to this broker and ingests every reading the base
# station publishes. Set these via environment variables (see .env.example)
# so credentials are never committed.
#   MQTT_HOST  e.g. abcd1234.s1.eu.hivemq.cloud
#   MQTT_PORT  8883 for TLS (HiveMQ Cloud default)
#   MQTT_USER / MQTT_PASS  the broker credentials you created in HiveMQ
#   MQTT_TOPIC topic the base station publishes to
MQTT_HOST = _env("MQTT_HOST")
MQTT_PORT = int(_env("MQTT_PORT", "8883"))
MQTT_USER = _env("MQTT_USER")
MQTT_PASS = _env("MQTT_PASS")
MQTT_TOPIC = _env("MQTT_TOPIC", "loslope/readings")
MQTT_TLS = _env("MQTT_TLS", "true").lower() != "false"
# MQTT is only started when a host is configured.
MQTT_ENABLED = bool(MQTT_HOST)

# --- Deployment ------------------------------------------------------------
# On a fresh cloud container the SQLite DB starts empty; seed demo nodes +
# readings so the dashboard is populated and the ML can train on day one.
AUTO_SEED = _env("AUTO_SEED", "true").lower() != "false"

# --- Behaviour -------------------------------------------------------------
# A node is considered offline if no reading has arrived within this window.
OFFLINE_SECONDS = 60

# Retrain the ML models automatically after this many newly ingested readings.
RETRAIN_EVERY_N = 25

# Alert level names, indexed by the integer `lvl` field.
LEVEL_NAMES = ["NORMAL", "WATCH", "WARNING", "CRITICAL"]

# Engineering thresholds used by the synthetic data generator and the
# ML-based time-to-critical forecast. These mirror the firmware thresholds.
CRITICAL_TILT_DEV = 6.0      # degrees
CRITICAL_SOIL = 80.0         # % saturation
