"""Configuration for the ensemble scoring weights.

These are starting assumptions, not statistically validated optimal weights.
See improvements.md Section 5.4 for details.

The weights must sum to 1.0. Adjusting them here changes the ensemble
score across the entire application without modifying model code.
"""

from __future__ import annotations

ENSEMBLE_WEIGHTS: dict[str, float] = {
    "random_forest": 0.50,
    "kmeans": 0.20,
    "cosine": 0.30,
}

_total = sum(ENSEMBLE_WEIGHTS.values())
if abs(_total - 1.0) > 1e-9:
    raise ValueError(f"Ensemble weights must sum to 1.0, got {_total}")
