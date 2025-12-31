"""API v1 router aggregator."""

from fastapi import APIRouter

from src.api.v1.endpoints import auth, documents, queries, agents, health, dashboard, roles, feedback, search, analytics, versions, knowledge_graph, collaboration

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

api_router.include_router(
    feedback.router,
    prefix="/feedback",
    tags=["feedback"],
)

api_router.include_router(
    search.router,
    prefix="/search",
    tags=["search"],
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"],
)

api_router.include_router(
    versions.router,
    tags=["versions"],
)

api_router.include_router(
    knowledge_graph.router,
    tags=["knowledge-graph"],
)

api_router.include_router(
    collaboration.router,
    tags=["collaboration"],
)