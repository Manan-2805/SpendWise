from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    categories,
    transactions,
    users,
)

api_v1_router = APIRouter()

# Each resource's router is included with a prefix and tags
api_v1_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)

api_v1_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"],
)

api_v1_router.include_router(
    categories.router,
    prefix="/categories",
    tags=["Categories"],
)

api_v1_router.include_router(
    transactions.router,
    prefix="/transactions",
    tags=["Transactions"],
)
