from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ml.predict import SavedMatcher

from .models import Profile, Room, User

STATUS_RECOMMENDED = "recommended"
STATUS_AVAILABLE = "available"
STATUS_EXCLUDED = "excluded"
STATUS_UNSCORED = "unscored"

STATUS_LABELS = {
    STATUS_RECOMMENDED: "Recommended",
    STATUS_AVAILABLE: "Available",
    STATUS_EXCLUDED: "Not eligible",
    STATUS_UNSCORED: "Not scored",
}

STATUS_RANK = {
    STATUS_RECOMMENDED: 0,
    STATUS_AVAILABLE: 1,
    STATUS_EXCLUDED: 2,
    STATUS_UNSCORED: 3,
}

BREAKDOWN_LABELS = {
    "random_forest": "Random Forest",
    "kmeans": "K-Means",
    "cosine": "Cosine similarity",
}

ROOM_TYPE_PREFERENCES = {
    "single": {"private_room"},
    "shared": {"shared_room"},
    "studio": {"private_room"},
    "apartment": {"entire_place"},
}

ALTERNATIVE_LOCATIONS = {
    "chennai": {"chengalpattu", "kanchipuram", "tiruvallur"},
    "coimbatore": {"tiruppur", "erode"},
    "madurai": {"dindigul", "virudhunagar"},
    "vellore": {"tiruvannamalai", "ranipet"},
}


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def normalize_location(value: Any) -> str:
    return normalize_text(value)


def normalize_number(value: Any, field_name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a whole number") from exc
    if number < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return number


def normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(candidate)
    for key in (
        "gender", "occupation", "sleep_schedule", "smoking", "drinking",
        "guests_preference", "food_preference", "pets", "study_habit",
        "gender_preference", "room_type_preference", "required_room_type",
    ):
        if key in normalized and normalized[key] is not None:
            normalized[key] = normalize_text(normalized[key])
    normalized["location"] = normalize_location(normalized.get("location"))
    for key in ("age", "budget_min", "budget_max", "cleanliness", "noise_level", "strict_max_rent"):
        if normalized.get(key) is not None:
            normalized[key] = normalize_number(normalized[key], key)
    normalized["no_smoking"] = bool(normalized.get("no_smoking", False))
    return normalized


def normalized_room(room: Room) -> dict[str, Any]:
    return {
        "location": normalize_location(room.location),
        "room_type": normalize_text(room.room_type),
        "gender_restriction": normalize_text(getattr(room, "gender_restriction", "any")) or "any",
        "monthly_rent": normalize_number(room.monthly_rent, "monthly_rent"),
        "capacity": normalize_number(room.capacity, "capacity"),
    }


def location_group(room_location: str, preferred_location: str, expanded: bool) -> str:
    if room_location == preferred_location:
        return "Preferred location"
    if expanded and room_location in ALTERNATIVE_LOCATIONS.get(preferred_location, set()):
        return "Alternative location"
    return "Other location"


def room_type_matches(room_type: str, preference: str) -> bool:
    allowed_types = ROOM_TYPE_PREFERENCES.get(preference)
    return preference in {"", "any"} or (
        room_type == preference if allowed_types is None else room_type in allowed_types
    )


def profile_dict(profile: Profile) -> dict[str, Any]:
    return {
        "age": profile.age, "gender": profile.gender, "occupation": profile.occupation,
        "location": profile.location, "budget_min": profile.budget_min, "budget_max": profile.budget_max,
        "sleep_schedule": profile.sleep_schedule, "smoking": profile.smoking, "drinking": profile.drinking,
        "cleanliness": profile.cleanliness, "noise_level": profile.noise_level,
        "guests_preference": profile.guests_preference, "food_preference": profile.food_preference,
        "pets": profile.pets, "study_habit": profile.study_habit, "interests": profile.interests,
        "gender_preference": profile.gender_preference, "room_type_preference": profile.room_type_preference,
    }


def load_matcher() -> SavedMatcher:
    configured_dir = os.getenv("ARTIFACT_DIR")
    artifact_dir = (
        Path(configured_dir)
        if configured_dir
        else Path(__file__).resolve().parents[2] / "ml" / "artifacts"
    )
    return SavedMatcher(artifact_dir)


def room_constraints(room: Room, occupant_count: int, request: dict[str, Any]) -> list[str]:
    request = normalize_candidate(request)
    fields = normalized_room(room)
    reasons: list[str] = []
    if not room.active:
        reasons.append("Room is inactive")
    if occupant_count >= fields["capacity"]:
        reasons.append("Room is full")
    gender_restriction = fields["gender_restriction"]
    candidate_gender = normalize_text(request.get("gender"))
    if (
        gender_restriction != "any"
        and candidate_gender
        and candidate_gender != gender_restriction
    ):
        reasons.append("Room gender restriction does not match")
    preferred_location = normalize_location(request.get("location"))
    allowed_locations = request.get("_allowed_locations") or {preferred_location}
    if preferred_location and fields["location"] not in allowed_locations:
        reasons.append("Room is outside the preferred location")
    budget_min = request.get("budget_min")
    if budget_min is not None and fields["monthly_rent"] < budget_min:
        reasons.append("Rent is below the minimum budget")
    budget_max = request.get("budget_max")
    if budget_max is not None and fields["monthly_rent"] > budget_max:
        reasons.append("Rent exceeds the maximum budget")
    if request.get("strict_max_rent") is not None and fields["monthly_rent"] > request["strict_max_rent"]:
        reasons.append("Rent exceeds the strict maximum")
    if request.get("required_room_type") and not room_type_matches(
        fields["room_type"], request["required_room_type"]
    ):
        reasons.append("Room type does not meet the required type")
    if request.get("no_smoking") and any(
        occupant.profile and occupant.profile.smoking != "non_smoker"
        for occupant in room.memberships
    ):
        reasons.append("An occupant does not meet the no-smoking requirement")
    return reasons


def base_room_payload(room: Room, user: User | None) -> dict[str, Any]:
    fields = normalized_room(room)
    occupant_count = len(room.memberships)
    available_slots = max(fields["capacity"] - occupant_count, 0)
    joined = user is not None and any(
        membership.user_id == user.id for membership in room.memberships
    )
    return {
        "room_id": room.id,
        "room_name": room.name,
        "active": room.active,
        "location": str(room.location).strip(),
        "room_type": str(room.room_type).strip(),
        "monthly_rent": fields["monthly_rent"],
        "capacity": fields["capacity"],
        "gender_restriction": fields["gender_restriction"],
        "description": getattr(room, "description", "") or "",
        "amenities": [
            item.strip() for item in str(getattr(room, "amenities", "") or "").split(",") if item.strip()
        ],
        "current_occupants": occupant_count,
        "available_slots": available_slots,
        "joined": joined,
        "can_join": bool(user) and room.active and available_slots > 0 and not joined,
        "occupants": [
            {
                "occupant_id": idx + 1,
                "has_profile": membership.user.profile is not None,
                "gender": (membership.user.profile.gender if membership.user.profile else "unspecified").title(),
                "occupation": (membership.user.profile.occupation if membership.user.profile else "Resident").title(),
            }
            for idx, membership in enumerate(room.memberships)
        ],
        "facts": [
            {"label": "Location", "value": room.location},
            {"label": "Room type", "value": fields["room_type"].replace("_", " ").title()},
            {"label": "Monthly rent", "value": f"\u20b9{fields['monthly_rent']:,}"},
            {"label": "Occupants", "value": f"{occupant_count} of {fields['capacity']}"},
            {"label": "Open slots", "value": str(available_slots)},
            {"label": "Gender restriction", "value": fields["gender_restriction"].title()},
        ],
    }


def _score_breakdown(scores: list[dict[str, float]]) -> list[dict[str, Any]]:
    keys = list(scores[0])
    return [
        {
            "key": key,
            "label": BREAKDOWN_LABELS.get(key, key.replace("_", " ").title()),
            "value": round(sum(score[key] for score in scores) / len(scores), 2),
        }
        for key in keys
    ]


def evaluate_room(
    matcher: SavedMatcher | None,
    candidate: dict[str, Any],
    room: Room,
    user: User | None,
) -> dict[str, Any]:
    occupant_count = len(room.memberships)
    try:
        reasons = room_constraints(room, occupant_count, candidate)
    except ValueError as exc:
        reasons = [f"Invalid room data: {exc}"]
    payload = base_room_payload(room, user)

    breakdown: list[dict[str, Any]] = []
    score: float | None = None
    compatibility_note: str | None = None

    if not reasons and room.memberships:
        occupants_with_profiles = [
            m for m in room.memberships
            if m.user and m.user.profile is not None
        ]
        if matcher is not None and occupants_with_profiles:
            scores = [
                matcher.score_pair(candidate, profile_dict(m.user.profile))
                for m in occupants_with_profiles
            ]
            breakdown = _score_breakdown(scores)
            score = next((item["value"] for item in breakdown if item["key"] == "ensemble"), None)
            if len(occupants_with_profiles) < len(room.memberships):
                compatibility_note = (
                    f"Scored with {len(occupants_with_profiles)} of {len(room.memberships)} occupants"
                )
        elif matcher is None:
            compatibility_note = "Compatibility model currently unavailable"
        else:
            compatibility_note = "Occupants have not completed lifestyle profiles yet"
    elif not reasons and not room.memberships:
        compatibility_note = "Empty room — compatibility not calculated"

    if reasons:
        status = STATUS_EXCLUDED
    elif score is not None:
        status = STATUS_RECOMMENDED
    else:
        status = STATUS_AVAILABLE

    return {
        **payload,
        "status": status,
        "status_label": STATUS_LABELS[status],
        "reasons": reasons,
        "ensemble_score": score,
        "score_breakdown": [item for item in breakdown if item["key"] != "ensemble"],
        "scored": score is not None,
        "compatibility_note": compatibility_note,
    }


def recommend(
    matcher: SavedMatcher | None,
    candidate: dict[str, Any],
    rooms: list[Room],
    user: User | None,
    *,
    expand_search: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    candidate = normalize_candidate(candidate)
    preferred_location = candidate["location"]
    allowed_locations = {preferred_location}
    if expand_search:
        allowed_locations.update(ALTERNATIVE_LOCATIONS.get(preferred_location, set()))
    candidate["_allowed_locations"] = allowed_locations
    entries = [
        {
            **evaluate_room(matcher, candidate, room, user),
            "location_group": location_group(
                normalized_room(room)["location"],
                preferred_location,
                expand_search,
            ),
        }
        for room in rooms
        if normalized_room(room)["location"] in allowed_locations
        if user is None
        or not any(membership.user_id == user.id for membership in room.memberships)
    ]
    entries = [entry for entry in entries if entry["status"] != STATUS_EXCLUDED]
    entries.sort(
        key=lambda item: (
            0 if item["current_occupants"] > 0 else 1,
            0 if item["location_group"] == "Preferred location" else 1,
            -(item["ensemble_score"] or 0.0),
            item["room_name"].lower(),
        )
    )
    page_size = max(1, min(page_size, 100))
    page = max(1, page)
    start = (page - 1) * page_size
    paged_entries = entries[start:start + page_size]
    summary = [
        {"label": "Recommended", "value": sum(1 for e in entries if e["status"] == STATUS_RECOMMENDED)},
        {"label": "Empty available", "value": sum(1 for e in entries if e["status"] == STATUS_AVAILABLE)},
        {"label": "Total eligible", "value": len(entries)},
    ]
    return {
        "summary": summary,
        "rooms": paged_entries,
        "occupied_rooms": [e for e in paged_entries if e["current_occupants"] > 0],
        "empty_rooms": [e for e in paged_entries if e["current_occupants"] == 0],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": len(entries),
            "has_more": start + page_size < len(entries),
        },
        "expand_search": expand_search,
        "preferred_location": preferred_location,
    }


def list_rooms(
    rooms: list[Room],
    user: User | None,
    candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entries = []
    for room in rooms:
        try:
            reasons = (
                room_constraints(room, len(room.memberships), candidate)
                if candidate is not None
                else []
            )
        except ValueError as exc:
            reasons = [f"Invalid room data: {exc}"]
        entry = {
            **base_room_payload(room, user),
            "status": STATUS_EXCLUDED if reasons else (
                STATUS_AVAILABLE if candidate is not None else STATUS_UNSCORED
            ),
            "status_label": STATUS_LABELS[
                STATUS_EXCLUDED if reasons else (
                    STATUS_AVAILABLE if candidate is not None else STATUS_UNSCORED
                )
            ],
            "reasons": reasons,
            "ensemble_score": None,
            "score_breakdown": [],
            "scored": False,
            "compatibility_note": None,
        }
        if reasons:
            entry["can_join"] = False
        entries.append(entry)
    summary = [
        {"label": "Rooms", "value": len(entries)},
        {"label": "Open slots", "value": sum(entry["available_slots"] for entry in entries)},
        {"label": "Full", "value": sum(1 for entry in entries if entry["available_slots"] == 0)},
    ]
    return {"summary": summary, "rooms": entries}