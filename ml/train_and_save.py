"""Train the notebook-compatible roommate matching models and save artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler

RANDOM_SEED = 42
DATA_URL = (
    "https://huggingface.co/datasets/cive202/Lifestyle_Preferences_Dataset/"
    "resolve/main/roommate_dataset.csv"
)
NUMERIC = ["age", "budget_min", "budget_max", "cleanliness", "noise_level"]
CATEGORICAL_NOMINAL = [
    "gender",
    "occupation",
    "location",
    "sleep_schedule",
    "smoking",
    "drinking",
    "guests_preference",
    "food_preference",
    "pets",
    "study_habit",
    "gender_preference",
    "room_type_preference",
]
REQUIRED_COLUMNS = ["user_id", *NUMERIC, *CATEGORICAL_NOMINAL, "interests"]


def generate_synthetic_fallback(n: int = 1200, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Generate the same schema used by the notebook when the download is unavailable."""
    rng = np.random.default_rng(seed)
    options = {
        "gender": (["male", "female", "non_binary", "prefer_not_to_say"], [0.45, 0.45, 0.05, 0.05]),
        "occupation": (["Student", "Intern", "Fresh Graduate", "Young Professional"], None),
        "location": (
            ["Kathmandu", "Lalitpur", "Bhaktapur", "Pokhara", "Chitwan", "Butwal",
             "Biratnagar", "Dharan", "Itahari", "Nepalgunj", "Birgunj", "Hetauda"],
            None,
        ),
        "sleep_schedule": (["early_bird", "night_owl", "flexible"], None),
        "smoking": (["non_smoker", "smoker", "occasional"], [0.75, 0.10, 0.15]),
        "drinking": (["non_drinker", "drinker", "social"], [0.40, 0.25, 0.35]),
        "guests_preference": (["rarely", "sometimes", "frequently"], None),
        "food_preference": (["vegetarian", "non_vegetarian", "vegan", "no_preference"], None),
        "pets": (["okay_with_pets", "not_okay_with_pets", "no_pets", "has_pets"], None),
        "study_habit": (["quiet", "group_study", "background_noise_ok", "rarely_studies_at_home"], None),
        "gender_preference": (["male", "female", "non_binary", "any"], None),
        "room_type_preference": (["any", "shared_room", "private_room", "entire_place"], None),
    }
    interest_pool = [
        "Hiking", "Photography", "Treks", "Music", "Gaming", "Cooking",
        "Language", "Book Club", "Travel", "Yoga", "Futsal", "Board Games",
    ]
    rows: list[dict[str, Any]] = []
    for i in range(n):
        budget_min = int(rng.integers(4000, 35000))
        rows.append({
            "user_id": 100000 + i,
            "age": int(rng.integers(18, 33)),
            "gender": rng.choice(options["gender"][0], p=options["gender"][1]),
            "occupation": rng.choice(options["occupation"][0]),
            "location": rng.choice(options["location"][0]),
            "budget_min": budget_min,
            "budget_max": budget_min + int(rng.integers(1000, 15000)),
            "sleep_schedule": rng.choice(options["sleep_schedule"][0]),
            "wake_time": f"{int(rng.integers(4, 13)):02d}:{int(rng.integers(0, 60)):02d}",
            "smoking": rng.choice(options["smoking"][0], p=options["smoking"][1]),
            "drinking": rng.choice(options["drinking"][0], p=options["drinking"][1]),
            "cleanliness": int(rng.integers(1, 6)),
            "noise_level": int(rng.integers(1, 6)),
            "guests_preference": rng.choice(options["guests_preference"][0]),
            "food_preference": rng.choice(options["food_preference"][0]),
            "pets": rng.choice(options["pets"][0]),
            "study_habit": rng.choice(options["study_habit"][0]),
            "interests": "|".join(rng.choice(interest_pool, size=int(rng.integers(1, 4)), replace=False)),
            "gender_preference": rng.choice(options["gender_preference"][0]),
            "room_type_preference": rng.choice(options["room_type_preference"][0]),
        })
    return pd.DataFrame(rows)


def load_dataset() -> tuple[pd.DataFrame, str]:
    try:
        data = pd.read_csv(DATA_URL)
        return data, "huggingface"
    except Exception as exc:
        print(f"Dataset download failed ({type(exc).__name__}); using the notebook fallback.")
        return generate_synthetic_fallback(), "synthetic_fallback"


def validate_dataset(data: pd.DataFrame) -> None:
    missing = sorted(set(REQUIRED_COLUMNS) - set(data.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")
    if data[REQUIRED_COLUMNS].isna().any().any():
        raise ValueError("Required dataset columns contain missing values.")


def build_feature_matrix(
    data: pd.DataFrame,
) -> tuple[pd.DataFrame, StandardScaler, MultiLabelBinarizer, list[str]]:
    scaler = StandardScaler()
    numeric_scaled = pd.DataFrame(scaler.fit_transform(data[NUMERIC]), columns=NUMERIC)
    onehot = pd.get_dummies(data[CATEGORICAL_NOMINAL], prefix=CATEGORICAL_NOMINAL)
    interest_lists = data["interests"].fillna("").apply(lambda value: [item for item in str(value).split("|") if item])
    mlb = MultiLabelBinarizer()
    interests_encoded = pd.DataFrame(
        mlb.fit_transform(interest_lists),
        columns=[f"interest_{value}" for value in mlb.classes_],
    )
    features = pd.concat([numeric_scaled, onehot, interests_encoded], axis=1)
    features.index = data["user_id"].to_numpy()
    return features, scaler, mlb, list(features.columns)


def rule_based_compatibility(row_a: pd.Series, row_b: pd.Series) -> float:
    score = 0.0
    weight_total = 0.0

    def add(weight: float, match: float) -> None:
        nonlocal score, weight_total
        score += weight * match
        weight_total += weight

    add(15, 1.0 if row_a["sleep_schedule"] == row_b["sleep_schedule"] else (
        0.5 if "flexible" in (row_a["sleep_schedule"], row_b["sleep_schedule"]) else 0.0
    ))
    add(15, 1 - abs(row_a["cleanliness"] - row_b["cleanliness"]) / 4)
    add(10, 1 - abs(row_a["noise_level"] - row_b["noise_level"]) / 4)
    add(12, 1.0 if row_a["smoking"] == row_b["smoking"] else (
        0.4 if "occasional" in (row_a["smoking"], row_b["smoking"]) else 0.0
    ))
    add(8, 1.0 if row_a["drinking"] == row_b["drinking"] else 0.3)
    add(8, 1.0 if row_a["guests_preference"] == row_b["guests_preference"] else 0.3)
    add(7, 1.0 if row_a["pets"] == row_b["pets"] else 0.3)
    add(7, 1.0 if row_a["study_habit"] == row_b["study_habit"] else 0.3)
    low = max(row_a["budget_min"], row_b["budget_min"])
    high = min(row_a["budget_max"], row_b["budget_max"])
    overlap = max(0, high - low)
    span = max(row_a["budget_max"] - row_a["budget_min"], row_b["budget_max"] - row_b["budget_min"], 1)
    add(10, min(1.0, overlap / span))
    interests_a = set(str(row_a["interests"]).split("|"))
    interests_b = set(str(row_b["interests"]).split("|"))
    union = interests_a | interests_b
    add(8, len(interests_a & interests_b) / len(union) if union else 0.0)

    def gender_ok(preference: str, gender: str) -> bool:
        return preference == "any" or preference == gender

    add(10, 1.0 if (
        gender_ok(row_a["gender_preference"], row_b["gender"])
        and gender_ok(row_b["gender_preference"], row_a["gender"])
    ) else 0.0)
    return round(100 * score / weight_total, 2)


def make_pair_features(vec_a: np.ndarray, vec_b: np.ndarray) -> np.ndarray:
    vec_a = np.asarray(vec_a, dtype=float)
    vec_b = np.asarray(vec_b, dtype=float)
    return np.concatenate([np.abs(vec_a - vec_b), vec_a * vec_b])


def train(output_dir: Path) -> dict[str, Any]:
    data, dataset_source = load_dataset()
    validate_dataset(data)
    features, scaler, mlb, feature_columns = build_feature_matrix(data)
    indexed = data.set_index("user_id")

    kmeans = KMeans(n_clusters=8, random_state=RANDOM_SEED, n_init=10)
    kmeans.fit(features.to_numpy())
    feature_range = features.to_numpy().max(axis=0) - features.to_numpy().min(axis=0)
    max_feature_distance = float(np.linalg.norm(feature_range))
    centroid_range = kmeans.cluster_centers_.max(axis=0) - kmeans.cluster_centers_.min(axis=0)
    max_centroid_distance = float(np.linalg.norm(centroid_range)) or 1.0

    rng = np.random.default_rng(RANDOM_SEED)
    ids = features.index.to_numpy()
    pair_count = min(8000, len(ids) * 15)
    idx_a = rng.integers(0, len(ids), pair_count)
    idx_b = rng.integers(0, len(ids), pair_count)
    keep = idx_a != idx_b
    ids_a, ids_b = ids[idx_a[keep]], ids[idx_b[keep]]
    X_pairs = np.array([make_pair_features(features.loc[a], features.loc[b]) for a, b in zip(ids_a, ids_b)])
    y_pairs = np.array([rule_based_compatibility(indexed.loc[a], indexed.loc[b]) for a, b in zip(ids_a, ids_b)])
    X_train, X_test, y_train, y_test = train_test_split(
        X_pairs, y_pairs, test_size=0.2, random_state=RANDOM_SEED
    )
    random_forest = RandomForestRegressor(
        n_estimators=200, max_depth=12, random_state=RANDOM_SEED, n_jobs=-1
    )
    random_forest.fit(X_train, y_train)
    predictions = random_forest.predict(X_test)
    metrics = {
        "validation_pairs": int(len(y_test)),
        "validation_mae": float(mean_absolute_error(y_test, predictions)),
        "validation_r2": float(r2_score(y_test, predictions)),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(random_forest, output_dir / "random_forest.joblib")
    joblib.dump(kmeans, output_dir / "kmeans.joblib")
    joblib.dump(
        {
            "scaler": scaler,
            "mlb": mlb,
            "feature_columns": feature_columns,
            "numeric_columns": NUMERIC,
            "categorical_columns": CATEGORICAL_NOMINAL,
            "max_feature_distance": max_feature_distance,
            "max_centroid_distance": max_centroid_distance,
        },
        output_dir / "preprocessing.joblib",
    )
    metadata = {
        "random_seed": RANDOM_SEED,
        "dataset_source": dataset_source,
        "dataset_url": DATA_URL,
        "rows": int(len(data)),
        "feature_count": len(feature_columns),
        "pair_feature_count": len(feature_columns) * 2,
        "n_clusters": 8,
        "metrics": metrics,
        "score_scale": "0-100",
        "methodology": (
            "RandomForest learns the notebook rule_based_compatibility labels; "
            "KMeans and cosine are unsupervised alternatives."
        ),
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Dataset: {dataset_source}, rows={len(data)}, features={len(feature_columns)}")
    print(f"Validation MAE: {metrics['validation_mae']:.4f}")
    print(f"Validation R2: {metrics['validation_r2']:.4f}")
    print(f"Artifacts saved to {output_dir.resolve()}")
    return {
        "data": data,
        "features": features,
        "scaler": scaler,
        "mlb": mlb,
        "kmeans": kmeans,
        "random_forest": random_forest,
        "max_feature_distance": max_feature_distance,
        "max_centroid_distance": max_centroid_distance,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "artifacts")
    args = parser.parse_args()
    state = train(args.output_dir)
    first_two = state["data"].iloc[:2]
    first_features = state["features"]
    score = float(state["random_forest"].predict([
        make_pair_features(first_features.iloc[0], first_features.iloc[1])
    ])[0])
    if not np.isfinite(score):
        raise RuntimeError("Post-save training prediction was not finite.")
    print(f"Post-save training prediction check: {score:.2f}/100")
    print("SUCCESS: training and artifact export completed.")


if __name__ == "__main__":
    main()
