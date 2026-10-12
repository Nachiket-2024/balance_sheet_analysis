from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.policy_model import Policy, UserPolicy
from ..models.user_permission_model import UserPermission
from ..permissions_catalog import PERMISSION_CATALOG
from ..schemas.permission_schema import PermissionUsageEntryRead, PermissionUsagePolicyRead


@dataclass
class _ActionUsage:
    """Accumulator keyed by action while the two source tables are folded
    together in Python (see get_usage_by_action) - never returned itself,
    only used to build the PermissionUsageEntryRead list."""

    policy_names: list[str] = field(default_factory=list)
    policy_user_ids: dict[str, set[int]] = field(default_factory=dict)  # policy name -> user ids
    direct_user_ids: set[int] = field(default_factory=set)


class PermissionUsageRepository:
    """Read-only "who holds this action" summary, folding Policy/UserPolicy
    and UserPermission together per catalog action. No single SQL query
    does this cleanly (a user can reach the same action through more than
    one policy, and deduping across policy + direct grants needs the raw
    user ids, not pre-aggregated counts), so this fetches the small set of
    active policies/assignments/grants and aggregates in Python instead.
    Safe at this app's scale: the permission catalog is a few dozen fixed
    actions (see permissions_catalog.py), not a per-tenant-defined one that
    could grow unbounded.
    """

    @staticmethod
    async def get_usage_by_action(db: AsyncSession) -> dict[str, PermissionUsageEntryRead]:
        usage: dict[str, _ActionUsage] = {}

        policy_rows = (
            await db.execute(select(Policy.id, Policy.name, Policy.actions).where(Policy.is_active.is_(True)))
        ).all()

        policy_user_ids: dict[int, set[int]] = {}
        if policy_rows:
            policy_ids = [policy_row.id for policy_row in policy_rows]
            assignment_rows = (
                await db.execute(
                    select(UserPolicy.policy_id, UserPolicy.user_id).where(UserPolicy.policy_id.in_(policy_ids))
                )
            ).all()
            for assignment_row in assignment_rows:
                policy_user_ids.setdefault(assignment_row.policy_id, set()).add(assignment_row.user_id)

        for policy_row in policy_rows:
            user_ids = policy_user_ids.get(policy_row.id, set())
            for action in policy_row.actions:
                accum = usage.setdefault(action, _ActionUsage())
                accum.policy_names.append(policy_row.name)
                accum.policy_user_ids[policy_row.name] = user_ids

        direct_rows = (
            await db.execute(
                select(UserPermission.action, UserPermission.user_id).where(UserPermission.is_active.is_(True))
            )
        ).all()
        for direct_row in direct_rows:
            usage.setdefault(direct_row.action, _ActionUsage()).direct_user_ids.add(direct_row.user_id)

        result: dict[str, PermissionUsageEntryRead] = {}
        for entry in PERMISSION_CATALOG:
            accum = usage.get(entry.action, _ActionUsage())
            all_policy_user_ids: set[int] = set()
            for ids in accum.policy_user_ids.values():
                all_policy_user_ids |= ids
            result[entry.action] = PermissionUsageEntryRead(
                action=entry.action,
                resource_type=entry.resource_type,
                policies=[
                    PermissionUsagePolicyRead(name=name, user_count=len(accum.policy_user_ids[name]))
                    for name in sorted(set(accum.policy_names))
                ],
                policy_user_count=len(all_policy_user_ids),
                direct_grant_count=len(accum.direct_user_ids),
                total_user_count=len(all_policy_user_ids | accum.direct_user_ids),
            )
        return result


permission_usage_repository = PermissionUsageRepository()
