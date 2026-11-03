"""Shapes of JSON bodies the browser sends. FastAPI checks them automatically."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=200)
    role: Literal["student", "admin"]


class RoomTypeIn(BaseModel):
    """"Any room like this": a hostel code plus optional filters (None = any)."""

    hostel: str = Field(min_length=1, max_length=4)
    seater: Literal[1, 2, 3] | None = None
    ac: bool | None = None
    floor: int | None = Field(default=None, ge=0, le=20)


class ChoiceIn(BaseModel):
    room_id: int | None = None
    type: RoomTypeIn | None = None

    @model_validator(mode="after")
    def _exactly_one(self):
        if (self.room_id is None) == (self.type is None):
            raise ValueError("give either room_id or type")
        return self


class RequestIn(BaseModel):
    """Ranked choices, best first. room_ids is the older shape (exact rooms only)."""

    room_ids: list[int] | None = None
    choices: list[ChoiceIn] | None = None

    @model_validator(mode="after")
    def _one_shape(self):
        if (self.room_ids is None) == (self.choices is None):
            raise ValueError("give either room_ids or choices")
        return self

    def as_choices(self) -> list[int | dict]:
        if self.room_ids is not None:
            return list(self.room_ids)
        return [c.room_id if c.room_id is not None else c.type.model_dump() for c in self.choices]


class MatchRunIn(BaseModel):
    algorithm: Literal["ttc", "pairwise"] = "ttc"
    dry_run: bool = False
