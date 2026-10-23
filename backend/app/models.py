from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", uselist=False, lazy="selectin"
    )


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(50))
    occupation: Mapped[str] = mapped_column(String(100))
    location: Mapped[str] = mapped_column(String(100))
    budget_min: Mapped[int] = mapped_column(Integer)
    budget_max: Mapped[int] = mapped_column(Integer)
    sleep_schedule: Mapped[str] = mapped_column(String(50))
    smoking: Mapped[str] = mapped_column(String(50))
    drinking: Mapped[str] = mapped_column(String(50))
    cleanliness: Mapped[int] = mapped_column(Integer)
    noise_level: Mapped[int] = mapped_column(Integer)
    guests_preference: Mapped[str] = mapped_column(String(50))
    food_preference: Mapped[str] = mapped_column(String(50))
    pets: Mapped[str] = mapped_column(String(50))
    study_habit: Mapped[str] = mapped_column(String(80))
    interests: Mapped[str] = mapped_column(Text)
    gender_preference: Mapped[str] = mapped_column(String(50))
    room_type_preference: Mapped[str] = mapped_column(String(50))
    user: Mapped[User] = relationship(back_populates="profile")


class Room(Base):
    __tablename__ = "rooms"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(100))
    room_type: Mapped[str] = mapped_column(String(50))
    monthly_rent: Mapped[int] = mapped_column(Integer)
    capacity: Mapped[int] = mapped_column(Integer)
    gender_restriction: Mapped[str] = mapped_column(String(20), default="any", server_default="any")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    amenities: Mapped[str] = mapped_column(Text, default="", server_default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    memberships: Mapped[list["RoomMembership"]] = relationship(
        back_populates="room", lazy="selectin"
    )


class RoomMembership(Base):
    __tablename__ = "room_memberships"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_room_memberships_room_user"),
        Index("uq_room_memberships_user", "user_id", unique=True),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    room: Mapped[Room] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(lazy="selectin")