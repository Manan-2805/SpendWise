# Auth
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    PasswordChangeRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)

# Categories
from app.schemas.category import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
)
from app.schemas.common import (
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
    PaginationParams,
    SuccessResponse,
    ValidationErrorResponse,
)

# Transactions
from app.schemas.transaction import (
    TransactionCreate,
    TransactionFilters,
    TransactionResponse,
    TransactionType,
    TransactionUpdate,
    TransactionWithCategoryResponse,
)

# Users
from app.schemas.user import (
    UserCreate,
    UserInDB,
    UserResponse,
    UserUpdate,
)

__all__: list[str] = [
    # Common
    "PaginatedResponse",
    "PaginationParams",
    "ErrorResponse",
    "ErrorDetail",
    "ValidationErrorResponse",
    "SuccessResponse",
    # Auth
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "RefreshRequest",
    "PasswordChangeRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    # Users
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserInDB",
    # Categories
    "CategoryCreate",
    "CategoryUpdate",
    "CategoryResponse",
    # Transactions
    "TransactionType",
    "TransactionCreate",
    "TransactionUpdate",
    "TransactionResponse",
    "TransactionWithCategoryResponse",
    "TransactionFilters",
]
