"""Anomaly detection via IsolationForest.

One unsupervised model per node (learns that node's "normal" pattern) plus a
global fallback for nodes that don't yet have enough history. Anomaly score is
mapped to 0..1, where higher means more anomalous.
"""
import math

import numpy as np
from sklearn.ensemble import IsolationForest

from .features import FEATURES, reading_to_vector

MIN_SAMPLES = 30          # need this many readings before a per-node model
GLOBAL_KEY = "_global"


class AnomalyModel:
    def __init__(self):
        # key -> fitted IsolationForest (key is node_id as str, or GLOBAL_KEY)
        self.models: dict[str, IsolationForest] = {}

    def fit(self, readings_by_node: dict[int, list[dict]]):
        """Fit a model per node with enough data, plus a global model."""
        all_vecs = []
        new_models: dict[str, IsolationForest] = {}
        for node_id, readings in readings_by_node.items():
            vecs = [reading_to_vector(r) for r in readings]
            all_vecs.extend(vecs)
            if len(vecs) >= MIN_SAMPLES:
                model = IsolationForest(
                    n_estimators=100, contamination="auto", random_state=42
                )
                model.fit(np.array(vecs))
                new_models[str(node_id)] = model

        if len(all_vecs) >= MIN_SAMPLES:
            g = IsolationForest(
                n_estimators=100, contamination="auto", random_state=42
            )
            g.fit(np.array(all_vecs))
            new_models[GLOBAL_KEY] = g

        self.models = new_models
        return self

    def _pick(self, node_id: int) -> IsolationForest | None:
        return self.models.get(str(node_id)) or self.models.get(GLOBAL_KEY)

    def score(self, node_id: int, reading: dict) -> float:
        """Return an anomaly score in [0, 1]; 0 if no model is available yet."""
        model = self._pick(node_id)
        if model is None:
            return 0.0
        vec = np.array([reading_to_vector(reading)])
        # decision_function: positive => inlier, negative => outlier.
        d = float(model.decision_function(vec)[0])
        # Logistic map so outliers (d<0) approach 1, inliers approach 0.
        return round(1.0 / (1.0 + math.exp(8.0 * d)), 4)

    @property
    def is_ready(self) -> bool:
        return bool(self.models)
