from typing import Literal

from sqlalchemy import tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...user.user_model import User
from ..caching.authorization_cache_service import authorization_cache_service
from ..models.user_permission_model import UserPermission
from ..schemas.bulk_schema import BulkItemResult, BulkPermissionItem, BulkPermissionRemoveItem


class UserPermissionRepository:
    """
    User<->direct-permission grant queries and mutations: the granular
    counterpart to PolicyAssignmentRepository, for a single action granted
    straight to a user rather than via a Policy bundle. Mirrors that
    module's method shapes; see its docstrings for the shared reasoning
    (cache-aside, precise vs. namespace-wide invalidation, idempotency).
    """

    @staticmethod
    async def get_active_permissions_for_user(user_email: str, db: AsyncSession) -> list[UserPermission]:
        """The query the authorization/evaluation path actually runs:
        every *active* direct grant held by this user. Cache-aside via
        AuthorizationCacheService, same fail-closed contract as
        PolicyAssignmentRepository.get_active_policies_for_user."""
        cached = await authorization_cache_service.get_user_permissions(user_email)
        if cached is not None:
            return cached

        stmt = (
            select(UserPermission)
            .join(User, User.id == UserPermission.user_id)
            .where(User.email == user_email, UserPermission.is_active.is_(True))
        )
        result = await db.execute(stmt)
        grants = list(result.scalars().all())

        await authorization_cache_service.set_user_permissions(user_email, grants)
        return grants

    @staticmethod
    async def get_permissions_for_user(user_email: str, db: AsyncSession) -> list[UserPermission]:
        """Every direct grant (active or not): for inspection/listing, not
        for making an authorization decision."""
        stmt = (
            select(UserPermission)
            .join(User, User.id == UserPermission.user_id)
            .where(User.email == user_email)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def assign_permission_to_user(
        user_id: int,
        action: str,
        resource_type: str,
        conditions: dict | None,
        db: AsyncSession,
        assigned_by: str | None = None,
        user_email: str | None = None,
    ) -> UserPermission:
        """Idempotent on (user_id, action, resource_type), but unlike
        assign_policy_to_user, NOT a pure no-op on conflict: a grant's
        `conditions` are supplied at assignment time, so re-assigning with
        different conditions legitimately changes scope. Also reactivates
        a previously-deactivated grant."""
        existing = await db.execute(
            select(UserPermission).where(
                UserPermission.user_id == user_id,
                UserPermission.action == action,
                UserPermission.resource_type == resource_type,
            )
        )
        existing_row = existing.scalar_one_or_none()
        if existing_row:
            existing_row.conditions = conditions
            existing_row.is_active = True
            existing_row.assigned_by = assigned_by
            db.add(existing_row)
            await db.commit()
            await db.refresh(existing_row)
            grant = existing_row
        else:
            grant = UserPermission(
                user_id=user_id, action=action, resource_type=resource_type,
                conditions=conditions, assigned_by=assigned_by,
            )
            db.add(grant)
            await db.commit()
            await db.refresh(grant)

        if user_email is not None:
            await authorization_cache_service.invalidate_user_permissions(user_email)

        return grant

    @staticmethod
    async def remove_permission_from_user(
        user_id: int, action: str, resource_type: str, db: AsyncSession, user_email: str | None = None
    ) -> bool:
        """Hard delete, mirrors remove_policy_from_user. Returns True if a
        grant was found and removed, False if the user didn't hold it."""
        result = await db.execute(
            select(UserPermission).where(
                UserPermission.user_id == user_id,
                UserPermission.action == action,
                UserPermission.resource_type == resource_type,
            )
        )
        grant = result.scalar_one_or_none()
        if not grant:
            return False

        await db.delete(grant)
        await db.commit()

        if user_email is not None:
            await authorization_cache_service.invalidate_user_permissions(user_email)

        return True


    @staticmethod
    async def bulk_assign_permissions(
        valid_items: list[tuple[User, BulkPermissionItem]], db: AsyncSession, assigned_by: str | None
    ) -> list[BulkItemResult]:
        """
        `valid_items` already passed resolution and the per-item
        privilege-escalation guard. Stages every write, then commits once
        for the whole batch. Idempotent per item: an already-held
        (action, resource_type) is updated in place. Reported
        "already_held" (not "success") only when the row existed, was
        already active, and had the exact same conditions.
        """
        if not valid_items:
            return []

        triplets = [(user.id, item.action, item.resource_type) for user, item in valid_items]
        existing = await db.execute(
            select(UserPermission).where(
                tuple_(UserPermission.user_id, UserPermission.action, UserPermission.resource_type).in_(triplets)
            )
        )
        existing_by_key = {(row.user_id, row.action, row.resource_type): row for row in existing.scalars().all()}

        results: list[BulkItemResult] = []
        affected_emails: set[str] = set()
        for user, item in valid_items:
            affected_emails.add(user.email)
            key = (user.id, item.action, item.resource_type)
            row = existing_by_key.get(key)
            if row is not None:
                already_held = row.is_active and row.conditions == item.conditions
                row.conditions = item.conditions
                row.is_active = True
                row.assigned_by = assigned_by
                db.add(row)
            else:
                already_held = False
                db.add(
                    UserPermission(
                        user_id=user.id, action=item.action, resource_type=item.resource_type,
                        conditions=item.conditions, assigned_by=assigned_by,
                    )
                )
            status: Literal["success", "already_held"] = "already_held" if already_held else "success"
            results.append(BulkItemResult(user_email=user.email, identifier=item.action, status=status))

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            return [
                BulkItemResult(user_email=r.user_email, identifier=r.identifier, status="error", error="commit_failed")
                for r in results
            ]

        await authorization_cache_service.invalidate_user_permissions_bulk(affected_emails)

        return results

    @staticmethod
    async def bulk_remove_permissions(
        valid_items: list[tuple[User, BulkPermissionRemoveItem]], db: AsyncSession
    ) -> list[BulkItemResult]:
        """Removal counterpart to bulk_assign_permissions. An item that
        isn't actually held is reported as an error (`not_held`), mirroring
        the single-item route's 404."""
        if not valid_items:
            return []

        triplets = [(user.id, item.action, item.resource_type) for user, item in valid_items]
        existing = await db.execute(
            select(UserPermission).where(
                tuple_(UserPermission.user_id, UserPermission.action, UserPermission.resource_type).in_(triplets)
            )
        )
        existing_by_key = {(row.user_id, row.action, row.resource_type): row for row in existing.scalars().all()}

        results: list[BulkItemResult] = []
        affected_emails: set[str] = set()
        for user, item in valid_items:
            key = (user.id, item.action, item.resource_type)
            row = existing_by_key.get(key)
            if row is None:
                results.append(
                    BulkItemResult(user_email=user.email, identifier=item.action, status="error", error="not_held")
                )
                continue
            await db.delete(row)
            affected_emails.add(user.email)
            results.append(BulkItemResult(user_email=user.email, identifier=item.action, status="success"))

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

        await authorization_cache_service.invalidate_user_permissions_bulk(affected_emails)

        return results


user_permission_repository = UserPermissionRepository()
