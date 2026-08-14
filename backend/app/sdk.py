"""
Public extension surface for domain/feature code built on top of this
template (see docs/mystic_auth/template-usage/overview.md).

Import from HERE, not internal paths like
`mystic_auth.authorization.dependencies.authorization_dependency` directly:
one file to discover what's available, and one file to reconcile when
pulling in upstream template updates instead of every call site.

`main.py` itself is held to the same rule: it imports only from this module,
never reaching into `mystic_auth/` directly, so the app's entry point and any
downstream app code share one boundary.

Everything below is a straight re-export; see the original module's
docstring for the "why" behind any given piece.

DO NOT hand-edit this file. Treat it as a drop-in you receive from upstream,
not a place to add your own re-exports: this is the one file a
`scripts/sync-upstream.sh` sync is expected to touch, and local edits here
are exactly what turns that sync into a manual conflict instead of applying
cleanly. If you need your own re-exports for your own domain code, add
them to app_sdk.py instead: it's the counterpart file kept empty by
upstream for exactly this purpose, so it never conflicts on a sync.
"""

import importlib

# `mystic_auth` is a sibling package of `app`, not a child of it, so a plain
# relative import can't reach it, and a plain absolute one only resolves
# inside the Docker image, where the working directory is backend/ and
# `app`/`mystic_auth` are both top-level packages. The test suite instead
# runs from the repo root and imports this module as `backend.app.sdk`,
# where the only importable name is `backend.mystic_auth...`. Deriving the
# right prefix from __package__ (rather than hardcoding either spelling)
# keeps this file working unchanged in both contexts, and, importantly,
# resolves to the exact same module objects (the same `database`/`settings`/
# etc. singletons) the rest of whichever context is already running, rather
# than a second, separately-imported copy. That matters concretely:
# tests/backend/conftest.py imports `database` directly via
# `backend.mystic_auth.database.connection` and mutates `database.engine` on
# that object, expecting the app under test (imported here through
# `backend.app.main` -> `backend.app.sdk`) to see the same mutated instance.
_pkg_parent = __package__.rsplit(".", 1)[0] if __package__ and "." in __package__ else ""
_mystic_auth_root = f"{_pkg_parent}.mystic_auth" if _pkg_parent else "mystic_auth"


def _m(path: str):
    return importlib.import_module(f"{_mystic_auth_root}.{path}")


# PBAC, see docs/mystic_auth/authorization/architecture.md
Permission = _m("authorization.permissions").Permission
require_authorization = _m("authorization.dependencies.authorization_dependency").require_authorization
authorization_service = _m("authorization.services.authorization_service").authorization_service
build_authorization_context = _m("authorization.context.request_context_builder").build_authorization_context

# Authentication, see docs/mystic_auth/authentication/overview.md
get_current_user = _m("auth.current_user.current_user_dependency").get_current_user
SecurityHeadersMiddleware = _m("auth.security.security_headers_middleware").SecurityHeadersMiddleware

# Database: Depends(database.get_session) in a route signature
database = _m("database.connection").database
# Settings: add your own fields to Settings in core/settings.py, read them
# from here rather than os.environ directly
settings = _m("core.settings").settings

# Small route helpers
get_or_404 = _m("api.get_or_404.get_or_404").get_or_404

# Machine-readable error codes for frontend translation, see
# docs/mystic_auth/translations/overview.md
AppError = _m("core.errors").AppError

# Routers, mounted on the FastAPI app in main.py
auth_router = _m("api.auth_routes.auth_routes").router
refresh_token_router = _m("api.auth_routes.refresh_token_routes").router
user_self_service_router = _m("api.user_routes.user_self_service_routes").router
user_management_query_router = _m("api.user_routes.user_management_query_routes").router
user_management_update_router = _m("api.user_routes.user_management_update_routes").router
user_lifecycle_router = _m("api.user_routes.user_lifecycle_routes").router
policy_crud_router = _m("api.pbac_routes.policy_crud_routes").router
policy_history_router = _m("api.pbac_routes.policy_history_routes").router
policy_assignment_router = _m("api.pbac_routes.policy_assignment_routes").router
authorization_check_router = _m("api.pbac_routes.authorization_check_routes").router
pbac_audit_log_router = _m("api.pbac_routes.pbac_audit_log_routes").router
security_audit_router = _m("api.audit_log_routes.audit_log_routes").router
health_router = _m("api.health_routes.health_routes").router

# Display/grouping metadata only, never a gating decision, see
# docs/mystic_auth/security/decisions.md#role-is-never-used-to-decide-access
UserRole = _m("user_table.user_model").UserRole

# Redis client singleton, closed on shutdown in main.py's lifespan
redis_client = _m("redis.client").redis_client

# Logging/observability middleware and helpers, wired up in main.py
LoggingMiddleware = _m("logging.logging_middleware").LoggingMiddleware
CorrelationIdMiddleware = _m("logging.correlation_id_middleware").CorrelationIdMiddleware
get_logger = _m("logging.logging_config").get_logger

# Error monitoring: init_sentry() is called once at import time in
# main.py; capture_exception() reports a caught-but-still-noteworthy
# exception the same way an unhandled one gets reported automatically. Both
# are safe no-ops when SENTRY_DSN is unset, see
# docs/mystic_auth/error-monitoring/overview.md.
# watch_for_late_dsn() is started as a background task from main.py's
# lifespan. It catches Bugsink's DSN on a slow/fresh boot, running after
# init_sentry() already ran and found nothing set. See its own docstring
# for why that's not a redundant second attempt at the same check.
_sentry_service = _m("error_monitoring.sentry_service")
init_sentry = _sentry_service.init_sentry
capture_exception = _sentry_service.capture_exception
watch_for_late_dsn = _sentry_service.watch_for_late_dsn

__all__ = [
    "Permission",
    "require_authorization",
    "authorization_service",
    "build_authorization_context",
    "get_current_user",
    "SecurityHeadersMiddleware",
    "database",
    "settings",
    "get_or_404",
    "AppError",
    "auth_router",
    "refresh_token_router",
    "user_self_service_router",
    "user_management_query_router",
    "user_management_update_router",
    "user_lifecycle_router",
    "policy_crud_router",
    "policy_history_router",
    "policy_assignment_router",
    "authorization_check_router",
    "pbac_audit_log_router",
    "security_audit_router",
    "health_router",
    "UserRole",
    "redis_client",
    "LoggingMiddleware",
    "CorrelationIdMiddleware",
    "get_logger",
    "init_sentry",
    "capture_exception",
    "watch_for_late_dsn",
]
