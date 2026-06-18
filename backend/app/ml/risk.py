"""Risk classification via RandomForest.

Trained on stored readings labelled by their `lvl` field, augmented with
synthetic samples (see synthetic.py) so the model is useful from day one.
Outputs a continuous risk score 0..100 derived from the class probabilities.
"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from . import synthetic
from .features import reading_to_vector

# All four levels must be represented for predict_proba columns to line up.
ALL_LEVELS = [0, 1, 2, 3]


class RiskModel:
    def __init__(self):
        self.clf: RandomForestClassifier | None = None
        self.classes_: list[int] = []

    def fit(self, readings: list[dict], n_synth_per_class: int = 400):
        """Fit on synthetic + real labelled readings."""
        Xs, ys = synthetic.generate(n_per_class=n_synth_per_class)
        X = list(Xs)
        y = list(ys)

        for r in readings:
            lvl = r.get("lvl")
            if lvl is None:
                continue
            X.append(reading_to_vector(r))
            y.append(int(lvl))

        X = np.array(X, dtype=float)
        y = np.array(y, dtype=int)

        clf = RandomForestClassifier(
            n_estimators=200, max_depth=12, random_state=42, n_jobs=-1
        )
        clf.fit(X, y)
        self.clf = clf
        self.classes_ = list(clf.classes_)
        return self

    def predict(self, reading: dict) -> dict:
        """Return risk score 0..100, predicted level, and per-level probs."""
        if self.clf is None:
            return {"risk": 0.0, "level": 0, "probabilities": {}}

        vec = np.array([reading_to_vector(reading)])
        proba = self.clf.predict_proba(vec)[0]
        probs = {lvl: 0.0 for lvl in ALL_LEVELS}
        for cls, p in zip(self.classes_, proba):
            probs[int(cls)] = float(p)

        # Expected (probability-weighted) level normalised to 0..100.
        expected = sum(lvl * probs[lvl] for lvl in ALL_LEVELS)
        risk = round(expected / 3.0 * 100.0, 1)
        level = int(max(probs, key=probs.get))
        return {
            "risk": risk,
            "level": level,
            "probabilities": {str(k): round(v, 4) for k, v in probs.items()},
        }

    @property
    def is_ready(self) -> bool:
        return self.clf is not None
