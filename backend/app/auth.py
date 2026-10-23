from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import User

SESSION_TTL = timedelta(days=7)
PBKDF2_ITERATIONS = 200_000

_sessions: dict[str, tuple[int, datetime]] = {}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split(":", 1)
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(actual.hex(), digest_hex)


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = (user_id, datetime.now(timezone.utc) + SESSION_TTL)
    return token


def destroy_session(token: str) -> None:
    _sessions.pop(token, None)


def token_from_header(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def _resolve(token: str | None, db: Session) -> User | None:
    if not token:
        return None
    entry = _sessions.get(token)
    if entry is None:
        return None
    user_id, expires_at = entry
    if expires_at <= datetime.now(timezone.utc):
        _sessions.pop(token, None)
        return None
    return db.get(User, user_id)


def optional_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    return _resolve(token_from_header(authorization), db)


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user