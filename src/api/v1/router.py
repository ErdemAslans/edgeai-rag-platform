"""API v1 router aggregator."""

from fastapi import APIRouter

from src.api.v1.endpoints import auth, documents, queries, agents, health, dashboard, roles

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"],
)

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["dashboard"],
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["authentication"],
)

api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["documents"],
)

api_router.include_router(
    queries.router,
    prefix="/queries",
    tags=["queries"],
)

api_router.include_router(
    agents.router,
    prefix="/agents",
    tags=["agents"],
)

api_router.include_router(
    roles.router,
    prefix="/roles",
    tags=["roles"],
)