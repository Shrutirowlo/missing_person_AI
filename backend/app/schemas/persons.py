from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Gender = Literal["MALE", "FEMALE", "OTHER", "UNKNOWN"]
PersonStatus = Literal["ACTIVE", "FOUND", "RESOLVED", "CLOSED"]


class SightingIn(BaseModel):
    person_id: str
    location: str = ""
    description: str = ""
    photo_urls: list[str] = []


class SightingOut(BaseModel):
    id: str
    person_id: str
    submitted_by: str
    ngo_org: str | None = None
    location: str = ""
    description: str = ""
    photo_urls: list[str] = []
    created_at: datetime | None = None


class NgoShareIn(BaseModel):
    ngo_org: str
    ngo_notes: str = ""


class PersonIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    age: int | None = Field(default=None, ge=0, le=130)
    gender: Gender = "UNKNOWN"
    height_cm: float | None = Field(default=None, ge=30, le=250)
    last_seen_location: str = ""
    last_seen_city: str = ""
    last_seen_state: str = ""
    date_last_seen: date | None = None
    description: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    contact_email: str = ""


class PersonUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    age: int | None = Field(default=None, ge=0, le=130)
    gender: Gender | None = None
    height_cm: float | None = Field(default=None, ge=30, le=250)
    last_seen_location: str | None = None
    last_seen_city: str | None = None
    last_seen_state: str | None = None
    date_last_seen: date | None = None
    description: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    status: PersonStatus | None = None


class PersonImageOut(BaseModel):
    id: str
    url: str
    is_primary: bool = False
    ai_labels: dict = {}
    created_at: datetime | None = None


class PersonOut(BaseModel):
    id: str
    full_name: str
    age: int | None = None
    gender: str
    height_cm: float | None = None
    last_seen_location: str = ""
    last_seen_city: str = ""
    last_seen_state: str = ""
    date_last_seen: str | None = None
    description: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    status: str
    archived: bool = False
    images: list[PersonImageOut] = []
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
