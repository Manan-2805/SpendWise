import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Response
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

# We initialize the hasher with Bcrypt.
# Bcrypt automatically generates a unique salt for every hash.
password_hasher = PasswordHash((BcryptHasher(),))


def hash_password(plain_text: str) -> str:
    """
    Hash a password using Bcrypt.
    The output includes the algorithm identifier, cost factor, salt, and hash.
    Example: $2b$12$W9G7...
    """
    return password_hasher.hash(plain_text)


def verify_password(plain_text: str, hashed: str) -> bool:
    """
    Verify a password against a hash.
    pwdlib handles extracting the salt and cost factor from the stored hash string.
    """
    return password_hasher.verify(plain_text, hashed)


def create_access_token(
    subject: int | str, expires_delta: timedelta | None = None
) -> str:
    """
    Create a short-lived, stateless access token.
    """
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
        "jti": str(uuid.uuid4()),
        "type": "access",  # CRITICAL: Prevents using a refresh token as an access token
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: int | str) -> str:
    """
    Create a long-lived refresh token.
    Note: The actual revocation state is tracked in the database, not the JWT itself.
    """
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "exp": expire,
        "iat": datetime.now(UTC),
        "sub": str(subject),
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT.
    Raises InvalidTokenError if signature is invalid, expired, or malformed.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except InvalidTokenError as e:
        # We catch the base exception to avoid leaking specific failure reasons
        # (e.g., "ExpiredSignatureError" vs "InvalidSignatureError") to attackers.
        raise InvalidTokenError("Invalid or expired token") from e


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """
    Set secure, HttpOnly cookies for access and refresh tokens.
    """
    # Access Token Cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # JS cannot read this
        secure=True,  # Only sent over HTTPS (ignored on localhost in some browsers)
        samesite="lax",  # Protects against CSRF
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",  # Available on all routes
    )

    # Refresh Token Cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",  # Only sent to auth routes (reduces attack surface)
    )


def clear_auth_cookies(response: Response) -> None:
    """
    Clear cookies on logout.
    """
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")


def hash_refresh_token(token: str) -> str:
    """
    Create a SHA-256 hash of the refresh token for database storage.
    SHA-256 is fast and sufficient for hashing high-entropy random strings (JWTs).
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
