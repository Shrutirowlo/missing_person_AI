from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..deps import current_user_dep, db_dep
from ..schemas.auth import LoginIn, ProfileUpdateIn, RegisterIn, TokenOut, UserOut
from ..services.auth_service import AuthService, to_user_out

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, db: AsyncIOMotorDatabase = Depends(db_dep)):
    try:
        return await AuthService(db).register(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncIOMotorDatabase = Depends(db_dep)):
    try:
        return await AuthService(db).login(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.get("/profile", response_model=UserOut)
async def profile(user: dict = Depends(current_user_dep)):
    return to_user_out(user)


@router.patch("/profile", response_model=UserOut)
async def update_profile(payload: ProfileUpdateIn, user: dict = Depends(current_user_dep),
                         db: AsyncIOMotorDatabase = Depends(db_dep)):
    try:
        updated = await AuthService(db).update_profile(user["id"], payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return updated


@router.post("/logout")
async def logout():
    # Stateless JWT: logout is client-side token discard.
    return {"status": "ok", "message": "Discard the access token client-side to log out."}
