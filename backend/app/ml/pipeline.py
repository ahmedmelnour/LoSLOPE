"""ML pipeline orchestrator.

Owns the three models, persists them to disk, retrains on demand or after every
N new readings, and enriches each incoming reading with anomaly + risk scores
and a short-term forecast.
"""
import threading
from collections import defaultdict

import joblib

from .. import db
from ..config import MODEL_DIR, RETRAIN_EVERY_N
from .anomaly import AnomalyModel
from .risk import RiskModel
from . import forecast

ANOMALY_PATH = MODEL_DIR / "anomaly.joblib"
RISK_PATH = MODEL_DIR / "risk.joblib"

FORECAST_WINDOW = 40       # readings used for the regression window


class MLPipeline:
    def __init__(self):
        self.anomaly = AnomalyModel()
        self.risk = RiskModel()
        self._lock = threading.Lock()
        self._since_retrain = 0
        self.last_trained: str | None = None
        self.n_train_samples = 0

    # --- persistence -------------------------------------------------------
    def load_or_train(self):
        loaded = False
        try:
            if ANOMALY_PATH.exists():
                self.anomaly = joblib.load(ANOMALY_PATH)
            if RISK_PATH.exists():
                self.risk = joblib.load(RISK_PATH)
                loaded = self.risk.is_ready
        except Exception as e:  # corrupt/incompatible pickle -> retrain
            print(f"[ml] could not load models ({e}); retraining")
            loaded = False
        if not loaded:
            self.retrain()

    def _save(self):
        joblib.dump(self.anomaly, ANOMALY_PATH)
        joblib.dump(self.risk, RISK_PATH)

    # --- training ----------------------------------------------------------
    def retrain(self) -> dict:
        """Retrain all models from stored readings (+ synthetic for risk)."""
        with self._lock:
            readings = db.all_readings_for_training()
            by_node: dict[int, list[dict]] = defaultdict(list)
            for r in readings:
                by_node[r["node_id"]].append(r)

            self.anomaly.fit(by_node)
            self.risk.fit(readings)
            self._since_retrain = 0
            self.last_trained = db.utcnow_iso()
            self.n_train_samples = len(readings)
            self._save()
        return self.status()

    # --- inference ---------------------------------------------------------
    def enrich(self, reading: dict) -> dict:
        """Compute anomaly + risk for a single reading (no DB access)."""
        anomaly = self.anomaly.score(reading["node_id"], reading)
        risk = self.risk.predict(reading)
        return {
            "anomaly": anomaly,
            "risk": risk["risk"],
            "risk_level": risk["level"],
            "risk_probabilities": risk["probabilities"],
        }

    def forecast_for_node(self, node_id: int) -> dict:
        window = db.get_recent_readings(node_id, FORECAST_WINDOW)
        return forecast.forecast_node(window)

    def note_new_reading(self) -> bool:
        """Increment the retrain counter; retrain + return True if due."""
        self._since_retrain += 1
        if self._since_retrain >= RETRAIN_EVERY_N:
            self.retrain()
            return True
        return False

    # --- status ------------------------------------------------------------
    def status(self) -> dict:
        return {
            "anomaly_ready": self.anomaly.is_ready,
            "risk_ready": self.risk.is_ready,
            "last_trained": self.last_trained,
            "train_samples": self.n_train_samples,
            "readings_since_retrain": self._since_retrain,
            "retrain_every_n": RETRAIN_EVERY_N,
        }


# Singleton used across the app.
pipeline = MLPipeline()
