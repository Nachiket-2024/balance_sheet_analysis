from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..caching.authorization_cache_service import authorization_cache_service
from ..models.policy_model import UserPolicy
from ..models.user_permission_model import UserPermission


class ActionNotInPolicyError(ValueError):
    """Raised when the requested action isn't one of the target policy's
    own `actions` - there is nothing to carve out."""


class PolicyActionRevocationService:
    """
    Carves a single action out of a user's policy assignment, without
    touching the policy definition (other users may hold it too) and
    without dropping the user's other actions from that same policy.

    A Policy assignment is otherwise all-or-nothing: revoking it drops
    every action it granted, even ones the user should keep. Without this
    service, "lose exactly one action" means revoking the whole policy and
    manually re-granting the rest, or editing the policy definition
    itself (which affects every other holder). Neither matches "take one
    action away from one user".

    Implementation: in one transaction, remove the UserPolicy assignment
    row, then re-create (or reactivate) a direct UserPermission grant for
    each of the policy's other actions, carrying over its `conditions` so
    the user's effective access is unchanged except for the revoked
    action.

    One-shot conversion triggered by an explicit operator action, not a
    generic "diff a policy assignment" mechanism or a DB trigger.
    """

    @staticmethod
    async def revoke_single_action(
        user_id: int,
        policy,
        action: str,
        db: AsyncSession,
        revoked_by: str | None = None,
        user_email: str | None = None,
    ) -> bool:
        """
        Returns False if the user doesn't hold `policy` at all (caller
        should treat this as 404, mirroring remove_policy_from_user).
        Raises ActionNotInPolicyError if `action` isn't one of the
        policy's own actions (caller should treat this as 400).

        `revoked_by` is the caller's email, recorded as `assigned_by` on
        every direct grant created here - these are genuinely new grants
        the caller is responsible for, same as any other direct grant.
        """
        if action not in policy.actions:
            raise ActionNotInPolicyError(f"'{action}' is not one of policy '{policy.name}'s actions")

        existing_assignment = await db.execute(
            select(UserPolicy).where(UserPolicy.user_id == user_id, UserPolicy.policy_id == policy.id)
        )
        assignment = existing_assignment.scalar_one_or_none()
        if assignment is None:
            return False

        remaining_actions = [a for a in policy.actions if a != action]

        # Only the SAME resource_type as the policy: an existing direct
        # grant for one of these actions on a DIFFERENT resource_type is a
        # separate, unrelated grant that must be left alone.
        existing_grants = await db.execute(
            select(UserPermission).where(
                UserPermission.user_id == user_id,
                UserPermission.resource_type == policy.resource_type,
                UserPermission.action.in_(remaining_actions),
            )
        )
        existing_by_action = {g.action: g for g in existing_grants.scalars().all()}

        for remaining_action in remaining_actions:
            grant = existing_by_action.get(remaining_action)
            if grant is not None:
                grant.conditions = policy.conditions
                grant.is_active = True
                grant.assigned_by = revoked_by
                db.add(grant)
            else:
                db.add(
                    UserPermission(
                        user_id=user_id,
                        action=remaining_action,
                        resource_type=policy.resource_type,
                        conditions=policy.conditions,
                        assigned_by=revoked_by,
                    )
                )

        await db.delete(assignment)
        # One commit for the whole operation: a failure partway through
        # (e.g. the assignment delete) must not leave some of the
        # replacement direct grants committed without it, which would
        # silently duplicate the user's effective access instead of
        # preserving it.
        await db.commit()

        if user_email is not None:
            await authorization_cache_service.invalidate_user_policies(user_email)
            await authorization_cache_service.invalidate_user_permissions(user_email)

        return True


policy_action_revocation_service = PolicyActionRevocationService()
