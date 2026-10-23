from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import (
    create_session,
    current_user,
    destroy_session,
    hash_password,
    optional_user,
    token_from_header,
    verify_password,
)
from .database import Base, engine, get_db
from .form_schema import profile_form_schema
from .matching import (
    evaluate_room,
    list_rooms,
    load_matcher,
    profile_dict,
    recommend,
    room_constraints,
)
from .models import Profile, Room, RoomMembership, User
from .schemas import Credentials, FilterRequest, ProfileInput, RecommendationRequest, RoomInput

_matcher: Any = None
_matcher_error: str | None = None


def initialize_schema() -> None:
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    room_columns = {column["name"] for column in inspector.get_columns("rooms")}
    if "gender_restriction" not in room_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE rooms ADD COLUMN gender_restriction "
                    "VARCHAR(20) NOT NULL DEFAULT 'any'"
                )
            )
    room_columns = {column["name"] for column in inspect(engine).get_columns("rooms")}
    with engine.begin() as connection:
        if "description" not in room_columns:
            connection.execute(
                text("ALTER TABLE rooms ADD COLUMN description TEXT NOT NULL DEFAULT ''")
            )
        if "amenities" not in room_columns:
            connection.execute(
                text("ALTER TABLE rooms ADD COLUMN amenities TEXT NOT NULL DEFAULT ''")
            )
    membership_columns = {column["name"] for column in inspect(engine).get_columns("room_memberships")}
    if "joined_at" not in membership_columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE room_memberships ADD COLUMN joined_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP")
            )
    with engine.begin() as connection:
        try:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_room_memberships_user "
                    "ON room_memberships (user_id)"
                )
            )
        except IntegrityError as exc:
            raise RuntimeError(
                "Cannot enforce one room per user because duplicate room memberships "
                "already exist. Reconcile room_memberships.user_id before restarting."
            ) from exc


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _matcher, _matcher_error
    initialize_schema()
    try:
        _matcher = load_matcher()
        _matcher_error = None
    except FileNotFoundError as exc:
        _matcher = None
        _matcher_error = str(exc)
    yield


app = FastAPI(title="Roommate Matching API", version="1.1.0", lifespan=lifespan)

_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", os.getenv("CORS_ORIGIN", "http://localhost:5173")
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok" if _matcher is not None else "degraded",
        "models": "loaded" if _matcher is not None else "not_loaded",
        "detail": _matcher_error,
    }


@app.post("/auth/register")
def register(credentials: Credentials, db: Session = Depends(get_db)) -> dict[str, str]:
    if db.scalar(select(User).where(User.email == credentials.email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=credentials.email,
        password_hash=hash_password(credentials.password),
        is_admin=credentials.email == os.getenv("ADMIN_EMAIL"),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered") from exc
    db.refresh(user)
    return {"token": create_session(user.id)}


@app.post("/auth/login")
def login(credentials: Credentials, db: Session = Depends(get_db)) -> dict[str, str]:
    user = db.scalar(select(User).where(User.email == credentials.email))
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": create_session(user.id)}


@app.post("/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, str]:
    token = token_from_header(authorization)
    if token:
        destroy_session(token)
    return {"status": "signed_out"}


@app.get("/me")
def me(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    membership = db.scalar(
        select(RoomMembership).where(RoomMembership.user_id == user.id)
    )
    current_room = None
    if membership is not None:
        room = db.get(Room, membership.room_id)
        if room is not None:
            current_room = list_rooms([room], user)["rooms"][0]
    return {
        "email": user.email,
        "is_admin": user.is_admin,
        "has_profile": user.profile is not None,
        "current_room": current_room,
    }


@app.get("/profile/form")
def profile_form() -> dict[str, Any]:
    return profile_form_schema()


@app.get("/profile")
def get_profile(user: User = Depends(current_user)) -> dict:
    if user.profile is None:
        raise HTTPException(status_code=404, detail="Profile not created")
    return profile_dict(user.profile)


@app.put("/profile")
def save_profile(
    profile_input: ProfileInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    profile = user.profile or Profile(user_id=user.id)
    for key, value in profile_input.model_dump().items():
        setattr(profile, key, value)
    db.add(profile)
    db.commit()
    return {"status": "saved"}


@app.get("/rooms")
def rooms(
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    active_rooms = db.scalars(
        select(Room).order_by(Room.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    candidate = profile_dict(user.profile) if user and user.profile else None
    result = list_rooms(active_rooms, user, candidate)
    result["pagination"] = {
        "page": page,
        "page_size": page_size,
        "has_more": len(active_rooms) == page_size,
    }
    return result


@app.get("/rooms/{room_id}")
def get_room_details(
    room_id: int,
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    room = db.scalar(select(Room).where(Room.id == room_id))
    if room is None or not room.active:
        raise HTTPException(status_code=404, detail="Room not found")
    candidate = profile_dict(user.profile) if user and user.profile else None
    if candidate and _matcher is not None and len(room.memberships) > 0:
        return evaluate_room(_matcher, candidate, room, user)
    return list_rooms([room], user, candidate)["rooms"][0]


@app.post("/admin/rooms")
def add_room(
    room_input: RoomInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")
    room = Room(**room_input.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return list_rooms([room], user)["rooms"][0]


@app.post("/recommendations")
def recommendations(
    payload: RecommendationRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    expand_search: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    if user.profile is None:
        raise HTTPException(
            status_code=400,
            detail="Save your lifestyle profile before finding rooms",
        )
    rooms_to_score: list[Room] = []
    offset = 0
    batch_size = 100
    while True:
        batch = db.scalars(
            select(Room)
            .where(Room.active.is_(True))
            .order_by(Room.id)
            .offset(offset)
            .limit(batch_size)
        ).all()
        rooms_to_score.extend(batch)
        if len(batch) < batch_size:
            break
        offset += batch_size
    candidate = profile_dict(user.profile)
    submitted_filters = payload.model_dump()
    for key in ("strict_max_rent", "required_room_type", "no_smoking"):
        candidate[key] = submitted_filters.get(key)
    result = recommend(
        _matcher,
        candidate,
        rooms_to_score,
        user,
        expand_search=expand_search,
        page=page,
        page_size=page_size,
    )
    if _matcher is None:
        result["notice"] = _matcher_error or (
            "Compatibility scores are unavailable. Run python ml/train_and_save.py, "
            "then restart the API."
        )
    return result


@app.post("/rooms/{room_id}/join")
def join_room(
    room_id: int,
    payload: RecommendationRequest | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if user.profile is None:
        raise HTTPException(
            status_code=400,
            detail="Save your lifestyle profile before joining a room",
        )
    room = db.scalar(
        select(Room).where(Room.id == room_id).with_for_update()
    )
    if room is None or not room.active:
        raise HTTPException(status_code=404, detail="Room not found")
    if len(room.memberships) >= room.capacity:
        raise HTTPException(status_code=409, detail="Room is full")
    existing = db.scalar(
        select(RoomMembership).where(
            RoomMembership.room_id == room_id,
            RoomMembership.user_id == user.id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already a member")
    existing_room = db.scalar(
        select(RoomMembership)
        .where(RoomMembership.user_id == user.id)
        .with_for_update()
    )
    if existing_room:
        raise HTTPException(status_code=409, detail="You already belong to a room")
    candidate = profile_dict(user.profile)
    if payload is not None:
        submitted = payload.model_dump()
        for key in ("strict_max_rent", "required_room_type", "no_smoking"):
            candidate[key] = submitted.get(key)
    reasons = room_constraints(room, len(room.memberships), candidate)
    if reasons:
        raise HTTPException(
            status_code=409,
            detail=f"Room is not eligible: {'; '.join(reasons)}",
        )
    db.add(RoomMembership(room_id=room_id, user_id=user.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Room membership could not be created")
    return {"status": "joined"}


@app.post("/rooms/{room_id}/leave")
def leave_room(
    room_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    membership = db.scalar(
        select(RoomMembership).where(
            RoomMembership.room_id == room_id,
            RoomMembership.user_id == user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="You are not a member of this room")
    db.delete(membership)
    db.commit()
    return {"status": "left"}


@app.post("/me/leave")
def leave_current_room(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    membership = db.scalar(
        select(RoomMembership).where(RoomMembership.user_id == user.id)
    )
    if membership is None:
        raise HTTPException(status_code=400, detail="You do not belong to any room")
    db.delete(membership)
    db.commit()
    return {"status": "left"}