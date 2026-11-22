from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.exceptions import (
    AccessDeniedError,
    CategoryNotFoundError,
    TransactionNotFoundError,
)
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.transaction import (
    TransactionCreate,
    TransactionFilters,
    TransactionResponse,
    TransactionUpdate,
    TransactionWithCategoryResponse,
)
from app.services.transaction import TransactionService

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[TransactionResponse])
async def list_transactions(
    filters: TransactionFilters = Depends(),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> PaginatedResponse[TransactionResponse]:
    """List transactions for the authenticated user with filtering and pagination."""
    transaction_service = TransactionService(db)

    items, total = await transaction_service.get_filtered(
        current_user.id,
        filters,
        offset=pagination.offset,
        limit=pagination.per_page,
    )

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )


@router.post(
    "/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED
)
async def create_transaction(
    data: TransactionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> TransactionResponse:
    """Create a new transaction."""
    transaction_service = TransactionService(db)
    try:
        return await transaction_service.create(data, current_user.id)
    except CategoryNotFoundError as e:
        raise e
    except AccessDeniedError as e:
        raise e


@router.get("/{transaction_id}", response_model=TransactionWithCategoryResponse)
async def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> TransactionResponse:
    """Get a specific transaction by ID, including category details."""
    transaction_service = TransactionService(db)
    try:
        return await transaction_service.get_by_id_with_category(
            transaction_id,
            current_user.id,
        )
    except TransactionNotFoundError as e:
        raise e
    except AccessDeniedError as e:
        raise e


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> TransactionResponse:
    """Update a transaction."""
    transaction_service = TransactionService(db)
    try:
        return await transaction_service.update(
            transaction_id,
            data,
            current_user.id,
        )
    except TransactionNotFoundError as e:
        raise e
    except CategoryNotFoundError as e:
        raise e
    except AccessDeniedError as e:
        raise e


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> None:
    """Delete a transaction (soft delete)."""
    transaction_service = TransactionService(db)
    try:
        await transaction_service.soft_delete(transaction_id, current_user.id)
    except TransactionNotFoundError as e:
        raise e
    except AccessDeniedError as e:
        raise e
