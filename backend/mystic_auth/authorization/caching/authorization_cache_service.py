import json
import traceback

from ...logging.logging_config import get_logger
from ...redis.client import redis_client
from ..models.policy_model import Policy

logger = get_logger(__name__)

# authz:user_policies:{email} -> a user's active, assigned policy list
# (JSON array of serialized policies). This is the ONE cache target this
# module currently implements. See the class docstring for why
# "policy lookup by name" and "evaluation results" (both also mentioned in
# the authorization performance layer) are deliberately NOT cached.
_USER_POLICIES_KEY_PREFIX = "authz:user_policies:"
_USER_POLICIES_KEY_PATTERN = f"{_USER_POLICIES_KEY_PREFIX}*"


def _user_policies_key(user_email: str) -> str:
    return f"{_USER_POLICIES_KEY_PREFIX}{user_email}"


# TTL bounds how long a cached policy list can outlive an invalidation this
# module failed to receive for any reason. Never serve
# indefinitely stale permissions". This is the backstop, not the primary
# invalidation mechanism (which is the explicit invalidate_* calls below).
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
    """
    Reconstructs a plain, session-detached Policy: safe here because
    get_active_policies_for_user's result is read-only-consumed (the
    evaluator only ever reads .name/.actions/.resource_type/.conditions),
    never passed into session.add()/session.delete() the way a
    get_by_name() result sometimes is (see this module's docstring for why
    that distinction matters and why get_by_name is NOT cached).
    """
    return Policy(
        name=data["name"],
        description=data.get("description"),
        actions=data.get("actions") or [],
        resource_type=data["resource_type"],
        conditions=data.get("conditions"),
        is_active=data.get("is_active", True),
    )


class AuthorizationCacheService:
    """
    The single, centralized Redis abstraction for authorization data, per
    the authorization performance layer: "Create centralized Redis
    abstraction layer (single module)" / "Do not scatter Redis calls
    throughout authorization code". Only policy_repository.py calls this;
    nothing else in the authorization module (the service, the evaluator,
    routes) talks to Redis directly for authorization purposes.

    Cache target, deliberately scoped to one:
        get_active_policies_for_user's result (a user's active, assigned
        policy list): the one authorization-hot-path DB query that runs
        on literally every authorize() call, is expensive (a two-table
        join), rarely changes, and is only ever read-consumed downstream
        (never fed back into a database mutation).

    Explicitly NOT cached in this pass, and why:
        - "Policy lookup [by name]": get_by_name's result is routinely
          fetched immediately before being passed into
          PolicyRepository.update()/delete() (see api/pbac_routes/policy_crud_routes.py),
          which call session.add(db_obj)/session.delete(db_obj) on it. A
          cache-reconstructed, session-detached object with a pre-set
          primary key handed to session.add() risks SQLAlchemy treating it
          as a new pending INSERT (since the session's identity map has
          never seen that PK), which would raise an IntegrityError on
          flush instead of performing the intended UPDATE. Caching this
          safely would need either a `session.merge()` step wherever a
          cached policy might be mutated, or a hard split between "cached,
          read-only" and "always-fresh, mutable" call sites: real, but
          separate, work: left as a documented follow-up rather than
          shipped half-correct.
        - "Evaluation results" (the final allow/deny for a specific
          action+resource+context): several condition types (time,
          date_range, network, security_context) are legitimately
          request-context-dependent: the same (user, action,
          resource_type) can correctly evaluate differently a minute later,
          or from a different IP. Caching the *decision* risks serving a
          stale answer for exactly the conditions designed to be
          time/context-sensitive. Caching the *policy list* (this module)
          already removes the one expensive part (the DB round trip);
          evaluating that list against the current resource/context is
          pure in-memory computation, so there is no meaningful
          performance case left for caching the decision itself, only
          correctness risk.

    Fail-closed, precisely: every method here fails closed *with respect to
    the cache*, never with respect to authorization itself. Any Redis
    error (connection failure, timeout, corrupt payload) is caught and
    logged, and the method returns a cache-miss sentinel (None) rather than
    raising or returning something possibly wrong. The caller
    (policy_repository.get_active_policies_for_user) then falls through to
    the authoritative database query on any miss: the one source of truth
    this cache can never disagree with, since it is populated *from* it and
    invalidated whenever it changes. That is what "fail closed" means here:
    the cache is never trusted over the database. It does not mean "deny
    every authorization request whenever Redis is unreachable". That would
    turn a transient cache outage into an application-wide denial of
    service, strictly worse than falling back to the database evaluation
    this cache exists only to speed up.
    """

    @staticmethod
    async def get_user_policies(user_email: str) -> list[Policy] | None:
        """Returns None on a cache miss or any cache failure: both are
        treated identically by the caller: fall through to the database."""
        try:
            raw = await redis_client.get(_user_policies_key(user_email))
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
            await redis_client.set(_user_policies_key(user_email), payload, ex=_USER_POLICIES_TTL_SECONDS)
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
            await redis_client.delete(_user_policies_key(user_email))
        except Exception:
            logger.warning("Authorization cache invalidation failed (user_policies):\n%s", traceback.format_exc())

    @staticmethod
    async def invalidate_all_user_policies() -> None:
        """
        Called on any policy update/delete: a policy's own definition
        changing (actions, conditions, resource_type, is_active) can affect
        every user who holds it, and there is no cheap reverse index from
        policy -> its holders, so this flushes the whole user_policies
        namespace rather than guessing which users are affected. Policy
        edits are rare relative to authorization checks, so a full-
        namespace flush on (infrequent) writes is a deliberate, safe
        trade-off: never serve a stale grant after a policy edit. Uses
        SCAN (not KEYS), so it never blocks Redis even on a large keyspace.
        """
        try:
            async for key in redis_client.scan_iter(match=_USER_POLICIES_KEY_PATTERN):
                await redis_client.delete(key)
        except Exception:
            logger.warning(
                "Authorization cache namespace flush failed (user_policies):\n%s", traceback.format_exc()
            )


authorization_cache_service = AuthorizationCacheService()
