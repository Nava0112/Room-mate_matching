"""Insert repeatable demonstration rooms and isolated demo occupants."""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import inspect, select, text

from app.database import Base, SessionLocal, engine
from app.models import Profile, Room, RoomMembership, User
from app.auth import hash_password


LOCATIONS = [
    "Chennai", "chennai", "CHENNAI", "Coimbatore", "Madurai", "Vellore",
    "Tiruchirappalli", "Salem", "Bengaluru", "Hyderabad", "Kathmandu",
]
ROOM_TYPES = ["shared_room", "private_room", "entire_place"]
GENDERS = ["any", "female", "male"]
AMENITIES = [
    "Wi-Fi, power backup, furnished",
    "Laundry, kitchen, security",
    "Parking, water supply, study desk",
    "AC, balcony, housekeeping",
]


def build_rooms() -> list[dict[str, object]]:
    rooms: list[dict[str, object]] = [
        {
            "name": "Sunrise Hostel - Room A",
            "location": "Kathmandu",
            "room_type": "shared_room",
            "monthly_rent": 9000,
            "capacity": 3,
        },
        {
            "name": "Sunrise Hostel - Room B",
            "location": "Kathmandu",
            "room_type": "shared_room",
            "monthly_rent": 11000,
            "capacity": 2,
        },
        {
            "name": "Green Valley PG - Room 1",
            "location": "Lalitpur",
            "room_type": "private_room",
            "monthly_rent": 15000,
            "capacity": 1,
        },
        {
            "name": "Green Valley PG - Room 2",
            "location": "Lalitpur",
            "room_type": "shared_room",
            "monthly_rent": 8000,
            "capacity": 4,
        },
        {
            "name": "Hilltop Apartments - Unit 3",
            "location": "Pokhara",
            "room_type": "entire_place",
            "monthly_rent": 20000,
            "capacity": 2,
        },
        {
            "name": "Riverside Rooms - R5",
            "location": "Bhaktapur",
            "room_type": "shared_room",
            "monthly_rent": 9500,
            "capacity": 3,
        },
        {
            "name": "City Center Flat - F2",
            "location": "Kathmandu",
            "room_type": "entire_place",
            "monthly_rent": 24000,
            "capacity": 3,
        },
        {
            "name": "Budget Rooms - B1",
            "location": "Chitwan",
            "room_type": "shared_room",
            "monthly_rent": 6500,
            "capacity": 4,
        },
        {
            "name": "Marina Residency - Room 101",
            "location": "Chennai",
            "room_type": "shared_room",
            "monthly_rent": 8500,
            "capacity": 3,
        },
        {
            "name": "Adyar Homes - Studio 2",
            "location": "Chennai",
            "room_type": "private_room",
            "monthly_rent": 16000,
            "capacity": 1,
        },
        {
            "name": "Gandhipuram Living - Room C",
            "location": "Coimbatore",
            "room_type": "shared_room",
            "monthly_rent": 7000,
            "capacity": 2,
        },
        {
            "name": "Madurai Junction Flat - F1",
            "location": "Madurai",
            "room_type": "entire_place",
            "monthly_rent": 14000,
            "capacity": 3,
        },
        {
            "name": "Rockfort Residency - Room 4",
            "location": "Tiruchirappalli",
            "room_type": "shared_room",
            "monthly_rent": 6500,
            "capacity": 3,
        },
        {
            "name": "Salem Central Rooms - S2",
            "location": "Salem",
            "room_type": "private_room",
            "monthly_rent": 9000,
            "capacity": 1,
        },
        {
            "name": "Vellore Campus Home - Room B",
            "location": "Vellore",
            "room_type": "shared_room",
            "monthly_rent": 6000,
            "capacity": 2,
        },
        {
            "name": "Tirunelveli Garden House - G1",
            "location": "Tirunelveli",
            "room_type": "entire_place",
            "monthly_rent": 12000,
            "capacity": 4,
        },
    ]
    for index in range(17, 51):
        location = LOCATIONS[(index - 17) % len(LOCATIONS)]
        room_type = ROOM_TYPES[(index - 17) % len(ROOM_TYPES)]
        capacity = 1 if room_type == "private_room" else 2 + ((index - 17) % 3)
        rooms.append(
            {
                "name": f"{location.title()} Demo Residence - Room {index}",
                "location": location,
                "room_type": room_type,
                "monthly_rent": 6000 + ((index * 137) % 15000),
                "capacity": capacity,
            }
        )
    for index, room in enumerate(rooms):
        room.update(
            gender_restriction=GENDERS[index % len(GENDERS)],
            description=f"Demo accommodation in {room['location']} with practical shared-living facilities.",
            amenities=AMENITIES[index % len(AMENITIES)],
            active=True,
        )
    return rooms


DUMMY_ROOMS = build_rooms()


def demo_profile(gender: str) -> dict[str, object]:
    return {
        "age": 22,
        "gender": gender,
        "occupation": "Student",
        "location": "Chennai",
        "budget_min": 5000,
        "budget_max": 14000,
        "sleep_schedule": "flexible",
        "smoking": "non_smoker",
        "drinking": "non_drinker",
        "cleanliness": 4,
        "noise_level": 2,
        "guests_preference": "sometimes",
        "food_preference": "vegetarian",
        "pets": "no_pets",
        "study_habit": "quiet",
        "interests": "Cooking|Music|Travel",
        "gender_preference": "any",
        "room_type_preference": "any",
    }


def seed_rooms() -> tuple[int, int]:
    Base.metadata.create_all(bind=engine)
    room_columns = {column["name"] for column in inspect(engine).get_columns("rooms")}
    with engine.begin() as connection:
        if "gender_restriction" not in room_columns:
            connection.execute(
                text(
                    "ALTER TABLE rooms ADD COLUMN gender_restriction "
                    "VARCHAR(20) NOT NULL DEFAULT 'any'"
                )
            )
        if "description" not in room_columns:
            connection.execute(
                text("ALTER TABLE rooms ADD COLUMN description TEXT NOT NULL DEFAULT ''")
            )
        if "amenities" not in room_columns:
            connection.execute(
                text("ALTER TABLE rooms ADD COLUMN amenities TEXT NOT NULL DEFAULT ''")
            )
    membership_columns = {column["name"] for column in inspect(engine).get_columns("room_memberships")}
    with engine.begin() as connection:
        if "joined_at" not in membership_columns:
            connection.execute(
                text("ALTER TABLE room_memberships ADD COLUMN joined_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP")
            )
    inserted_rooms = 0
    inserted_occupants = 0
    with SessionLocal.begin() as db:
        demo_users: list[User] = []
        for index in range(1, 25):
            email = f"demo-occupant-{index}@example.invalid"
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                gender = "female" if index % 2 else "male"
                user = User(
                    email=email,
                    password_hash=hash_password("DemoOnlyPass123!"),
                    is_admin=False,
                )
                db.add(user)
                db.flush()
                db.add(Profile(user_id=user.id, **demo_profile(gender)))
                inserted_occupants += 1
            demo_users.append(user)

        available_users = [
            user for user in demo_users
            if db.scalar(
                select(RoomMembership).where(RoomMembership.user_id == user.id)
            ) is None
        ]
        for index, room_data in enumerate(DUMMY_ROOMS):
            room = db.scalar(select(Room).where(Room.name == room_data["name"]))
            if room is None:
                room = Room(**room_data)
                db.add(room)
                db.flush()
                inserted_rooms += 1
            else:
                for key, value in room_data.items():
                    setattr(room, key, value)
            if index % 2 == 0 and not room.memberships and available_users:
                occupant = available_users.pop(0)
                db.add(RoomMembership(room_id=room.id, user_id=occupant.id))
                db.flush()
    return inserted_rooms, inserted_occupants


if __name__ == "__main__":
    rooms_inserted, occupants_inserted = seed_rooms()
    print(
        f"Inserted {rooms_inserted} rooms and {occupants_inserted} isolated demo occupants; "
        "existing records were preserved."
    )
