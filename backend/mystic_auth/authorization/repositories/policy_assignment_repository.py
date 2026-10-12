from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...user.user_model import User

# Centralized Valkey cache for authorization data (see its own docstring
# for what's cached and why). Every mutation below invalidates whatever
# it could have made stale.
from ..caching.authorization_cache_service import authorization_cache_service
from ..models.policy_model import Policy, UserPolicy
from ..schemas.bulk_schema import BulkItemResult


class PolicyAssignmentRepository:
    """User<->policy assignment queries and mutations: which policies a
    user holds, and granting/revoking one. Split out of
    policy_repository.py (which owns policy CRUD), which re-exports every
    method here so existing call sites keep working unchanged."""

    @staticmethod
    async def get_active_policies_for_user(user_email: str, db: AsyncSession) -> list[Policy]:
        """
        The query the evaluation path actually runs: every active policy
        assigned to this user. Filtering is_active here (not in the
        evaluator) keeps a disabled policy from ever reaching evaluation.

        Cache-aside via AuthorizationCacheService: checked first, falls
        through to the database on a miss (or any cache failure, which is
        indistinguishable from a miss by design) and populates the cache.
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
        """How many users currently hold this policy, regardless of the
        policy's own is_active flag. Used by the revoke endpoint to refuse
        removing the last remaining holder of system_superuser: deleting
        the policy row is already blocked, but revoking every assignment
        would leave the system equally unrecoverable."""
        result = await db.execute(
            select(func.count()).select_from(UserPolicy).where(UserPolicy.policy_id == policy_id)
        )
        return result.scalar_one()

    @staticmethod
    async def get_holder_emails(policy_id: int, db: AsyncSession) -> list[str]:
        """Every email currently assigned this policy, regardless of the
        policy's own is_active flag (a holder of a just-deactivated policy
        still needs to be told its access dropped). Used when a policy's
        definition changes, affecting every holder at once rather than a
        single already-known user_email."""
        result = await db.execute(
            select(User.email).join(UserPolicy, UserPolicy.user_id == User.id).where(UserPolicy.policy_id == policy_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_holders(policy_id: int, db: AsyncSession) -> list[dict]:
        """Every user currently assigned this policy, with enough detail
        for the "Assigned users" view (name/email/role) and the delete
        confirm's holder count, newest assignment first. Unlike
        get_holder_emails, this is for display, not for the
        publish_permissions_changed fan-out, so it carries assigned_at/
        assigned_by too."""
        stmt = (
            select(User.email, User.name, User.role, UserPolicy.assigned_at, UserPolicy.assigned_by)
            .join(UserPolicy, UserPolicy.user_id == User.id)
            .where(UserPolicy.policy_id == policy_id)
            .order_by(UserPolicy.assigned_at.desc())
        )
        result = await db.execute(stmt)
        return [
            {
                "email": row.email,
                "name": row.name,
                "role": row.role,
                "assigned_at": row.assigned_at,
                "assigned_by": row.assigned_by,
            }
            for row in result.all()
        ]

    @staticmethod
    async def get_holder_emails_for_update(policy_id: int, db: AsyncSession) -> list[str]:
        """
        Locking counterpart to get_holder_emails: row-locks every current
        UserPolicy assignment of this policy before returning holders.

        Used by the route-level "can't remove the last system_superuser
        assignment" guard: without a lock, two concurrent bulk-remove
        requests targeting different holder subsets could each read the
        same pre-removal count, each pass the guard individually, and
        together strip every assignment (full account lockout). Locking up
        front serializes such requests: the second blocks until the first
        commits, then re-reads the real post-removal holder set.
        """
        result = await db.execute(
            select(User.email)
            .join(UserPolicy, UserPolicy.user_id == User.id)
            .where(UserPolicy.policy_id == policy_id)
            .with_for_update(of=UserPolicy)
        )
        return list(result.scalars().all())

    @staticmethod
    async def assign_policy_to_user(
        user_id: int,
        policy_id: int,
        db: AsyncSession,
        assigned_by: str | None = None,
        user_email: str | None = None,
    ) -> UserPolicy:
        """
        `assigned_by` is the email of the user making the assignment, or
        "system" for automated assignment, for the audit trail.

        `user_email`, if given, precisely invalidates that user's cached
        policy set. Optional: system-side self-assignment at signup
        doesn't pass it (a brand-new user has nothing cached yet), while
        the management-facing assign route does, since that user may
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
    async def user_holds_policy(user_id: int, policy_id: int, db: AsyncSession) -> bool:
        """Whether this user currently holds this policy assignment,
        regardless of the policy's own is_active flag. Checked before the
        system_superuser last-holder lockout, so revoking from a user who
        never held the policy gets a correct 404 instead of being blocked
        by the lockout guard."""
        result = await db.execute(
            select(UserPolicy).where(
                UserPolicy.user_id == user_id, UserPolicy.policy_id == policy_id
            )
        )
        return result.scalar_one_or_none() is not None

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


    @staticmethod
    async def bulk_assign_policies(
        valid_items: list[tuple[User, Policy]], db: AsyncSession, assigned_by: str | None
    ) -> list[BulkItemResult]:
        """
        `valid_items` already passed resolution and the per-item
        privilege-escalation guard in the route layer. Stages writes and
        commits once for the whole batch.

        Idempotent per item, same as assign_policy_to_user: an
        already-held pair adds no duplicate row, reported "already_held".

        The existing_pairs snapshot only rules out pairs already held
        before this call started; it can't see a concurrent request's
        insert of the same pair, so a plain insert can still hit the
        uq_user_policy constraint. Each insert is staged in its own
        SAVEPOINT (db.begin_nested) so a unique-violation resolves to
        "already_held" for just that item, instead of surfacing at the
        final db.commit() and failing the whole transaction, including
        unrelated items that never conflicted with anything.
        """
        if not valid_items:
            return []

        user_ids = {user.id for user, _ in valid_items}
        policy_ids = {policy.id for _, policy in valid_items}
        existing = await db.execute(
            select(UserPolicy.user_id, UserPolicy.policy_id).where(
                UserPolicy.user_id.in_(user_ids), UserPolicy.policy_id.in_(policy_ids)
            )
        )
        existing_pairs = {(uid, pid) for uid, pid in existing.all()}

        results: list[BulkItemResult] = []
        affected_emails: set[str] = set()
        for user, policy in valid_items:
            affected_emails.add(user.email)
            already_held = (user.id, policy.id) in existing_pairs
            if already_held:
                results.append(BulkItemResult(user_email=user.email, identifier=policy.name, status="already_held"))
                continue

            try:
                async with db.begin_nested():
                    db.add(UserPolicy(user_id=user.id, policy_id=policy.id, assigned_by=assigned_by))
                    await db.flush()
            except IntegrityError:
                results.append(BulkItemResult(user_email=user.email, identifier=policy.name, status="already_held"))
                continue

            results.append(BulkItemResult(user_email=user.email, identifier=policy.name, status="success"))

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            return [
                BulkItemResult(user_email=r.user_email, identifier=r.identifier, status="error", error="commit_failed")
                for r in results
            ]

        await authorization_cache_service.invalidate_user_policies_bulk(affected_emails)

        return results

    @staticmethod
    async def bulk_remove_policies(
        valid_items: list[tuple[User, Policy]], db: AsyncSession
    ) -> list[BulkItemResult]:
        """Removal counterpart to bulk_assign_policies. An item whose pair
        isn't actually held is reported as an error (`not_held`), same as
        the single-item route's 404, rather than silently skipped."""
        if not valid_items:
            return []

        user_ids = {user.id for user, _ in valid_items}
        policy_ids = {policy.id for _, policy in valid_items}
        existing = await db.execute(
            select(UserPolicy).where(UserPolicy.user_id.in_(user_ids), UserPolicy.policy_id.in_(policy_ids))
        )
        existing_rows = {(row.user_id, row.policy_id): row for row in existing.scalars().all()}

        results: list[BulkItemResult] = []
        affected_emails: set[str] = set()
        for user, policy in valid_items:
            row = existing_rows.get((user.id, policy.id))
            if row is None:
                results.append(
                    BulkItemResult(user_email=user.email, identifier=policy.name, status="error", error="not_held")
                )
                continue
            await db.delete(row)
            affected_emails.add(user.email)
            results.append(BulkItemResult(user_email=user.email, identifier=policy.name, status="success"))

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            return [
                BulkItemResult(
                    user_email=r.user_email, identifier=r.identifier, status="error", error="commit_failed"
                )
                if r.status == "success"
                else r
                for r in results
            ]

        await authorization_cache_service.invalidate_user_policies_bulk(affected_emails)

        return results


policy_assignment_repository = PolicyAssignmentRepository()
