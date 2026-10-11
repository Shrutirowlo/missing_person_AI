from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["ADMIN", "POLICE", "NGO_WORKER", "CITIZEN"]


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: str | None = None
    first_name: str = ""
    last_name: str = ""
    # Public signup may request CITIZEN (instant access) or POLICE (locked
    # until an admin approves). ADMIN/NGO_WORKER are never self-granted —
    # the service clamps anything else to CITIZEN.
    requested_role: Literal["CITIZEN", "POLICE"] = "CITIZEN"


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    email: str | None = None
    first_name: str = ""
    last_name: str = ""
    role: str
    approved: bool = False
    ngo_org: str | None = None
    created_at: datetime | None = None


class UserAdminOut(UserOut):
    """Used for admin list responses; explicit response model."""
    pass


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProfileUpdateIn(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
