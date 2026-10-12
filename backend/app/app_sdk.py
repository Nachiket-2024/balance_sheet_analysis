"""
App-specific extension surface (see docs/mystic_auth/template-usage/overview.md).

Counterpart to sdk.py: sdk.py re-exports the template's own building blocks
and isn't meant to be hand-edited. This file is where a project built on the
template adds its own re-exports and startup registrations for its own domain
code, so template updates never conflict with app-specific additions here.

Ships empty upstream on purpose, so it never conflicts on a
`scripts/mystic_auth/upstream-sync/sync-upstream.sh` sync. If a sync ever shows a change to this file
coming from upstream anyway, keep YOUR version: upstream's is only ever the
empty starting point.

Add your own imports/exports below as your app grows.

Deliberately holds ONLY mystic_auth re-exports, not this app's own routers,
since this app's own models import `Base` from here, and main.py imports the
app's routers directly from their route modules. Re-exporting those routers
would make this module a dependency of the models and a dependent of them,
creating a circular import.
"""

import importlib

# Same dual-context problem sdk.py's own docstring explains (this module is
# imported both as `backend.app.app_sdk` from the repo root, e.g. by tests,
# and as `app.app_sdk` inside the Docker image, where cwd is backend/),
# resolved the same way, independently of sdk.py, so this file never depends
# on sdk.py's internals to reach mystic_auth.
_pkg_parent = __package__.rsplit(".", 1)[0] if __package__ and "." in __package__ else ""
_mystic_auth_root = f"{_pkg_parent}.mystic_auth" if _pkg_parent else "mystic_auth"


def _m(path: str):
    return importlib.import_module(f"{_mystic_auth_root}.{path}")


# ---------------------------- mystic_auth internals this app needs beyond sdk.py ----------------------------

# Needed by app/access/scope.py to derive a *list*-scoping SQL filter from a
# user's own assigned policy conditions (company_id/group_root_id): cheaper
# than one authorization_service.authorize() call per row when listing many
# companies/balance sheets. See app/access/scope.py's own docstring.
policy_repository = _m("authorization.repositories.policy_repository").policy_repository

# The shared declarative base: this app's own models (company_model.py,
# balance_sheet_model.py) inherit from THIS Base, not a new one of their own,
# so a single alembic env.py/metadata covers both mystic_auth's and this
# app's tables in one migration history (see backend/alembic/env.py).
Base = _m("database.base").Base

# Used to rate-limit this app's own cost-sensitive endpoints (LLM chat calls
# Groq per request; balance-sheet import calls yfinance), see
# api/llm_routes/llm_routes.py and api/balance_sheet_routes/balance_sheet_routes.py.
# mystic_auth's own routes use this for login/signup/etc.; nothing about it
# is auth-specific, so reusing it here avoids a second Redis-backed rate
# limiter implementation.
rate_limiter_service = _m("auth.security.rate_limiting.rate_limiter_service").rate_limiter_service

# Needed only by app/seed/seed_demo_data.py to create demo users with real
# hashed passwords and role assignments through mystic_auth's own user
# creation path, rather than inserting rows by hand.
password_service = _m("auth.password_logic.password_service").password_service
user_crud = _m("user.user_crud_collector").user_crud

# Downstream notification code uses the template's existing email task
# through this extension surface instead of importing template internals.
send_email_task = _m("procrastinate_tasks.email_tasks").send_email_task

__all__ = [
    "policy_repository",
    "Base",
    "rate_limiter_service",
    "password_service",
    "user_crud",
    "send_email_task",
]


def register_extensions() -> None:
    """Register downstream condition handlers before requests are served."""
    # This app currently has no custom MysticAuth condition handlers.
