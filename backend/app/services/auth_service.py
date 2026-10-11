"""Auth service: registration + login + profile."""
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from ..repositories.users import UserRepository
from ..schemas.auth import UserOut
from ..security import create_access_token, hash_password, verify_password


def public_user(doc: dict) -> dict:
    # Legacy user docs may carry approved=None or missing name fields;
    # coerce so UserOut response validation never 500s on old records.
    return {
        "id": doc.get("id"),
        "username": doc.get("username"),
        "email": doc.get("email"),
        "first_name": doc.get("first_name") or "",
        "last_name": doc.get("last_name") or "",
        "role": doc.get("role"),
        "approved": bool(doc.get("approved", False)),
        "ngo_org": doc.get("ngo_org"),
        "created_at": doc.get("created_at"),
    }


class AuthService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.users = UserRepository(db)

    async def register(self, payload: dict) -> dict:
        if await self.users.get_by_username(payload["username"]):
            raise ValueError("Username already taken")
        # Normalize blank email to "no email": the users.email unique index
        # rejects repeated null/"" values, so the field is omitted entirely
        # instead of storing a colliding placeholder.
        email = (payload.get("email") or "").strip() or None
        if email and await self.users.get_by_email(email):
            raise ValueError("Email already registered")
        # Public signup: CITIZEN gets instant access; POLICE is created
        # UNAPPROVED (admin must approve before any protected access).
        # Anything else is clamped to CITIZEN — roles are never self-granted.
        requested = payload.get("requested_role") or "CITIZEN"
        role = requested if requested in ("CITIZEN", "POLICE") else "CITIZEN"
        doc = {
            "username": payload["username"],
            "password_hash": hash_password(payload["password"]),
            "first_name": payload.get("first_name", ""),
            "last_name": payload.get("last_name", ""),
            "role": role,
            "approved": False,
            "ngo_org": None,
        }
        if email is not None:
            doc["email"] = email
        try:
            created = await self.users.create(doc)
        except DuplicateKeyError:
            # Lost a race with a concurrent signup — report cleanly.
            raise ValueError("Username or email already taken")
        token = create_access_token(
            created["id"],
            {
                "username": created["username"],
                "role": created["role"],
                "approved": created.get("approved", False),
                "ngo_org": created.get("ngo_org"),
            }
        )
        return {"access_token": token, "token_type": "bearer", "user": public_user(created)}

    async def login(self, username: str, password: str) -> dict:
        user = await self.users.get_by_username(username)
        if user is None or not verify_password(password, user.get("password_hash", "")):
            raise ValueError("Invalid username or password")
        token = create_access_token(
            user["id"],
            {
                "username": user["username"],
                "role": user["role"],
                "approved": user.get("approved", False),
                "ngo_org": user.get("ngo_org"),
            }
        )
        return {"access_token": token, "token_type": "bearer", "user": public_user(user)}

    async def update_profile(self, user_id: str, patch: dict) -> dict | None:
        clean = {k: v for k, v in patch.items() if v is not None and k in ("first_name", "last_name", "email")}
        if "email" in clean:
            clean["email"] = (clean["email"] or "").strip() or None
            if clean["email"] is None:
                del clean["email"]  # keep the unique index collision-free
            else:
                other = await self.users.get_by_email(clean["email"])
                if other is not None and other["id"] != user_id:
                    raise ValueError("Email already registered")
        try:
            updated = await self.users.update(user_id, clean)
        except DuplicateKeyError:
            raise ValueError("Email already registered")
        return public_user(updated) if updated else None


def to_user_out(doc: dict) -> UserOut:
    return UserOut(**public_user(doc))
