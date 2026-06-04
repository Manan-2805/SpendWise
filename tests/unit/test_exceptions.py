from decimal import Decimal

from app.core.exceptions import (
    AccessDeniedError,
    AuthenticationError,
    BadRequestError,
    CategoryNotFoundError,
    ConflictError,
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InsufficientFundsError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    RateLimitExceededError,
    ServiceUnavailableError,
    SpendWiseError,
    TransactionNotFoundError,
    UnverifiedEmailError,
    UsernameAlreadyTakenError,
    UserNotFoundError,
    ValidationError,
)


def test_exceptions_repr_and_init() -> None:
    # Test custom code init
    err = SpendWiseError("Custom message", code="CUSTOM_CODE")
    assert err.message == "Custom message"
    assert err.code == "CUSTOM_CODE"
    assert repr(err) == "SpendWiseError(message='Custom message', code='CUSTOM_CODE')"

    # Test default bad request
    bad_req = BadRequestError()
    assert bad_req.message == "Bad request"

    # Test validation error
    val_err = ValidationError("error")
    assert val_err.message == "error"

    # Test authentication error
    auth_err = AuthenticationError()
    assert auth_err.message == "Authentication failed"

    # Test invalid token
    tok_err = InvalidTokenError()
    assert tok_err.message == "Token is invalid or expired"

    # Test invalid credentials
    cred_err = InvalidCredentialsError()
    assert cred_err.message == "Invalid email or password"

    # Test access denied
    acc_err = AccessDeniedError()
    assert acc_err.message == "You do not have permission to access this resource"

    # Test inactive user
    in_err = InactiveUserError()
    assert in_err.message == "This account has been deactivated"

    # Test unverified email
    unv_err = UnverifiedEmailError()
    assert unv_err.message == "Please verify your email address before continuing"

    # Test not found
    nf_err = NotFoundError()
    assert nf_err.message == "Resource not found"

    # Test user not found empty init
    u_nf_empty = UserNotFoundError()
    assert u_nf_empty.message == "User not found"

    # Test user not found with email
    u_nf_email = UserNotFoundError(email="test@test.com")
    assert u_nf_email.message == "User with email test@test.com not found"

    # Test category not found
    cat_nf = CategoryNotFoundError(1)
    assert cat_nf.message == "Category with id 1 not found"

    # Test transaction not found
    tx_nf = TransactionNotFoundError(1)
    assert tx_nf.message == "Transaction with id 1 not found"

    # Test conflict error
    conf_err = ConflictError()
    assert conf_err.message == "Resource conflict"

    # Test email already registered
    email_reg = EmailAlreadyRegisteredError("test@test.com")
    assert email_reg.message == "An account with email test@test.com already exists"

    # Test username already taken
    user_taken = UsernameAlreadyTakenError("username")
    assert user_taken.message == "Username 'username' is already taken"

    # Test insufficient funds
    funds_err = InsufficientFundsError(Decimal("10.00"), Decimal("5.00"))
    assert funds_err.message == "Insufficient funds: need 10.00, have 5.00"

    # Test rate limit exceeded
    rate_err = RateLimitExceededError()
    assert rate_err.message == "Too many requests — please slow down"

    # Test service unavailable
    srv_err = ServiceUnavailableError("database")
    assert (
        srv_err.message
        == "The database is currently unavailable — please try again shortly"
    )
