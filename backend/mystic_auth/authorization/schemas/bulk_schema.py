from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .policy_schema import POLICY_ACTION_MAX_LENGTH, POLICY_NAME_MAX_LENGTH, POLICY_RESOURCE_TYPE_MAX_LENGTH

PolicyName = Annotated[str, Field(min_length=1, max_length=POLICY_NAME_MAX_LENGTH)]
PolicyAction = Annotated[str, Field(min_length=1, max_length=POLICY_ACTION_MAX_LENGTH)]
ResourceType = Annotated[str, Field(min_length=1, max_length=POLICY_RESOURCE_TYPE_MAX_LENGTH)]

# Bulk request items are capped at 200 per request: bulk assignment is an
# operator action (not a synchronous hot-path check like
# BatchAuthorizationCheckRequest's 1-50), but still bounded to keep one
# request's worst-case DB lock/latency time predictable.
_MAX_BULK_ITEMS = 200


class BulkItemResult(BaseModel):
    """
    One item's outcome from a bulk operation. Bulk endpoints are
    best-effort: valid items commit, invalid ones are reported back here
    rather than failing the whole batch (see bulk_policy_routes.py /
    bulk_permission_routes.py / bulk_role_routes.py for the one exception:
    a genuine DB-level commit failure, which has no partial outcome to
    report).
    """

    user_email: str
    identifier: str  # policy_name / action / role value, whichever this bulk op is over
    # "already_held": an assign/grant that was a no-op (target already had
    # it), reported separately from "success" so a bulk-assign result shows
    # per user what actually changed. Removal/revoke never sets this: not
    # holding the thing removed is already a "not_held" error.
    status: Literal["success", "already_held", "error"]
    error: str | None = None


class BulkResponse(BaseModel):
    results: list[BulkItemResult]
    success_count: int
    error_count: int


class BulkPolicyItem(BaseModel):
    user_email: str
    policy_name: PolicyName


class BulkPolicyRequest(BaseModel):
    items: list[BulkPolicyItem] = Field(..., min_length=1, max_length=_MAX_BULK_ITEMS)


class BulkPermissionItem(BaseModel):
    user_email: str
    action: PolicyAction
    resource_type: ResourceType
    conditions: dict | None = None


class BulkPermissionRequest(BaseModel):
    items: list[BulkPermissionItem] = Field(..., min_length=1, max_length=_MAX_BULK_ITEMS)


class BulkPermissionRemoveItem(BaseModel):
    user_email: str
    action: PolicyAction
    resource_type: ResourceType


class BulkPermissionRemoveRequest(BaseModel):
    items: list[BulkPermissionRemoveItem] = Field(..., min_length=1, max_length=_MAX_BULK_ITEMS)


class BulkRoleItem(BaseModel):
    user_email: str
    role: str


class BulkRoleRequest(BaseModel):
    items: list[BulkRoleItem] = Field(..., min_length=1, max_length=_MAX_BULK_ITEMS)


def summarize(results: list[BulkItemResult]) -> BulkResponse:
    """Wraps a bulk operation's per-item results in the response envelope
    (success/error counts), shared by bulk_policy_routes.py /
    bulk_permission_routes.py / bulk_role_routes.py so each doesn't
    recompute the same tally."""
    success_count = sum(1 for r in results if r.status in ("success", "already_held"))
    return BulkResponse(results=results, success_count=success_count, error_count=len(results) - success_count)


def bulk_error(user_email: str, identifier: str, code: str) -> BulkItemResult:
    """One item's error outcome, in the shape summarize() and the route's
    own repository-produced results already share - previously
    byte-identically redefined as a private `_error` helper in each of
    bulk_policy_routes.py / bulk_permission_routes.py / bulk_role_routes.py."""
    return BulkItemResult(user_email=user_email, identifier=identifier, status="error", error=code)
