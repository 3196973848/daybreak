import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User


COOKIE_NAME = "planagent_session"
_EPHEMERAL_SECRET = secrets.token_urlsafe(32)


def _secret() -> bytes:
    return (settings.auth_secret or _EPHEMERAL_SECRET).encode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32
    )
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, hash_hex = stored.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        actual = hashlib.scrypt(
            password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=len(expected)
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_session_token(user_id: int) -> str:
    payload = json.dumps(
        {
            "uid": user_id,
            "exp": int(time.time()) + settings.auth_session_ttl_days * 86400,
        },
        separators=(",", ":"),
    ).encode()
    body = _b64(payload)
    signature = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def parse_session_token(token: str) -> int | None:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return None
        payload = json.loads(_unb64(body))
        if payload.get("exp", 0) < time.time():
            return None
        user_id = payload.get("uid")
        return int(user_id) if isinstance(user_id, int) else None
    except Exception:
        return None


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    if not settings.auth_enabled:
        user = db.scalar(select(User).where(User.username == "local"))
        if user is None:
            user = User(username="local", password_hash="")
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    token = request.cookies.get(COOKIE_NAME)
    user_id = parse_session_token(token) if token else None
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        create_session_token(user_id),
        httponly=True,
        samesite="lax",
        max_age=settings.auth_session_ttl_days * 86400,
        secure=settings.auth_cookie_secure,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)
