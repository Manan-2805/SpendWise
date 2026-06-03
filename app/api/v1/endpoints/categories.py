from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.exceptions import CategoryNotFoundError, ConflictError
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.category import CategoryService

router = APIRouter()


@router.get("/", response_model=list[CategoryResponse])
async def list_categories(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryResponse]:
    """List all categories for the authenticated user."""
    category_service = CategoryService(db)
    return await category_service.get_all_for_user(current_user.id)


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    """Create a new category."""
    category_service = CategoryService(db)
    try:
        category: CategoryResponse = await category_service.create(
            data, current_user.id
        )
        return category
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=e.message) from e


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    """Get a specific category by ID."""
    category_service = CategoryService(db)
    try:
        category: CategoryResponse = await category_service.get_by_id(
            category_id, current_user.id
        )
        return category
    except CategoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    """Update a category."""
    category_service = CategoryService(db)
    try:
        category: CategoryResponse = await category_service.update(
            category_id, data, current_user.id
        )
        return category
    except CategoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a category (soft delete)."""
    category_service = CategoryService(db)
    try:
        await category_service.soft_delete(category_id, current_user.id)
    except CategoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
