from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("Enter a valid email address")
        return value


class ProfileInput(BaseModel):
    age: int = Field(ge=18, le=100)
    gender: str = Field(min_length=1)
    occupation: str = Field(min_length=1)
    location: str = Field(min_length=1)
    budget_min: int = Field(ge=0)
    budget_max: int = Field(ge=0)
    sleep_schedule: str = Field(min_length=1)
    smoking: str = Field(min_length=1)
    drinking: str = Field(min_length=1)
    cleanliness: int = Field(ge=1, le=5)
    noise_level: int = Field(ge=1, le=5)
    guests_preference: str = Field(min_length=1)
    food_preference: str = Field(min_length=1)
    pets: str = Field(min_length=1)
    study_habit: str = Field(min_length=1)
    interests: str = ""
    gender_preference: str = Field(min_length=1)
    room_type_preference: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _strip_text(cls, values):
        if isinstance(values, dict):
            return {
                key: value.strip() if isinstance(value, str) else value
                for key, value in values.items()
            }
        return values

    @model_validator(mode="after")
    def _budget_order(self) -> "ProfileInput":
        if self.budget_max < self.budget_min:
            raise ValueError("budget_max must be greater than or equal to budget_min")
        return self


class RoomInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=100)
    room_type: str = Field(min_length=1)
    monthly_rent: int = Field(ge=0)
    capacity: int = Field(ge=1, le=100)
    gender_restriction: str = Field(default="any", pattern="^(any|male|female)$")
    description: str = ""
    amenities: str = ""
    active: bool = True

    @model_validator(mode="before")
    @classmethod
    def _strip_text(cls, values):
        if isinstance(values, dict):
            return {
                key: value.strip() if isinstance(value, str) else value
                for key, value in values.items()
            }
        return values


class FilterRequest(BaseModel):
    """Hard constraint filters submitted alongside recommendation or join requests.

    The user's profile (soft preferences) is loaded from the database.
    Only explicitly user-defined hard constraints appear here.
    """

    strict_max_rent: int | None = Field(default=None, ge=0)
    required_room_type: str | None = None
    no_smoking: bool = False

    @field_validator("strict_max_rent", mode="before")
    @classmethod
    def _blank_rent(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    @field_validator("required_room_type", mode="before")
    @classmethod
    def _blank_room_type(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and value.strip().lower() in {"", "any"}:
            return None
        return value

    @field_validator("no_smoking", mode="before")
    @classmethod
    def _coerce_flag(cls, value):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return value


# Backward compatibility alias — older code may reference this name.
RecommendationRequest = FilterRequest