"""
Company-hierarchy scoping for this app's PBAC checks.

mystic-auth's PBAC evaluates a Policy's `resource_attributes` condition as
flat equality against fields on the resource passed to authorize()/require()
(see docs/mystic_auth/authorization/condition-schema-reference.md); there is
no built-in "any descendant of X" traversal. To model "a CEO sees only their
company" and "a group executive sees their whole group" on top of that, every
policy we seed for this app's resources (company/balance_sheet/llm) uses one
of exactly two condition shapes:

    {"resource_attributes": {"company_id": <id>}}       # scoped to one company
    {"resource_attributes": {"group_root_id": <id>}}     # scoped to a whole group
    (absent/empty conditions)                            # unrestricted (e.g. admin)

`group_root_id` is a denormalized column on Company (see company_model.py):
the top-most ancestor's id, so "every company in Reliance's group" is a flat
equality on one column instead of a recursive parent_company_id walk.

Every resource we ever pass to authorization_service.authorize()/.require()
for these resource types is built via resource_scope_dict() below, so the
same two condition keys work identically whether the resource being checked
is a Company itself, a BalanceSheet row, or an LLM chat request about a
company, so the evaluator never needs resource-type-specific condition logic.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from ..app_sdk import policy_repository


def resource_scope_dict(company_id: int, group_root_id: int) -> dict:
    """The `resource=` payload passed to every authorize()/require() call
    for a company-scoped resource, see module docstring."""
    return {"company_id": company_id, "group_root_id": group_root_id}


@dataclass
class CompanyScope:
    """The result of collapsing a user's assigned policies into a
    list-filtering rule for one (action, resource_type) pair."""

    unrestricted: bool
    company_ids: frozenset[int]
    group_root_ids: frozenset[int]

    def is_empty(self) -> bool:
        """True if this scope grants access to nothing at all. The caller
        should short-circuit to an empty result rather than run a query."""
        return not self.unrestricted and not self.company_ids and not self.group_root_ids


async def get_company_scope(
    user_email: str, action: str, resource_type: str, db: AsyncSession
) -> CompanyScope:
    """
    Derives which companies `user_email` may `action` on `resource_type` for,
    directly from their own active policies' conditions. Used to build a
    single SQL filter for LIST endpoints (see companies/company_crud.py,
    balance_sheets/balance_sheet_crud.py), instead of one
    authorization_service.authorize() call per candidate row (which would
    also write one PBAC audit-log entry per row on every list request).

    Single-resource GET/POST/DELETE endpoints do NOT use this: they fetch
    the specific row first and call authorization_service.require(...,
    resource=resource_scope_dict(...)) directly, so exactly one audit entry
    is written per real access to a specific resource.
    """
    policies = await policy_repository.get_active_policies_for_user(user_email, db)

    unrestricted = False
    company_ids: set[int] = set()
    group_root_ids: set[int] = set()

    for policy in policies:
        if policy.resource_type not in (resource_type, "*"):
            continue
        if action not in (policy.actions or []):
            continue

        resource_attrs = (policy.conditions or {}).get("resource_attributes")
        if not resource_attrs:
            unrestricted = True
            continue

        if "company_id" in resource_attrs:
            company_ids.add(resource_attrs["company_id"])
        if "group_root_id" in resource_attrs:
            group_root_ids.add(resource_attrs["group_root_id"])

    return CompanyScope(
        unrestricted=unrestricted,
        company_ids=frozenset(company_ids),
        group_root_ids=frozenset(group_root_ids),
    )
