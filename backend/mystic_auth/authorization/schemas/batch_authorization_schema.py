from pydantic import BaseModel, Field

# Bounds one request's work (policy fetch is O(1) per batch, but evaluation
# is O(checks)) and limits how much a single request can probe in one shot.
MAX_BATCH_SIZE = 50


class BatchAuthorizationCheckItem(BaseModel):
    """
    One entry in a batch-check request : the same shape a single
    authorize() call takes. min_length=1 on action/resource_type (not just
    max_length) rejects the empty-string form of a malformed check up
    front, consistent with AuthorizationCheckRequest's own fields (see
    policy_schema.py).
    """

    action: str = Field(..., min_length=1, max_length=200)
    resource_type: str = Field(..., min_length=1, max_length=100)
    resource: dict | None = None


class BatchAuthorizationCheckRequest(BaseModel):
    """
    Request body for POST /authorization/batch-check. `checks` is bounded
    on both ends: min_length=1 rejects an empty batch outright,
    max_length=MAX_BATCH_SIZE enforces the maximum batch size.
    """

    checks: list[BatchAuthorizationCheckItem] = Field(..., min_length=1, max_length=MAX_BATCH_SIZE)


class BatchAuthorizationCheckResult(BaseModel):
    """
    One check's outcome. Deliberately minimal : unlike the single-check
    inspection endpoint (AuthorizationCheckResponse), this never includes
    policy names or condition details, only enough to drive a UI decision,
    to avoid leaking which policies matched/rejected a check.
    """

    action: str
    resource_type: str
    allowed: bool
    # None when allowed; otherwise a short, machine-readable classification
    # (e.g. "no_matching_policy", "condition_failed") : coarse enough to be
    # useful without naming which policy/condition was involved.
    denial_reason: str | None = None


class BatchAuthorizationCheckResponse(BaseModel):
    """Response body for POST /authorization/batch-check."""

    results: list[BatchAuthorizationCheckResult]
