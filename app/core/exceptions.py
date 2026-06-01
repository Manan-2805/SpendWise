"""
Custom exception hierarchy for SpendWise.

Design principles:
- Every exception has a machine-readable `code` for API clients to handle
- Every exception has a human-readable `message`
- The hierarchy mirrors HTTP status codes at the domain level
- Catching a parent catches all children (use this in exception handlers)

Usage in services:
    raise TransactionNotFoundError(transaction_id=42)

Usage in API exception handlers:
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
"""

from decimal import Decimal


# ─────────────────────────────────────────────────────────────
# Base exception
# ─────────────────────────────────────────────────────────────

class SpendWiseError(Exception):
    """
    Base class for all SpendWise application exceptions.

    All custom exceptions inherit from this — catching SpendWiseError
    catches everything the application intentionally raises.
    """
    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, code={self.code!r})"


# ─────────────────────────────────────────────────────────────
# 400 — Bad Request / Validation failures
# ─────────────────────────────────────────────────────────────

class BadRequestError(SpendWiseError):
    """Generic bad request — the client sent something invalid."""
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str = "Bad request") -> None:
        super().__init__(message)


class ValidationError(SpendWiseError):
    """
    Business logic validation failed.

    Distinct from Pydantic's ValidationError (which handles field-level
    validation). This is for domain-level rules like:
    "You cannot create a transaction with a future date without a note."
    """
    status_code = 400
    code = "VALIDATION_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)


# ─────────────────────────────────────────────────────────────
# 401 — Unauthenticated
# ─────────────────────────────────────────────────────────────

class AuthenticationError(SpendWiseError):
    """Could not verify who the user is."""
    status_code = 401
    code = "AUTHENTICATION_FAILED"

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message)


class InvalidTokenError(AuthenticationError):
    """JWT is malformed, expired, or has been tampered with."""
    code = "INVALID_TOKEN"

    def __init__(self, message: str = "Token is invalid or expired") -> None:
        super().__init__(message)


class InvalidCredentialsError(AuthenticationError):
    """Email and password combination is wrong."""
    code = "INVALID_CREDENTIALS"

    def __init__(self) -> None:
        super().__init__("Invalid email or password")


# ─────────────────────────────────────────────────────────────
# 403 — Forbidden / Authorisation failures
# ─────────────────────────────────────────────────────────────

class AccessDeniedError(SpendWiseError):
    """
    The user is authenticated but does not have permission.

    Note: We deliberately return 404 in many places where 403 would be
    technically correct — returning 403 reveals that the resource exists.
    Use AccessDeniedError only when it is safe to reveal existence.
    """
    status_code = 403
    code = "ACCESS_DENIED"

    def __init__(self, message: str = "You do not have permission to access this resource") -> None:
        super().__init__(message)


class InactiveUserError(AccessDeniedError):
    """User account exists but has been deactivated."""
    code = "INACTIVE_USER"

    def __init__(self) -> None:
        super().__init__("This account has been deactivated")


class UnverifiedEmailError(AccessDeniedError):
    """User has not verified their email address."""
    code = "EMAIL_NOT_VERIFIED"

    def __init__(self) -> None:
        super().__init__("Please verify your email address before continuing")


# ─────────────────────────────────────────────────────────────
# 404 — Not Found
# ─────────────────────────────────────────────────────────────

class NotFoundError(SpendWiseError):
    """Base class for all 'resource not found' exceptions."""
    status_code = 404
    code = "NOT_FOUND"

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message)


class UserNotFoundError(NotFoundError):
    code = "USER_NOT_FOUND"

    def __init__(self, user_id: int | None = None, email: str | None = None) -> None:
        if user_id is not None:
            message = f"User with id {user_id} not found"
        elif email is not None:
            message = f"User with email {email} not found"
        else:
            message = "User not found"
        super().__init__(message)
        self.user_id = user_id
        self.email = email


class CategoryNotFoundError(NotFoundError):
    code = "CATEGORY_NOT_FOUND"

    def __init__(self, category_id: int) -> None:
        super().__init__(f"Category with id {category_id} not found")
        self.category_id = category_id


class TransactionNotFoundError(NotFoundError):
    code = "TRANSACTION_NOT_FOUND"

    def __init__(self, transaction_id: int) -> None:
        super().__init__(f"Transaction with id {transaction_id} not found")
        self.transaction_id = transaction_id


# ─────────────────────────────────────────────────────────────
# 409 — Conflict
# ─────────────────────────────────────────────────────────────

class ConflictError(SpendWiseError):
    """A resource already exists or there is a state conflict."""
    status_code = 409
    code = "CONFLICT"

    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(message)


class EmailAlreadyRegisteredError(ConflictError):
    code = "EMAIL_ALREADY_REGISTERED"

    def __init__(self, email: str) -> None:
        super().__init__(f"An account with email {email} already exists")
        self.email = email


class UsernameAlreadyTakenError(ConflictError):
    code = "USERNAME_ALREADY_TAKEN"

    def __init__(self, username: str) -> None:
        super().__init__(f"Username '{username}' is already taken")
        self.username = username


# ─────────────────────────────────────────────────────────────
# 422 — Business Logic Validation
# ─────────────────────────────────────────────────────────────

class InsufficientFundsError(ValidationError):
    """Transaction would result in a negative balance below allowed threshold."""
    code = "INSUFFICIENT_FUNDS"

    def __init__(self, required: Decimal, available: Decimal) -> None:
        super().__init__(
            f"Insufficient funds: need {required}, have {available}"
        )
        self.required = required
        self.available = available


# ─────────────────────────────────────────────────────────────
# 429 — Rate Limited (raised manually, usually handled by slowapi)
# ─────────────────────────────────────────────────────────────

class RateLimitExceededError(SpendWiseError):
    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, message: str = "Too many requests — please slow down") -> None:
        super().__init__(message)


# ─────────────────────────────────────────────────────────────
# 503 — Service Unavailable
# ─────────────────────────────────────────────────────────────

class ServiceUnavailableError(SpendWiseError):
    """A required external service (DB, Redis, email) is unreachable."""
    status_code = 503
    code = "SERVICE_UNAVAILABLE"

    def __init__(self, service: str = "service") -> None:
        super().__init__(f"The {service} is currently unavailable — please try again shortly")
        self.service = service