from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.matching import evaluate_room, recommend


def profile(gender: str = "female") -> SimpleNamespace:
    return SimpleNamespace(
        age=24,
        gender=gender,
        occupation="Student",
        location="Vellore",
        budget_min=5000,
        budget_max=10000,
        sleep_schedule="early_bird",
        smoking="non_smoker",
        drinking="non_drinker",
        cleanliness=4,
        noise_level=2,
        guests_preference="sometimes",
        food_preference="vegetarian",
        pets="no_pets",
        study_habit="quiet",
        interests="Reading|Cooking",
        gender_preference="any",
        room_type_preference="shared",
    )


def room(
    room_id: int,
    *,
    rent: int = 6000,
    capacity: int = 2,
    gender_restriction: str = "any",
    memberships: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=room_id,
        name=f"Room {room_id}",
        location="Vellore",
        room_type="shared_room",
        monthly_rent=rent,
        capacity=capacity,
        gender_restriction=gender_restriction,
        active=True,
        memberships=memberships or [],
    )


class FakeMatcher:
    def __init__(self) -> None:
        self.calls = 0

    def score_pair(self, _candidate, _occupant) -> dict[str, float]:
        self.calls += 1
        return {
            "random_forest": 70.0,
            "kmeans": 80.0,
            "cosine": 90.0,
            "ensemble": 78.0,
        }


class MatchingTests(unittest.TestCase):
    def test_empty_room_has_no_fabricated_score(self) -> None:
        matcher = FakeMatcher()
        result = evaluate_room(matcher, vars(profile()), room(1), None)
        self.assertEqual(result["status"], "available")
        self.assertIsNone(result["ensemble_score"])
        self.assertFalse(result["scored"])
        self.assertEqual(matcher.calls, 0)

    def test_current_occupants_are_scored(self) -> None:
        occupant = SimpleNamespace(
            user_id=9,
            user=SimpleNamespace(email="roommate@example.com", profile=profile("male")),
            profile=profile("male"),
        )
        matcher = FakeMatcher()
        result = evaluate_room(matcher, vars(profile()), room(1, memberships=[occupant]), None)
        self.assertEqual(result["ensemble_score"], 78.0)
        self.assertEqual(matcher.calls, 1)

    def test_hard_constraints_exclude_room(self) -> None:
        result = evaluate_room(
            FakeMatcher(),
            vars(profile()),
            room(1, rent=12000, gender_restriction="male"),
            None,
        )
        self.assertEqual(result["status"], "excluded")
        self.assertIn("Rent exceeds the maximum budget", result["reasons"])
        self.assertIn("Room gender restriction does not match", result["reasons"])

    def test_room_type_filter_uses_form_aliases(self) -> None:
        candidate = vars(profile())
        candidate["required_room_type"] = "shared"
        result = evaluate_room(FakeMatcher(), candidate, room(1), None)
        self.assertEqual(result["status"], "available")

    def test_location_and_budget_boundaries_are_normalized(self) -> None:
        candidate = vars(profile())
        candidate["location"] = "  CHENNAI "
        candidate["budget_min"] = 6000
        candidate["budget_max"] = 6000
        chennai_room = room(1, rent=6000)
        chennai_room.location = " chEnnai "
        result = evaluate_room(FakeMatcher(), candidate, chennai_room, None)
        self.assertEqual(result["status"], "available")

    def test_different_location_is_excluded(self) -> None:
        candidate = vars(profile())
        candidate["location"] = "Chennai"
        other = room(1)
        other.location = "Kathmandu"
        result = evaluate_room(FakeMatcher(), candidate, other, None)
        self.assertIn("Room is outside the preferred location", result["reasons"])

    def test_expand_search_groups_alternative_locations(self) -> None:
        candidate = vars(profile())
        candidate["location"] = "Chennai"
        alternative = room(1)
        alternative.location = "Kanchipuram"
        result = recommend(FakeMatcher(), candidate, [alternative], None, expand_search=True)
        self.assertEqual(result["rooms"][0]["location_group"], "Alternative location")

    def test_recommendations_are_paged_without_duplicates(self) -> None:
        candidate = vars(profile())
        rooms = [room(index) for index in range(1, 4)]
        first = recommend(FakeMatcher(), candidate, rooms, None, page=1, page_size=2)
        second = recommend(FakeMatcher(), candidate, rooms, None, page=2, page_size=2)
        self.assertEqual([item["room_id"] for item in first["rooms"]], [1, 2])
        self.assertEqual([item["room_id"] for item in second["rooms"]], [3])

    def test_recommendations_exclude_joined_and_ineligible_rooms(self) -> None:
        user = SimpleNamespace(id=7)
        joined = SimpleNamespace(
            user_id=7,
            user=SimpleNamespace(email="me@example.com", profile=profile()),
            profile=profile(),
        )
        eligible = room(
            1,
            memberships=[
                SimpleNamespace(
                    user_id=9,
                    user=SimpleNamespace(email="roommate@example.com", profile=profile()),
                    profile=profile(),
                )
            ],
        )
        result = recommend(FakeMatcher(), vars(profile()), [room(2, memberships=[joined]), eligible], user)
        self.assertEqual([entry["room_id"] for entry in result["rooms"]], [1])

    def test_room_type_preference_is_soft_not_hard_constraint(self) -> None:
        candidate = vars(profile())
        candidate["room_type_preference"] = "single"  # Soft preference
        # room is shared_room; since candidate has no required_room_type, room should NOT be excluded
        shared = room(1)
        result = evaluate_room(FakeMatcher(), candidate, shared, None)
        self.assertNotEqual(result["status"], "excluded")
        self.assertEqual(result["status"], "available")

    def test_occupant_without_profile_does_not_exclude_room(self) -> None:
        occupant_no_profile = SimpleNamespace(
            user_id=12,
            user=SimpleNamespace(email="newbie@example.com", profile=None),
            profile=None,
        )
        r = room(1, memberships=[occupant_no_profile])
        result = evaluate_room(FakeMatcher(), vars(profile()), r, None)
        self.assertNotEqual(result["status"], "excluded")
        self.assertIn("not completed lifestyle profiles", result["compatibility_note"].lower())

    def test_privacy_occupant_emails_are_not_exposed(self) -> None:
        occupant = SimpleNamespace(
            user_id=9,
            user=SimpleNamespace(email="secret_resident@example.com", profile=profile()),
            profile=profile(),
        )
        r = room(1, memberships=[occupant])
        result = evaluate_room(FakeMatcher(), vars(profile()), r, None)
        for occ in result["occupants"]:
            self.assertNotIn("email", occ)
            self.assertIn("occupant_id", occ)

    def test_recommend_separates_occupied_and_empty_rooms(self) -> None:
        occupant = SimpleNamespace(
            user_id=9,
            user=SimpleNamespace(email="roommate@example.com", profile=profile()),
            profile=profile(),
        )
        occupied = room(1, memberships=[occupant])
        empty = room(2, memberships=[])
        result = recommend(FakeMatcher(), vars(profile()), [occupied, empty], None)
        self.assertIn("occupied_rooms", result)
        self.assertIn("empty_rooms", result)
        self.assertEqual(len(result["occupied_rooms"]), 1)
        self.assertEqual(len(result["empty_rooms"]), 1)
        self.assertEqual(result["occupied_rooms"][0]["room_id"], 1)
        self.assertEqual(result["empty_rooms"][0]["room_id"], 2)
        self.assertIsNone(result["empty_rooms"][0]["ensemble_score"])

    def test_strict_max_rent_filter(self) -> None:
        candidate = vars(profile())
        candidate["strict_max_rent"] = 5500
        r = room(1, rent=6000)
        result = evaluate_room(FakeMatcher(), candidate, r, None)
        self.assertEqual(result["status"], "excluded")
        self.assertIn("Rent exceeds the strict maximum", result["reasons"])


if __name__ == "__main__":
    unittest.main()
