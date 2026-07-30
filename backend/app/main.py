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

# This app's own routers, imported directly from their own modules rather
# than through app_sdk.py, to avoid a circular import (see app_sdk.py's own
# docstring): these modules' models need app_sdk.Base, so app_sdk.py can't
# also depend on them. Routes live under api/<feature>_routes/, mirroring
# mystic_auth's own api/ layout (api/auth_routes/, api/pbac_routes/, ...).
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
    user_router,
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

# Starlette applies middleware in reverse of add order: the LAST middleware
# added ends up OUTERMOST, running first on the way in. So
# CorrelationIdMiddleware is added last, making it outermost, so
# request.state.request_id (and the logging contextvar it sets) is populated
# before every other middleware runs, including LoggingMiddleware's "Incoming
# request" log line below.

# Sourced from settings (FRONTEND_BASE_URL + optional
# FRONTEND_ADDITIONAL_BASE_URLS) rather than hardcoded, so this works
# unchanged across local/staging/production instead of only ever allowing
# http://localhost:5173. See Settings.cors_allowed_origins for how the list
# is built. Redirect/email links still always point at FRONTEND_BASE_URL
# alone regardless of how many origins are CORS-allowed here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
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
app.include_router(user_router)
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

# This app's own domain routers (see app_sdk.py): companies, balance
# sheets, LLM chat. Kept as a separate block from the mystic_auth routers
# above so a future template merge only ever touches the block above this.
app.include_router(company_router)
app.include_router(balance_sheet_router)
app.include_router(llm_router)


@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.APP_NAME}!"}
