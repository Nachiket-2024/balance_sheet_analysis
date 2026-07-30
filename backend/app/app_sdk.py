"""
App-specific extension surface (see docs/mystic_auth/template-usage/overview.md).

This is the counterpart to sdk.py: sdk.py re-exports the template's own
building blocks, this file is where a project built on this template adds
its own re-exports for its own domain code, kept separate so template
updates never conflict with app-specific additions here.

Deliberately holds ONLY mystic_auth re-exports, not this app's own routers,
since this app's own models (company_model.py, balance_sheet_model.py) import
`Base` from here, and main.py imports this app's routers directly from their
own modules (companies/company_routes.py etc.) instead of through here.
Re-exporting the routers here too would make this module both a dependency
of the models (via Base) and a dependent of them (via the routers, which
import the models): a real circular import, not just a style choice.
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
rate_limiter_service = _m("auth.security.rate_limiter_service").rate_limiter_service

# Needed only by app/seed/seed_demo_data.py to create demo users with real
# hashed passwords and role assignments through mystic_auth's own user
# creation path, rather than inserting rows by hand.
password_service = _m("auth.password_logic.password_service").password_service
user_crud = _m("user_crud.user_crud_collector").user_crud

__all__ = [
    "policy_repository",
    "Base",
    "rate_limiter_service",
    "password_service",
    "user_crud",
]
