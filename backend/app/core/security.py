from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.user import User, UserRole

_password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    expires_in = settings.jwt_access_ttl_min * 60
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)
    return token, expires_in


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from exc
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return uuid.UUID(sub)


def refresh_token_ttl(user: User) -> timedelta:
    days = (
        settings.jwt_refresh_ttl_days_master
        if user.is_master
        else settings.jwt_refresh_ttl_days
    )
    return timedelta(days=days)


def require_admin_user(user: User) -> User:
    if user.is_master:
        return user
    if user.role != UserRole.admin or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


def require_master_user(user: User) -> User:
    if not user.is_master:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Master role required")
    return user
