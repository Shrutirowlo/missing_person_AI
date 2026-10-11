"""Admin router — user management, role assignment, and police approvals."""
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from ..deps import db_dep, require_admin
from ..repositories.users import UserRepository
from ..schemas.auth import UserOut
from ..services.auth_service import public_user

router = APIRouter(prefix="/admin", tags=["admin"])

# ADMIN cannot be assigned via this endpoint — use promote-admin instead
ASSIGNABLE_ROLES = {"CITIZEN", "POLICE", "NGO_WORKER"}


class RoleChangeIn(BaseModel):
    role: str


class ApprovalIn(BaseModel):
    approved: bool


def _pub(doc: dict) -> dict:
    # Reuse the shared normalizer so legacy docs (approved=None, etc.)
    # serialize cleanly into UserOut instead of raising a 500.
    return public_user(doc)


@router.get("/users", response_model=list[UserOut])
async def list_all_users(
    user: dict = Depends(require_admin()),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    docs = await UserRepository(db).list_all(limit=500)
    return [_pub(d) for d in docs]


@router.patch("/users/{user_id}/role")
async def change_user_role(
    user_id: str,
    payload: RoleChangeIn,
    user: dict = Depends(require_admin()),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    if payload.role not in ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assign role '{payload.role}'. Allowed: {sorted(ASSIGNABLE_ROLES)}"
        )
    repo = UserRepository(db)
    target = await repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    updated = await repo.update(user_id, {"role": payload.role, "approved": False})
    return _pub(updated)


@router.patch("/users/{user_id}/approval")
async def set_approval(
    user_id: str,
    payload: ApprovalIn,
    user: dict = Depends(require_admin()),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    repo = UserRepository(db)
    target = await repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if target.get("role") != "POLICE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only POLICE accounts require approval"
        )
    updated = await repo.update(user_id, {"approved": payload.approved})
    return _pub(updated)


@router.post("/users/{user_id}/promote-admin")
async def promote_to_admin(
    user_id: str,
    user: dict = Depends(require_admin()),
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """Only existing admins can promote another user to ADMIN."""
    repo = UserRepository(db)
    target = await repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    updated = await repo.update(user_id, {"role": "ADMIN", "approved": True})
    return _pub(updated)
