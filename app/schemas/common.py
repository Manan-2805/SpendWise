from pydantic import BaseModel, Field


def require_value[Value](value: Value | None) -> Value:
    if value is None:
        raise ValueError("Field cannot be null")
    return value


class PaginatedResponse[T](BaseModel):
    """
    Generic paginated response — works for any resource type.

    Usage in route handlers:
        return PaginatedResponse[TransactionResponse](
            items=transactions,
            total=total,
            page=page,
            per_page=per_page,
        )

    Usage in route decorator:
        @router.get("/", response_model=PaginatedResponse[TransactionResponse])
    """

    items: list[T]
    total: int = Field(ge=0, description="Total number of matching records")
    page: int = Field(ge=1, description="Current page number (1-indexed)")
    per_page: int = Field(ge=1, le=100, description="Items per page")
    pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool
    has_prev: bool

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        per_page: int,
    ) -> "PaginatedResponse[T]":
        """Factory method — calculates derived fields automatically."""
        import math

        pages: int = math.ceil(total / per_page) if total > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )


class ErrorDetail(BaseModel):
    """Single field-level error in a validation response."""

    field: str = Field(description="Dot-separated path to the invalid field")
    message: str = Field(description="Human-readable error message")
    type: str = Field(description="Machine-readable error type code")


class ErrorResponse(BaseModel):
    """Standard error response for HTTP errors."""

    detail: str = Field(description="Human-readable error description")
    code: str = Field(description="Machine-readable error code for client handling")


class ValidationErrorResponse(BaseModel):
    """422 Unprocessable Entity — field-level validation failures."""

    detail: str = "Request validation failed"
    code: str = "VALIDATION_ERROR"
    errors: list[ErrorDetail]


class SuccessResponse(BaseModel):
    """Simple success acknowledgement for operations that return no data."""

    message: str
    success: bool = True


class PaginationParams(BaseModel):
    """
    Query parameter group for pagination — used with Depends() in routes.

    Usage:
        @router.get("/transactions/")
        async def list_transactions(
            pagination: PaginationParams = Depends(),
        ):
            skip = pagination.offset
            limit = pagination.per_page
    """

    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate the SQL OFFSET from page and per_page."""
        return (self.page - 1) * self.per_page
