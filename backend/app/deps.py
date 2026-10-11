"""FastAPI dependencies: DB handle + authenticated current user + role guards."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from .db import get_db
from .repositories.users import UserRepository
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


async def db_dep() -> AsyncIOMotorDatabase:
    return get_db()


async def current_user_dep(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(creds.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = await UserRepository(db).get_by_id(payload.get("sub", ""))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return user


def require_role(*roles: str):
    """Returns a dependency that allows only the listed roles."""
    async def _dep(user: dict = Depends(current_user_dep)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(roles)}"
            )
        return user
    return _dep


def require_admin():
    return require_role("ADMIN")


def require_police_or_admin():
    return require_role("POLICE", "ADMIN")


def require_ngo_or_above():
    """NGO_WORKER, POLICE, or ADMIN."""
    return require_role("NGO_WORKER", "POLICE", "ADMIN")


def require_approved_police():
    """POLICE who have been approved by an admin, or ADMIN."""
    async def _dep(user: dict = Depends(current_user_dep)) -> dict:
        role = user.get("role")
        if role == "ADMIN":
            return user
        if role == "POLICE":
            if not user.get("approved", False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Police account pending admin approval."
                )
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires approved POLICE or ADMIN role."
        )
    return _dep
