"""LoSLOPE machine-learning module.

Three capabilities, all operating on stored readings:
  - anomaly  : per-node IsolationForest over the sensor feature vector
  - risk     : RandomForest risk classifier (real + synthetic training data)
  - forecast : short-term regression + ML time-to-critical
"""
from .pipeline import pipeline  # noqa: F401
