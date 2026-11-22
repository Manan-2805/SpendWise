import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Response
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings
from app.core.exceptions import AuthenticationError

password_hasher = PasswordHash((BcryptHasher(),))


def hash_password(plain_text: str) -> str:
    return password_hasher.hash(plain_text)


def verify_password(plain_text: str, hashed: str) -> bool:
    return password_hasher.verify(plain_text, hashed)


def create_access_token(
    subject: int | str, expires_delta: timedelta | None = None, *, auth_version: int = 0
) -> str:
    jti = str(uuid.uuid4())
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "exp": expire,
        "iat": datetime.now(UTC),
        "sub": str(subject),
        "jti": jti,
        "type": "access",
        "auth_version": auth_version,
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: int | str) -> tuple[str, str]:
    jti = str(uuid.uuid4())
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "exp": expire,
        "iat": datetime.now(UTC),
        "sub": str(subject),
        "jti": jti,
        "type": "refresh",
    }

    raw_token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return raw_token, jti


def verify_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "jti", "type"]},
        )
        if payload.get("type") != expected_type:
            raise AuthenticationError(f"Invalid token type: expected {expected_type}")
        return payload
    except jwt.ExpiredSignatureError as e:
        raise AuthenticationError("Token has expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthenticationError("Invalid token") from e


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    secure = settings.ENVIRONMENT != "development"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=f"{settings.API_V1_PREFIX}/auth/refresh",
    )


def clear_auth_cookies(response: Response) -> None:
    secure = settings.ENVIRONMENT != "development"
    response.delete_cookie(key="access_token", path="/", secure=secure, httponly=True)
    response.delete_cookie(
        key="refresh_token",
        path=f"{settings.API_V1_PREFIX}/auth/refresh",
        secure=secure,
        httponly=True,
    )


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
