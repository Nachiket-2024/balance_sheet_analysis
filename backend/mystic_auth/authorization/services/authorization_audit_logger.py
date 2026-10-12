import traceback

from ...logging.logging_config import get_logger
from ...procrastinate_tasks.audit_log_tasks import log_authorization_decision_task
from ..evaluators.authorization_decision import AuthorizationDecision

logger = get_logger(__name__)


def build_audit_entry(
    user_email: str,
    action: str,
    resource_type: str,
    resource: dict | object | None,
    context: dict | None,
    decision: AuthorizationDecision,
) -> dict:
    """
    The audit log row (as a plain dict, not yet persisted) for one
    decision, capturing which policies matched vs. were rejected and
    which condition(s) failed, so "why was this denied" is answerable
    from the trail alone. Shared by log_decision (single commit) and
    authorize_batch (one commit for the whole batch).
    """
    # resource is often an arbitrary dict/object with no guaranteed
    # key, so this is a best-effort identifier for the log entry.
    resource_identifier = None
    if isinstance(resource, dict):
        resource_identifier = resource.get("email") or resource.get("id")
    elif resource is not None:
        resource_identifier = getattr(resource, "email", None) or getattr(resource, "id", None)
    if resource_identifier is not None:
        resource_identifier = str(resource_identifier)

    return {
        "user_email": user_email,
        "action": action,
        "resource_type": resource_type,
        "resource_identifier": resource_identifier,
        "allowed": decision.allowed,
        "candidate_policy_names": decision.matched_policies + decision.rejected_policies,
        "granting_policy_names": decision.matched_policies,
        "failed_conditions": decision.failed_conditions or None,
        "context": context,
    }


async def log_decision(
    user_email: str,
    action: str,
    resource_type: str,
    resource: dict | object | None,
    context: dict | None,
    decision: AuthorizationDecision,
) -> None:
    """
    Queues an audit row via Procrastinate rather than writing it inline:
    this is the choke point every authorize()/require() call goes
    through, so a synchronous commit here would add write latency to
    every protected request. The INSERT happens in a background worker
    instead; the trail becomes eventually consistent (typically
    sub-second).

    A failure to even queue the job must never break the authorization
    decision it's describing, so it's caught and logged, never re-raised.
    """
    try:
        await log_authorization_decision_task.defer_async(
            entry=build_audit_entry(user_email, action, resource_type, resource, context, decision)
        )
    except Exception:
        logger.warning("Failed to queue authorization audit log entry:\n%s", traceback.format_exc())
