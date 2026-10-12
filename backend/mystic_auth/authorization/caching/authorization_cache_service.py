import json
import traceback

from ...logging.logging_config import get_logger
from ...valkey.client import valkey_client
from ..models.policy_model import Policy
from ..models.user_permission_model import UserPermission

logger = get_logger(__name__)

# authz:user_policies:{email} -> a user's active, assigned policy list
# (JSON array of serialized policies). See the class docstring for why
# "policy lookup by name" and "evaluation results" are deliberately not
# cached.
_USER_POLICIES_KEY_PREFIX = "authz:user_policies:"
_USER_POLICIES_KEY_PATTERN = f"{_USER_POLICIES_KEY_PREFIX}*"


def _user_policies_key(user_email: str) -> str:
    return f"{_USER_POLICIES_KEY_PREFIX}{user_email}"


# authz:user_permissions:{email} -> a user's active direct permission
# grants (JSON array). A sibling namespace, not merged into
# _USER_POLICIES_KEY_PREFIX above: a UserPermission row IS the per-user
# grant (unlike a Policy, which many users can share), so it only ever
# needs precise, single-user invalidation, never a namespace-wide flush.
# See invalidate_user_permissions.
_USER_PERMISSIONS_KEY_PREFIX = "authz:user_permissions:"


def _user_permissions_key(user_email: str) -> str:
    return f"{_USER_PERMISSIONS_KEY_PREFIX}{user_email}"


# TTL bounds how long a cached policy list can outlive a missed
# invalidation. Backstop only, not the primary invalidation mechanism
# (that's the explicit invalidate_* calls below).
_USER_POLICIES_TTL_SECONDS = 60


def _serialize_policy(policy: Policy) -> dict:
    return {
        "name": policy.name,
        "description": policy.description,
        "actions": list(policy.actions) if policy.actions else [],
        "resource_type": policy.resource_type,
        "conditions": policy.conditions,
        "is_active": policy.is_active,
    }


def _deserialize_policy(data: dict) -> Policy:
    """Reconstructs a plain, session-detached Policy: safe here because
    the cached result is read-only-consumed by the evaluator, never
    passed into session.add()/delete() the way get_by_name()'s result
    sometimes is (see class docstring for why get_by_name isn't cached)."""
    return Policy(
        name=data["name"],
        description=data.get("description"),
        actions=data.get("actions") or [],
        resource_type=data["resource_type"],
        conditions=data.get("conditions"),
        is_active=data.get("is_active", True),
    )


def _serialize_user_permission(grant: UserPermission) -> dict:
    return {
        "action": grant.action,
        "resource_type": grant.resource_type,
        "conditions": grant.conditions,
        "is_active": grant.is_active,
    }


def _deserialize_user_permission(data: dict) -> UserPermission:
    """Reconstructs a plain, session-detached UserPermission - same
    read-only-consumed reasoning as _deserialize_policy above."""
    return UserPermission(
        action=data["action"],
        resource_type=data["resource_type"],
        conditions=data.get("conditions"),
        is_active=data.get("is_active", True),
    )


class AuthorizationCacheService:
    """
    The single, centralized Valkey abstraction for authorization data.
    Only policy_repository.py and user_permission_repository.py call
    this; nothing else in the authorization module talks to Valkey
    directly.

    Cache targets:
        - get_active_policies_for_user's result: runs on every
          authorize() call, is expensive (a two-table join), rarely
          changes, and is only ever read-consumed downstream.
        - get_active_permissions_for_user's result: same shape of
          hot-path query, kept in its own sibling namespace since its
          invalidation rules differ (see invalidate_user_permissions).

    Explicitly NOT cached, and why:
        - Policy lookup by name: get_by_name's result is routinely fed
          straight into PolicyRepository.update()/delete(), which call
          session.add()/delete() on it. A cache-reconstructed,
          session-detached object with a pre-set primary key handed to
          session.add() risks SQLAlchemy treating it as a new INSERT
          (since the session's identity map never saw that PK), raising
          an IntegrityError instead of doing the intended UPDATE. Caching
          this safely needs either a session.merge() step or a hard
          cached/mutable call-site split: real work, left as a follow-up.
        - Evaluation results (final allow/deny for a specific check):
          condition types like time/date_range/network are legitimately
          context-dependent, so the same (user, action, resource_type)
          can correctly evaluate differently a minute later or from a
          different IP. Caching the policy list already removes the
          expensive part (the DB round trip); evaluating it is pure
          in-memory computation, so caching the decision itself would
          only add correctness risk, no real speedup.

    Fail-closed with respect to the cache, never with respect to
    authorization. Any Valkey error is caught, logged, and returns a
    cache-miss sentinel (None); the caller then falls through to the
    authoritative database query. It does not mean "deny every request
    whenever Valkey is unreachable": that would turn a transient cache
    outage into an application-wide denial of service.
    """

    @staticmethod
    async def get_user_policies(user_email: str) -> list[Policy] | None:
        """Returns None on a cache miss or any cache failure: both are
        treated identically by the caller (fall through to the database)."""
        try:
            raw = await valkey_client.get(_user_policies_key(user_email))
        except Exception:
            logger.warning("Authorization cache read failed (user_policies):\n%s", traceback.format_exc())
            return None

        if raw is None:
            return None

        try:
            return [_deserialize_policy(item) for item in json.loads(raw)]
        except Exception:
            logger.warning("Authorization cache payload corrupt (user_policies):\n%s", traceback.format_exc())
            return None

    @staticmethod
    async def set_user_policies(user_email: str, policies: list[Policy]) -> None:
        """Best-effort populate: a write failure here must never surface
        to the caller (the database query it's caching already
        succeeded; this is purely a subsequent-request optimization)."""
        try:
            payload = json.dumps([_serialize_policy(policy) for policy in policies])
            await valkey_client.set(_user_policies_key(user_email), payload, ex=_USER_POLICIES_TTL_SECONDS)
        except Exception:
            logger.warning("Authorization cache write failed (user_policies):\n%s", traceback.format_exc())

    @staticmethod
    async def invalidate_user_policies(user_email: str) -> None:
        """
        Called on policy assignment/revocation for this specific user:
        precise invalidation, since exactly one user's effective policy
        set changed.
        """
        try:
            await valkey_client.delete(_user_policies_key(user_email))
        except Exception:
            logger.warning("Authorization cache invalidation failed (user_policies):\n%s", traceback.format_exc())

    @staticmethod
    async def invalidate_user_policies_bulk(user_emails: set[str]) -> None:
        """Same effect as invalidate_user_policies() per email, collapsed
        into one valkey_client.delete() call: used when the exact set of
        affected users is already known (unlike invalidate_all_user_policies,
        for a policy edit with no cheap reverse index to its holders)."""
        if not user_emails:
            return
        try:
            await valkey_client.delete(*(_user_policies_key(email) for email in user_emails))
        except Exception:
            logger.warning("Authorization cache invalidation failed (user_policies bulk):\n%s", traceback.format_exc())

    @staticmethod
    async def invalidate_all_user_policies() -> None:
        """
        Called on any policy update/delete: a policy's definition change
        can affect every user who holds it, and there's no cheap reverse
        index from policy to its holders, so this flushes the whole
        user_policies namespace instead of guessing who's affected. Policy
        edits are rare relative to authorization checks, so a full flush
        on infrequent writes is a deliberate trade-off. Uses SCAN (not
        KEYS) so it never blocks Valkey, batching deletes per SCAN batch.
        """
        try:
            batch: list[str] = []
            async for key in valkey_client.scan_iter(match=_USER_POLICIES_KEY_PATTERN):
                batch.append(key)
                if len(batch) >= 500:
                    await valkey_client.delete(*batch)
                    batch = []
            if batch:
                await valkey_client.delete(*batch)
        except Exception:
            logger.warning(
                "Authorization cache namespace flush failed (user_policies):\n%s", traceback.format_exc()
            )

    @staticmethod
    async def get_user_permissions(user_email: str) -> list[UserPermission] | None:
        """Same contract as get_user_policies: None on a miss or any
        failure, both treated identically by the caller."""
        try:
            raw = await valkey_client.get(_user_permissions_key(user_email))
        except Exception:
            logger.warning("Authorization cache read failed (user_permissions):\n%s", traceback.format_exc())
            return None

        if raw is None:
            return None

        try:
            return [_deserialize_user_permission(item) for item in json.loads(raw)]
        except Exception:
            logger.warning("Authorization cache payload corrupt (user_permissions):\n%s", traceback.format_exc())
            return None

    @staticmethod
    async def set_user_permissions(user_email: str, grants: list[UserPermission]) -> None:
        """Best-effort populate, same contract as set_user_policies."""
        try:
            payload = json.dumps([_serialize_user_permission(grant) for grant in grants])
            await valkey_client.set(_user_permissions_key(user_email), payload, ex=_USER_POLICIES_TTL_SECONDS)
        except Exception:
            logger.warning("Authorization cache write failed (user_permissions):\n%s", traceback.format_exc())

    @staticmethod
    async def invalidate_user_permissions(user_email: str) -> None:
        """Called on direct-permission grant/revoke for this user. No
        namespace-wide equivalent needed: a UserPermission row has no
        separate "definition" other users share, so single-user
        invalidation is always sufficient."""
        try:
            await valkey_client.delete(_user_permissions_key(user_email))
        except Exception:
            logger.warning("Authorization cache invalidation failed (user_permissions):\n%s", traceback.format_exc())

    @staticmethod
    async def invalidate_user_permissions_bulk(user_emails: set[str]) -> None:
        """Bulk counterpart to invalidate_user_permissions: one
        valkey_client.delete() for every affected key instead of one round
        trip per user."""
        if not user_emails:
            return
        try:
            await valkey_client.delete(*(_user_permissions_key(email) for email in user_emails))
        except Exception:
            logger.warning(
                "Authorization cache invalidation failed (user_permissions bulk):\n%s", traceback.format_exc()
            )


authorization_cache_service = AuthorizationCacheService()
