"""Admin-only user & access management: list users, set role, assign accounts."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_admin
from app.database.session import get_db
from app.services.auth.users import AuthUserService

router = APIRouter(prefix="/admin/users", tags=["admin"])


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: str
    is_active: bool
    picture: str | None
    last_login_at: datetime | None
    account_ids: list[int]


class RoleIn(BaseModel):
    role: str  # "admin" | "manager"


class ActiveIn(BaseModel):
    is_active: bool


class AccountsIn(BaseModel):
    account_ids: list[int]


@router.get("", response_model=list[UserOut], summary="List users + their access")
def list_users(
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserOut]:
    return [UserOut(**u) for u in AuthUserService(db).list_users_with_access()]


@router.patch("/{user_id}/role", response_model=UserOut, summary="Set a user's role")
def set_role(
    user_id: int,
    body: RoleIn,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    svc = AuthUserService(db)
    try:
        user = svc.set_role(user_id, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    db.commit()
    return _one(svc, user_id)


@router.patch("/{user_id}/active", response_model=UserOut, summary="Enable/disable a user")
def set_active(
    user_id: int,
    body: ActiveIn,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    svc = AuthUserService(db)
    if admin.id == user_id and not body.is_active:
        raise HTTPException(status_code=400, detail="You can't disable your own account.")
    if svc.set_active(user_id, body.is_active) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    db.commit()
    return _one(svc, user_id)


@router.put("/{user_id}/accounts", response_model=UserOut, summary="Set a manager's accounts")
def set_accounts(
    user_id: int,
    body: AccountsIn,
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    svc = AuthUserService(db)
    if svc.set_accounts(user_id, body.account_ids) is None:
        raise HTTPException(status_code=404, detail="User not found.")
    db.commit()
    return _one(svc, user_id)


@router.delete("/{user_id}", response_model=None, summary="Remove a user from the platform")
def delete_user(
    user_id: int,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="You can't remove your own account.")
    svc = AuthUserService(db)
    if not svc.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found.")
    db.commit()
    return {"ok": True, "removed": user_id}


def _one(svc: AuthUserService, user_id: int) -> UserOut:
    for u in svc.list_users_with_access():
        if u["id"] == user_id:
            return UserOut(**u)
    raise HTTPException(status_code=404, detail="User not found.")
