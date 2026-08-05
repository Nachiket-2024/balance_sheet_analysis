"""
Seeds this app's own baseline RBAC-shaped policies: unconditioned, so they
apply to every company (see docs/mystic_auth/authorization/rbac-quickstart.md:
"a policy with no conditions at all is already RBAC"). This is what lets a
fresh install be usable right away: sign up, get a policy assigned by an
admin, pick a company name, import from yfinance, with no one having to
hand-author a conditions JSON block first. Company/group-scoped policies
(the actual PBAC conditions, e.g. "only this subsidiary") remain something
you build on top of this, following the same shape (see docs/app/access-control/overview.md).

Runs automatically on every `docker compose up` (see the seed-base-policies
service in docker-compose.yml, same pattern as the alembic service running
migrations), not interactive, not something you're expected to run by hand.
Idempotent by name, like seed_demo_data.py: safe to run on every boot.

Deliberately does NOT create or assign to any user; see seed_demo_data.py
for disposable fake companies/users/scoped-policies to explore the full
hierarchy-scoping model instead. This script only makes the two ready-to-
assign role policies below exist so an admin can grant one from the Users/
Policies UI immediately.

Idempotent by name, not by content: if BASE_POLICIES below changes (a new
action added to an existing role, say), an already-seeded database keeps
the old action list, since a match by name is treated as "already done" and
skipped entirely. Edit the policy directly from the `/policies` UI (or
delete the row and rerun this script) to pick up a changed definition on an
existing install.
"""

import asyncio

from ..access.permissions import (
    BALANCE_SHEET_DELETE,
    BALANCE_SHEET_IMPORT,
    BALANCE_SHEET_READ,
    COMPANY_CREATE,
    COMPANY_DELETE,
    COMPANY_READ,
    COMPANY_UPDATE,
    LLM_CHAT,
)
from ..app_sdk import policy_repository
from ..sdk import database

# name -> (description, actions): one unconditioned policy per role, per
# the RBAC Quickstart recipe. resource_type "*" since both roles span
# company/balance_sheet/llm actions in one policy (see seed_demo_data.py's
# identical choice for why: those three share the same condition keys).
BASE_POLICIES: dict[str, tuple[str, list[str]]] = {
    "role_company_viewer": (
        "Read-only access to every company: view companies, view balance sheets, chat with the LLM.",
        [COMPANY_READ, BALANCE_SHEET_READ, LLM_CHAT],
    ),
    "role_company_manager": (
        "Full access to every company: everything role_company_viewer has, plus create/edit/delete companies "
        "and import/delete balance sheet data.",
        [
            COMPANY_READ,
            COMPANY_CREATE,
            COMPANY_UPDATE,
            COMPANY_DELETE,
            BALANCE_SHEET_READ,
            BALANCE_SHEET_IMPORT,
            BALANCE_SHEET_DELETE,
            LLM_CHAT,
        ],
    ),
}


async def seed_base_policies() -> None:
    async for db in database.get_session():
        for name, (description, actions) in BASE_POLICIES.items():
            existing = await policy_repository.get_by_name(name, db)
            if existing is not None:
                print(f"  already exists: {name}")
                continue
            await policy_repository.create(
                {
                    "name": name,
                    "description": description,
                    "actions": actions,
                    "resource_type": "*",
                    "conditions": {},
                    "is_active": True,
                },
                db,
                changed_by="system_seed",
            )
            print(f"  created policy: {name}")
        return


if __name__ == "__main__":
    asyncio.run(seed_base_policies())
