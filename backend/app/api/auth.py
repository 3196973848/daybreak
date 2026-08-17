import re

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import (
    clear_session_cookie,
    get_current_user,
    hash_password,
    set_session_cookie,
    verify_password,
)
from ..database import get_db
from ..models import Goal, User


router = APIRouter(prefix="/api/auth", tags=["auth"])

USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff-]{3,32}$")


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_RE.match(value):
            raise ValueError("用户名需为 3-32 位字母、数字、下划线、中文或连字符")
        return value

    @field_validator("password")
    @classmethod
    def valid_password(cls, value: str) -> str:
        if len(value) < 8 or len(value) > 128:
            raise ValueError("密码长度需为 8-128 位")
        return value


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "created_at": user.created_at.isoformat(),
    }


@router.post("/register", status_code=201)
def register(
    payload: Credentials, response: Response, db: Session = Depends(get_db)
):
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing is not None:
        raise HTTPException(status_code=409, detail="用户名已被使用")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()
    for goal in db.scalars(select(Goal).where(Goal.user_id.is_(None))).all():
        goal.user_id = user.id
    db.commit()
    db.refresh(user)
    set_session_cookie(response, user.id)
    return _user_dict(user)


@router.post("/login")
def login(
    payload: Credentials, response: Response, db: Session = Depends(get_db)
):
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    set_session_cookie(response, user.id)
    return _user_dict(user)


@router.post("/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_dict(user)
