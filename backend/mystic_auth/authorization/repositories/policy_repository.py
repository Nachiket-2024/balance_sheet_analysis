from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...user_table.user_model import User

# The one centralized Redis abstraction for authorization data, see its own
# docstring for exactly what is (and deliberately isn't) cached, and why.
# Every mutation below invalidates whatever it could have made stale.
from ..caching.authorization_cache_service import authorization_cache_service
from ..models.policy_model import Policy, UserPolicy

# Every create/update/delete below also stages a policy_history row in the
# same transaction, policy versioning writes history rows in the same transaction:
# every policy mutation must be traceable and reversible.
from .policy_history_repository import policy_history_repository


def _definition_snapshot(policy: Policy) -> dict:
    """
    The versioned "definition" of a policy: everything that determines
    what it grants, for policy_history's previous_definition/
    new_definition columns. Deliberately excludes id/timestamps: those
    identify *which row*, not *what it currently grants*, and would make
    every history diff spuriously include updated_at.
    """
    return {
        "name": policy.name,
        "description": policy.description,
        "actions": list(policy.actions) if policy.actions else [],
        "resource_type": policy.resource_type,
        "conditions": policy.conditions,
        "is_active": policy.is_active,
    }


class PolicyRepository:
    """
    Persistence layer for policies and user<->policy assignments. This is
    the only place that issues queries against the policies/user_policies
    tables: evaluators and services call through here rather than building
    their own queries, so the schema/query shape only needs to change in
    one place.

    Policies are looked up by name throughout the app (routes take a
    human-readable policy_name, never a numeric id), so there is no
    get_by_id; add one if/when a caller actually needs id-based lookup.

    create/update/delete each stage a policy_history row (via
    policy_history_repository.add_entry) alongside their own mutation and
    commit both in the same transaction, so a history entry can never
    exist without the change it describes actually having been persisted,
    or vice versa.
    """

    @staticmethod
    async def create(data: dict, db: AsyncSession, changed_by: str | None = None) -> Policy:
        policy = Policy(**data)
        db.add(policy)
        await db.flush()  # assign policy.id without ending the transaction

        policy_history_repository.add_entry(
            {
                "policy_id": policy.id,
                "policy_name": policy.name,
                "change_type": "created",
                "previous_definition": None,
                "new_definition": _definition_snapshot(policy),
                "changed_fields": None,
                "changed_by": changed_by,
                "change_reason": None,
            },
            db,
        )

        await db.commit()
        await db.refresh(policy)
        return policy

    @staticmethod
    async def get_by_name(name: str, db: AsyncSession) -> Policy | None:
        result = await db.execute(select(Policy).where(Policy.name == name))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db: AsyncSession, limit: int = 1000, offset: int = 0) -> list[Policy]:
        # Capped: every other list endpoint in the app (audit log, policy
        # history) bounds its query the same way; this one previously read
        # the whole table unconditionally.
        stmt = select(Policy).order_by(Policy.id).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db_obj: Policy,
        update_data: dict,
        db: AsyncSession,
        changed_by: str | None = None,
        change_reason: str | None = None,
        change_type: str = "updated",
    ) -> Policy:
        """
        `change_type` is "updated" for a normal edit, or "rolled_back" when
        this call is restoring a prior version (see
        api/pbac_routes/policy_history_routes.py's rollback endpoint); the
        only difference is how the resulting
        history entry is labeled; the mutation logic is identical either
        way, so rollback reuses this method rather than duplicating it.
        """
        previous_definition = _definition_snapshot(db_obj)

        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        await db.flush()

        new_definition = _definition_snapshot(db_obj)
        changed_fields = [
            field for field in update_data
            if previous_definition.get(field) != new_definition.get(field)
        ]

        # A no-op update (nothing actually differs) still gets a history
        # entry: the caller explicitly asked for this change, and an
        # empty changed_fields list is itself meaningful information
        # (e.g. rolling back to a version identical to the current one).
        policy_history_repository.add_entry(
            {
                "policy_id": db_obj.id,
                "policy_name": db_obj.name,
                "change_type": change_type,
                "previous_definition": previous_definition,
                "new_definition": new_definition,
                "changed_fields": changed_fields,
                "changed_by": changed_by,
                "change_reason": change_reason,
            },
            db,
        )

        await db.commit()
        await db.refresh(db_obj)

        # This policy's definition changed: every user who holds it may
        # now have a stale cached effective-policy set (see
        # AuthorizationCacheService.invalidate_all_user_policies's own
        # docstring for why this is a full-namespace flush rather than a
        # targeted one).
        await authorization_cache_service.invalidate_all_user_policies()

        return db_obj

    @staticmethod
    async def delete(
        db_obj: Policy,
        db: AsyncSession,
        changed_by: str | None = None,
        change_reason: str | None = None,
    ) -> None:
        previous_definition = _definition_snapshot(db_obj)

        policy_history_repository.add_entry(
            {
                "policy_id": db_obj.id,
                "policy_name": db_obj.name,
                "change_type": "deleted",
                "previous_definition": previous_definition,
                "new_definition": None,
                "changed_fields": None,
                "changed_by": changed_by,
                "change_reason": change_reason,
            },
            db,
        )

        await db.delete(db_obj)
        await db.commit()

        # See update()'s own comment: deleting a policy can strand every
        # holder's cached effective-policy set just as editing one can.
        await authorization_cache_service.invalidate_all_user_policies()

    @staticmethod
    async def get_active_policies_for_user(user_email: str, db: AsyncSession) -> list[Policy]:
        """
        The query the authorization/evaluation path actually runs: every
        *active* policy assigned to the user with this email. Filtering
        is_active here (rather than in the evaluator) keeps a disabled
        policy from ever reaching evaluation at all.

        Cache-aside: this is the one authorization-hot-path query cached
        by AuthorizationCacheService (see its docstring for exactly what's
        cached and why); checked first; on a miss (or any cache failure),
        falls through to the database and populates the cache for next
        time. A cache read failure is indistinguishable from a miss here
        by design (see AuthorizationCacheService's "fail closed" note).
        """
        cached = await authorization_cache_service.get_user_policies(user_email)
        if cached is not None:
            return cached

        stmt = (
            select(Policy)
            .join(UserPolicy, UserPolicy.policy_id == Policy.id)
            .join(User, User.id == UserPolicy.user_id)
            .where(User.email == user_email, Policy.is_active.is_(True))
        )
        result = await db.execute(stmt)
        policies = list(result.scalars().all())

        await authorization_cache_service.set_user_policies(user_email, policies)
        return policies

    @staticmethod
    async def get_policies_for_user(user_email: str, db: AsyncSession) -> list[Policy]:
        """Every assigned policy (active or not): for inspection/listing,
        not for making an authorization decision (use
        get_active_policies_for_user for that)."""
        stmt = (
            select(Policy)
            .join(UserPolicy, UserPolicy.policy_id == Policy.id)
            .join(User, User.id == UserPolicy.user_id)
            .where(User.email == user_email)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def count_assignments(policy_id: int, db: AsyncSession) -> int:
        """
        How many users currently hold this policy (assigned, regardless of
        the policy's own is_active flag). Used by
        api/pbac_routes/policy_assignment_routes.py's revoke endpoint to refuse removing the
        last remaining holder of system_superuser, see the
        "System policies are protected": deleting a policy row is already
        blocked for baseline policies, but *revoking every assignment* of
        system_superuser would leave the system equally unrecoverable
        (no one left able to manage policies at all).
        """
        result = await db.execute(
            select(UserPolicy).where(UserPolicy.policy_id == policy_id)
        )
        return len(result.scalars().all())

    @staticmethod
    async def assign_policy_to_user(
        user_id: int,
        policy_id: int,
        db: AsyncSession,
        assigned_by: str | None = None,
        user_email: str | None = None,
    ) -> UserPolicy:
        """
        `assigned_by` is the email of the admin making the assignment, or
        "system" for automated assignment (e.g. default policy at signup),
        for the audit trail.

        `user_email` is the receiving user's email, if the caller has it:
        used only to precisely invalidate that user's cached effective-
        policy set (see AuthorizationCacheService). Optional and backward
        compatible: system-side self-assignment at signup/OAuth2/system-
        user-bootstrap doesn't pass it, since a brand-new user has nothing
        cached yet to invalidate anyway; the admin-facing assign route
        (api/pbac_routes/policy_assignment_routes.py) does pass it, since that target user may
        already have a populated cache entry.

        Idempotent: assigning an already-held policy is a no-op, returning
        the existing assignment rather than raising a duplicate-key error.
        """
        existing = await db.execute(
            select(UserPolicy).where(
                UserPolicy.user_id == user_id, UserPolicy.policy_id == policy_id
            )
        )
        existing_row = existing.scalar_one_or_none()
        if existing_row:
            return existing_row

        assignment = UserPolicy(user_id=user_id, policy_id=policy_id, assigned_by=assigned_by)
        db.add(assignment)
        await db.commit()
        await db.refresh(assignment)

        if user_email is not None:
            await authorization_cache_service.invalidate_user_policies(user_email)

        return assignment

    @staticmethod
    async def remove_policy_from_user(
        user_id: int, policy_id: int, db: AsyncSession, user_email: str | None = None
    ) -> bool:
        """
        `user_email` is optional, used only for precise cache invalidation
        see assign_policy_to_user's own docstring. Returns True if an
        assignment was found and removed, False if the user didn't hold
        this policy to begin with.
        """
        result = await db.execute(
            select(UserPolicy).where(
                UserPolicy.user_id == user_id, UserPolicy.policy_id == policy_id
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            return False

        await db.delete(assignment)
        await db.commit()

        if user_email is not None:
            await authorization_cache_service.invalidate_user_policies(user_email)

        return True


policy_repository = PolicyRepository()
