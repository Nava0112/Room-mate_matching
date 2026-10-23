from __future__ import annotations

from typing import Any


def _opts(pairs: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"value": value, "label": label} for value, label in pairs]


GENDER = _opts([("female", "Female"), ("male", "Male"), ("non_binary", "Non-binary"), ("other", "Other")])
SLEEP = _opts([("early_bird", "Early bird"), ("night_owl", "Night owl"), ("flexible", "Flexible")])
SMOKING = _opts([("non_smoker", "Non-smoker"), ("occasional", "Occasional"), ("regular", "Regular")])
DRINKING = _opts([("non_drinker", "Non-drinker"), ("social", "Socially"), ("regular", "Regular")])
GUESTS = _opts([("never", "Never"), ("sometimes", "Sometimes"), ("often", "Often")])
FOOD = _opts([
    ("vegetarian", "Vegetarian"),
    ("vegan", "Vegan"),
    ("non_vegetarian", "Non-vegetarian"),
    ("any", "No preference"),
])
PETS = _opts([("no_pets", "No pets"), ("okay_with_pets", "Okay with pets"), ("has_pets", "Has pets")])
STUDY = _opts([
    ("quiet", "Quiet study"),
    ("music", "Studies with music"),
    ("group_study", "Group study"),
    ("flexible", "Flexible"),
])
GENDER_PREF = _opts([("any", "Any"), ("female", "Female"), ("male", "Male"), ("non_binary", "Non-binary")])
ROOM_TYPE = _opts([
    ("any", "Any"),
    ("single", "Single"),
    ("shared", "Shared"),
    ("studio", "Studio"),
    ("apartment", "Apartment"),
])
REQUIRED_ROOM_TYPE = _opts([
    ("", "Any"),
    ("single", "Single"),
    ("shared", "Shared"),
    ("studio", "Studio"),
    ("apartment", "Apartment"),
])

PROFILE_GROUPS: list[tuple[str, list[dict[str, Any]]]] = [
    (
        "Basics",
        [
            {"key": "age", "label": "Age", "type": "number", "min": 18, "max": 100, "step": 1, "default": 23},
            {"key": "gender", "label": "Gender", "type": "select", "options": GENDER, "default": "female"},
            {"key": "occupation", "label": "Occupation", "type": "text", "default": "Student"},
            {"key": "location", "label": "Preferred location", "type": "text", "default": "Kathmandu"},
        ],
    ),
    (
        "Budget",
        [
            {"key": "budget_min", "label": "Minimum monthly budget", "type": "number", "min": 0, "step": 500, "default": 10000},
            {"key": "budget_max", "label": "Maximum monthly budget", "type": "number", "min": 0, "step": 500, "default": 14000},
        ],
    ),
    (
        "Lifestyle",
        [
            {"key": "sleep_schedule", "label": "Sleep schedule", "type": "select", "options": SLEEP, "default": "early_bird"},
            {"key": "smoking", "label": "Smoking", "type": "select", "options": SMOKING, "default": "non_smoker"},
            {"key": "drinking", "label": "Drinking", "type": "select", "options": DRINKING, "default": "non_drinker"},
            {"key": "cleanliness", "label": "Cleanliness (1-5)", "type": "number", "min": 1, "max": 5, "step": 1, "default": 4},
            {"key": "noise_level", "label": "Noise tolerance (1-5)", "type": "number", "min": 1, "max": 5, "step": 1, "default": 2},
            {"key": "guests_preference", "label": "Guests", "type": "select", "options": GUESTS, "default": "sometimes"},
            {"key": "food_preference", "label": "Food", "type": "select", "options": FOOD, "default": "vegetarian"},
            {"key": "pets", "label": "Pets", "type": "select", "options": PETS, "default": "okay_with_pets"},
            {"key": "study_habit", "label": "Study habit", "type": "select", "options": STUDY, "default": "quiet"},
            {"key": "interests", "label": "Interests (separate with |)", "type": "text", "default": "Book Club|Cooking|Language"},
        ],
    ),
    (
        "Preferences",
        [
            {"key": "gender_preference", "label": "Preferred roommate gender", "type": "select", "options": GENDER_PREF, "default": "any"},
            {"key": "room_type_preference", "label": "Preferred room type", "type": "select", "options": ROOM_TYPE, "default": "any"},
        ],
    ),
]

FILTER_FIELDS: list[dict[str, Any]] = [
    {"key": "strict_max_rent", "label": "Strict maximum rent", "type": "number", "min": 0, "step": 500, "default": ""},
    {"key": "required_room_type", "label": "Required room type", "type": "select", "options": REQUIRED_ROOM_TYPE, "default": ""},
    {"key": "no_smoking", "label": "Only rooms with non-smoking occupants", "type": "checkbox", "default": False},
]


def profile_form_schema() -> dict[str, Any]:
    defaults = {field["key"]: field["default"] for _, fields in PROFILE_GROUPS for field in fields}
    defaults.update({field["key"]: field["default"] for field in FILTER_FIELDS})
    return {
        "profile_groups": [{"title": title, "fields": fields} for title, fields in PROFILE_GROUPS],
        "filter_fields": FILTER_FIELDS,
        "defaults": defaults,
    }