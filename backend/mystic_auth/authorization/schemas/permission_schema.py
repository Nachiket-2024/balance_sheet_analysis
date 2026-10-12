from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..conditions.condition_validator import sanitize_conditions_for_read
from ..permissions_catalog import PERMISSION_DESCRIPTION_MAX_LENGTH


class PermissionAssignmentRequest(BaseModel):
    """Request body for granting a direct permission to a user."""

    action: str = Field(..., min_length=1, max_length=200)
    resource_type: str = Field(..., min_length=1, max_length=100)
    conditions: dict | None = None


class UserPermissionRead(BaseModel):
    """Schema returned by the direct-permission-grant management API."""

    id: int
    action: str
    resource_type: str
    conditions: dict | None = None
    is_active: bool
    assigned_by: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("conditions", mode="before")
    @classmethod
    def _sanitize_conditions(cls, value: dict | None) -> dict | None:
        return sanitize_conditions_for_read(value)


class UserPermissionsRead(BaseModel):
    """Response shape for 'list direct permission grants held by a user'."""

    user_email: str
    permissions: list[UserPermissionRead]


class PermissionCatalogEntryRead(BaseModel):
    """One entry of the read-only, built-in permission catalog (see
    authorization/permissions_catalog.py). App-defined action strings are
    managed by the downstream application's own catalog."""

    action: str
    resource_type: str
    description: str = Field(..., min_length=1, max_length=PERMISSION_DESCRIPTION_MAX_LENGTH)


class PermissionUsagePolicyRead(BaseModel):
    """One active policy that grants a given catalog action, for
    PermissionUsageEntryRead.policies - lets the Permissions page's details
    dialog list "which policies grant this" without a second round trip per
    action."""

    name: str
    user_count: int


class PermissionUsageEntryRead(BaseModel):
    """Who actually holds one catalog action right now: which active
    policies grant it (and how many users each reaches), how many users
    hold it as a direct grant, and the deduplicated total across both
    sources (a user holding it both directly and via a policy is counted
    once). Backs the Permissions page's "Held by" column, its Unused/
    In-a-policy/Direct-grants quick filters, and the details dialog - see
    PermissionUsageRepository.get_usage_by_action.

    Only active policies/grants count as "held": an inactive policy that
    still lists the action, or a deactivated direct grant, isn't currently
    reachable by anyone, so it wouldn't be honest to call it "held".
    """

    action: str
    resource_type: str
    policies: list[PermissionUsagePolicyRead]
    policy_user_count: int
    direct_grant_count: int
    total_user_count: int
