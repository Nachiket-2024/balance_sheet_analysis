import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parent.parent.parent
_ = load_dotenv(dotenv_path=BASE_DIR / ".env")

# App routers import directly from their modules to avoid an app_sdk.py cycle.
# Their models depend on app_sdk.Base, so app_sdk.py cannot also import them.
from .api.balance_sheet_routes import balance_sheet_routes  # noqa: E402 (must follow load_dotenv() above)
from .api.company_routes import company_routes  # noqa: E402
from .api.llm_routes import llm_routes  # noqa: E402
from .sdk import (  # noqa: E402 (must follow load_dotenv() above, since sdk.py reads env-dependent settings at import time)
    CorrelationIdMiddleware,
    LoggingMiddleware,
    SecurityHeadersMiddleware,
    auth_router,
    authorization_check_router,
    capture_exception,
    database,
    get_logger,
    health_router,
    init_sentry,
    pbac_audit_log_router,
    policy_assignment_router,
    policy_crud_router,
    policy_history_router,
    redis_client,
    refresh_token_router,
    security_audit_router,
    settings,
    user_lifecycle_router,
    user_management_query_router,
    user_management_update_router,
    user_self_service_router,
    watch_for_late_dsn,
)

balance_sheet_router = balance_sheet_routes.router
company_router = company_routes.router
llm_router = llm_routes.router

logger = get_logger("main")

# Before the app starts serving requests, so every request from the very
# first one onward is covered. A no-op when SENTRY_DSN is unset (see
# error_monitoring/sentry_service.py and docs/mystic_auth/error-monitoring/overview.md).
init_sentry()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """
    Starts watch_for_late_dsn() as a fire-and-forget background task, a
    no-op unless init_sentry() above ran with SENTRY_DSN still unset (see
    that function's own docstring for why: Bugsink can take longer to
    become healthy than this app takes to boot, on a fresh/cold start).
    Never awaited, so it can't delay startup or block a single request;
    cancelled on shutdown along with everything else.

    On shutdown (SIGTERM from `docker stop` / orchestrator rolling
    restarts) explicitly dispose the DB connection pool and close the Redis
    client instead of relying on the process dying and the OS reclaiming
    the sockets.
    """
    dsn_watcher = asyncio.create_task(watch_for_late_dsn())
    yield
    dsn_watcher.cancel()
    await database.engine.dispose()
    await redis_client.aclose()


# In production, the interactive API docs are disabled since they're a debugging
# aid with no reason to be publicly reachable, and disabling them is one less
# thing to lock down at a proxy.
_is_production = settings.ENVIRONMENT.lower() == "production"
app = FastAPI(
    lifespan=lifespan,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

# Starlette applies middleware in reverse add order. Add CorrelationIdMiddleware
# last so request IDs exist before LoggingMiddleware logs the incoming request.

# Settings build the allowed CORS origins for local, staging, and production.
# Redirect and email links still use only FRONTEND_BASE_URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
    # Custom response headers are invisible to browser JS by default even
    # when the request itself succeeds; without this, X-Total-Count (see
    # list_all_users) is present on the wire but unreadable via axios.
    expose_headers=["X-Total-Count"],
)

app.add_middleware(LoggingMiddleware)

# Security-hardening response headers (X-Frame-Options, CSP, HSTS, etc.), see
# security_headers_middleware.py for per-header reasoning.
app.add_middleware(SecurityHeadersMiddleware)

# Added last so it becomes outermost (see note above).
app.add_middleware(CorrelationIdMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled Exception at {request.url.path}: {str(exc)}")
    await capture_exception(exc, request=request)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


app.include_router(auth_router)
app.include_router(refresh_token_router)
# Split from a single user_routes.py into user_self_service_routes.py (GET/PUT
# /users/me, no elevated permission) and, by operation type, user_management_query_routes.py
# (users:list_all/stats), user_management_update_routes.py (update_any/assign_role),
# and user_lifecycle_routes.py (delete_any/purge/reactivate) - all gated
# accordingly, see backend/mystic_auth/api/user_routes/. Registration order
# matters here: the self-service router must come first, since the management
# routers' PUT /users/{user_email} would otherwise shadow PUT /users/me
# (Starlette matches routes in registration order across the whole app, not
# per-router) - the same hazard policy_assignment_router's own
# /me-before-{email} ordering below guards against within a single router.
app.include_router(user_self_service_router)
app.include_router(user_management_query_router)
app.include_router(user_management_update_router)
app.include_router(user_lifecycle_router)
# Split from a single pbac_routes/policy_routes.py into feature-based modules
# (CRUD, history, assignment, checks, audit log), see backend/mystic_auth/api/pbac_routes/.
# Registration order matters: policy_assignment_router defines
# /authorization/users/me/policies before its own
# /authorization/users/{user_email}/policies, so it must be included whole;
# no other cross-router ordering constraint exists since each router owns a
# disjoint set of paths.
app.include_router(policy_crud_router)
app.include_router(policy_history_router)
app.include_router(policy_assignment_router)
app.include_router(authorization_check_router)
app.include_router(pbac_audit_log_router)
app.include_router(security_audit_router)
app.include_router(health_router)

# App-owned domain routers. Keep separate from template routers for sync review.
app.include_router(company_router)
app.include_router(balance_sheet_router)
app.include_router(llm_router)


@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.APP_NAME}!"}
