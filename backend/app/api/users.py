from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..deps import current_user_dep, db_dep, require_admin
from ..repositories.users import UserRepository
from ..schemas.auth import UserOut
from ..services.auth_service import public_user

router = APIRouter(prefix="/users", tags=["users"])


def _pub(doc: dict) -> dict:
    # Shared normalizer: legacy docs (approved=None, missing names)
    # must still serialize into UserOut without a 500.
    return public_user(doc)


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(current_user_dep)):
    return _pub(user)


@router.get("", response_model=list[UserOut])
async def list_users(user: dict = Depends(require_admin()),
                     db: AsyncIOMotorDatabase = Depends(db_dep)):
    return [_pub(d) for d in await UserRepository(db).list_all()]
