from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..conditions.condition_validator import sanitize_conditions_for_read

POLICY_DESCRIPTION_MAX_LENGTH = 160
POLICY_NAME_MAX_LENGTH = 100
POLICY_ACTION_MAX_LENGTH = 200
POLICY_RESOURCE_TYPE_MAX_LENGTH = 100
PolicyAction = Annotated[str, Field(min_length=1, max_length=POLICY_ACTION_MAX_LENGTH)]


class PolicyBase(BaseModel):
    """
    Shared shape for policy create/update/read schemas : mirrors the
    Policy ORM model's authorization-relevant fields (see policy_model.py).
    """

    name: str = Field(..., min_length=1, max_length=POLICY_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=POLICY_DESCRIPTION_MAX_LENGTH)
    actions: list[PolicyAction] = Field(..., min_length=1)
    resource_type: str = Field(..., min_length=1, max_length=POLICY_RESOURCE_TYPE_MAX_LENGTH)
    # Optional conditions narrowing the grant (e.g. {"self_only": true}) :
    # validated separately at write time (see conditions/condition_validator.py).
    conditions: dict | None = None


class PolicyCreate(PolicyBase):
    """Schema for creating a new policy via the authorization management API."""
    pass


class PolicyUpdate(BaseModel):
    """
    Schema for partially updating an existing policy. All fields optional :
    only provided fields are applied (see repository's update semantics).
    """

    name: str | None = Field(default=None, min_length=1, max_length=POLICY_NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=POLICY_DESCRIPTION_MAX_LENGTH)
    actions: list[PolicyAction] | None = Field(default=None, min_length=1)
    resource_type: str | None = Field(default=None, min_length=1, max_length=POLICY_RESOURCE_TYPE_MAX_LENGTH)
    conditions: dict | None = None
    is_active: bool | None = None

    # Not a Policy column itself : recorded in policy_history as this
    # change's audit-trail explanation (see api/pbac_routes/policies/policy_crud_routes.py).
    change_reason: str | None = Field(default=None, max_length=500)


class PolicyRead(PolicyBase):
    """Schema returned by the authorization management API."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    # Computed by the list endpoint in one aggregate query. Assignments
    # remain authoritative in user_policies; this is read-only metadata.
    holder_count: int = Field(default=0, ge=0)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("conditions", mode="before")
    @classmethod
    def _sanitize_conditions(cls, value: dict | None) -> dict | None:
        return sanitize_conditions_for_read(value)


class PolicyAssignmentRequest(BaseModel):
    """Request body for assigning/removing a policy to/from a user."""

    policy_name: str = Field(..., min_length=1, max_length=POLICY_NAME_MAX_LENGTH)


class PolicyActionRevocationRequest(BaseModel):
    """Request body for revoking a single action out of a user's policy
    assignment (see policy_action_revocation_service.py): `action` must be
    one of the target policy's own `actions`."""

    action: PolicyAction


class UserPoliciesRead(BaseModel):
    """Response shape for 'list policies assigned to a user'."""

    user_email: str
    policies: list[PolicyRead]


class PolicyHolderRead(BaseModel):
    """One user holding a policy: the "Assigned users" view and the
    delete confirm's holder count both use this (len() of the list for
    the count, no separate count endpoint)."""

    email: str
    name: str
    role: str | None = None
    assigned_at: datetime
    assigned_by: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AuthorizationCheckRequest(BaseModel):
    """
    Request body for the effective-authorization / inspection endpoint.
    POST (not GET+query params) because resource/context are arbitrary
    nested JSON, not flat scalars : the same shape
    AuthorizationService.authorize/require accept in-process.
    """

    # min_length=1 rejects an empty-string action/resource_type outright :
    # mirrored in batch_authorization_schema.py's BatchAuthorizationCheckItem.
    action: PolicyAction
    resource_type: str = Field(..., min_length=1, max_length=POLICY_RESOURCE_TYPE_MAX_LENGTH)
    # The specific resource instance to check ownership/attribute
    # conditions against (e.g. {"email": "...", "status": "draft"}) : omit
    # for an unconditional or resource-agnostic check.
    resource: dict | None = None
    # Additional contextual information for context_attributes conditions
    # (e.g. {"mfa_verified": true}).
    context: dict | None = None


class AuthorizationCheckResponse(BaseModel):
    """
    Response for the effective-authorization / inspection endpoint.
    Mirrors AuthorizationDecision (see evaluators/authorization_decision.py)
    : this is that same explanation, shaped for the API.
    """

    user_email: str
    action: str
    resource_type: str
    authorized: bool
    # Policies whose resource_type + action matched, regardless of whether
    # their conditions passed : "what was even considered".
    candidate_policies: list[str]
    # The subset of candidates whose conditions actually passed. Non-empty
    # iff authorized is True.
    granting_policies: list[str]
    # The subset of candidates whose conditions did NOT pass : always
    # candidate_policies minus granting_policies.
    rejected_policies: list[str]
    # {policy_name: [condition_key, ...]} for every rejected policy :
    # exactly which condition(s) failed, not just that something did.
    failed_conditions: dict[str, list[str]]
    # None when authorized; otherwise a short, machine-readable reason :
    # see AuthorizationDecision.denial_reason for the possible values.
    denial_reason: str | None
    # Every policy the user held at evaluation time, regardless of match :
    # a superset of candidate_policies.
    evaluated_policies: list[str]
    # ISO 8601 UTC : when this decision was computed (server clock).
    evaluation_timestamp: str
