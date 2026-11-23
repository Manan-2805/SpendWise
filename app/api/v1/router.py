from fastapi import APIRouter

from app.api.responses import OVERLOAD_RESPONSES
from app.api.v1.endpoints import auth, categories, health, reports, transactions, users

api_v1_router = APIRouter()

api_v1_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
    responses=OVERLOAD_RESPONSES,
)

api_v1_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"],
    responses=OVERLOAD_RESPONSES,
)

api_v1_router.include_router(
    categories.router,
    prefix="/categories",
    tags=["Categories"],
    responses=OVERLOAD_RESPONSES,
)

api_v1_router.include_router(
    transactions.router,
    prefix="/transactions",
    tags=["Transactions"],
    responses=OVERLOAD_RESPONSES,
)

api_v1_router.include_router(
    reports.router,
    prefix="/reports",
    tags=["Reports"],
    responses=OVERLOAD_RESPONSES,
)

api_v1_router.include_router(
    health.router,
    tags=["Health"],
)
