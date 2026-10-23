"""Inference-only helpers for the saved roommate matching artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

try:
    from .train_and_save import CATEGORICAL_NOMINAL, NUMERIC, make_pair_features
except ImportError:
    from train_and_save import CATEGORICAL_NOMINAL, NUMERIC, make_pair_features

try:
    from .config import ENSEMBLE_WEIGHTS
except ImportError:
    try:
        from ml.config import ENSEMBLE_WEIGHTS
    except ImportError:
        from config import ENSEMBLE_WEIGHTS


class SavedMatcher:
    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        try:
            self.random_forest = joblib.load(artifact_dir / "random_forest.joblib")
            self.kmeans = joblib.load(artifact_dir / "kmeans.joblib")
            self.preprocessing = joblib.load(artifact_dir / "preprocessing.joblib")
            self.metadata = json.loads((artifact_dir / "metadata.json").read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Missing ML artifact {exc.filename}. Run `python ml/train_and_save.py` first."
            ) from exc

    def vectorize(self, person: dict[str, Any]) -> np.ndarray:
        scaler = self.preprocessing["scaler"]
        mlb = self.preprocessing["mlb"]
        feature_columns = self.preprocessing["feature_columns"]
        numeric = pd.DataFrame([{column: person[column] for column in NUMERIC}])
        numeric_values = scaler.transform(numeric)[0]
        numeric_series = pd.Series(numeric_values, index=NUMERIC)
        onehot_columns = [
            column for column in feature_columns
            if any(column.startswith(prefix + "_") for prefix in CATEGORICAL_NOMINAL)
        ]
        onehot = pd.get_dummies(
            pd.DataFrame([{column: person[column] for column in CATEGORICAL_NOMINAL}]),
            prefix=CATEGORICAL_NOMINAL,
        ).reindex(columns=onehot_columns, fill_value=0).iloc[0]
        interests = [item for item in str(person.get("interests", "")).split("|") if item]
        interest_series = pd.Series(
            mlb.transform([interests])[0],
            index=[f"interest_{value}" for value in mlb.classes_],
        )
        return pd.concat([numeric_series, onehot, interest_series]).reindex(
            feature_columns, fill_value=0
        ).to_numpy(dtype=float)

    def score_pair(self, person_a: dict[str, Any], person_b: dict[str, Any]) -> dict[str, float]:
        vec_a = self.vectorize(person_a)
        vec_b = self.vectorize(person_b)
        cluster_a = int(self.kmeans.predict(vec_a.reshape(1, -1))[0])
        cluster_b = int(self.kmeans.predict(vec_b.reshape(1, -1))[0])
        if cluster_a == cluster_b:
            distance = np.linalg.norm(vec_a - vec_b)
            max_distance = self.preprocessing["max_feature_distance"] or 1.0
            kmeans_score = 100 * (1 - min(distance / max_distance, 1.0))
        else:
            distance = np.linalg.norm(
                self.kmeans.cluster_centers_[cluster_a] - self.kmeans.cluster_centers_[cluster_b]
            )
            max_distance = self.preprocessing["max_centroid_distance"] or 1.0
            kmeans_score = 70 * (1 - min(distance / max_distance, 1.0))
        similarity = float(cosine_similarity(vec_a.reshape(1, -1), vec_b.reshape(1, -1))[0, 0])
        cosine_score = 100 * max(0.0, similarity) if np.isfinite(similarity) else 0.0
        rf_score = float(self.random_forest.predict([
            make_pair_features(vec_a, vec_b)
        ])[0])
        scores = {
            "random_forest": float(np.clip(rf_score, 0, 100)),
            "kmeans": float(np.clip(kmeans_score, 0, 100)),
            "cosine": float(np.clip(cosine_score, 0, 100)),
        }
        scores["ensemble"] = sum(scores[key] * weight for key, weight in ENSEMBLE_WEIGHTS.items())
        if not all(np.isfinite(value) for value in scores.values()):
            raise ValueError("Inference produced a non-finite score.")
        return {key: round(value, 2) for key, value in scores.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, default=Path(__file__).parent / "artifacts")
    parser.add_argument("--profile-a", type=Path, required=True)
    parser.add_argument("--profile-b", type=Path, required=True)
    args = parser.parse_args()
    matcher = SavedMatcher(args.artifact_dir)
    profile_a = json.loads(args.profile_a.read_text(encoding="utf-8"))
    profile_b = json.loads(args.profile_b.read_text(encoding="utf-8"))
    print(json.dumps(matcher.score_pair(profile_a, profile_b), indent=2))


if __name__ == "__main__":
    main()
