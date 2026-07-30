from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PolicyBase(BaseModel):
    """
    Shared shape for policy create/update/read schemas : mirrors the
    Policy ORM model's authorization-relevant fields (see policy_model.py).
    """

    name: str = Field(..., max_length=100)
    description: str | None = Field(default=None, max_length=500)
    actions: list[str]
    resource_type: str = Field(..., max_length=100)
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

    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    actions: list[str] | None = None
    resource_type: str | None = Field(default=None, max_length=100)
    conditions: dict | None = None
    is_active: bool | None = None

    # Not a Policy column itself : recorded in policy_history as this
    # change's audit-trail explanation (see api/pbac_routes/policy_crud_routes.py).
    change_reason: str | None = Field(default=None, max_length=500)


class PolicyRead(PolicyBase):
    """Schema returned by the authorization management API."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PolicyAssignmentRequest(BaseModel):
    """Request body for assigning/removing a policy to/from a user."""

    policy_name: str = Field(..., max_length=100)


class UserPoliciesRead(BaseModel):
    """Response shape for 'list policies assigned to a user'."""

    user_email: str
    policies: list[PolicyRead]


class AuthorizationCheckRequest(BaseModel):
    """
    Request body for the effective-authorization / inspection endpoint.
    POST (not GET+query params) because resource/context are arbitrary
    nested JSON, not flat scalars : the same shape
    AuthorizationService.authorize/require accept in-process.
    """

    # min_length=1 rejects an empty-string action/resource_type outright :
    # mirrored in batch_authorization_schema.py's BatchAuthorizationCheckItem.
    action: str = Field(..., min_length=1, max_length=200)
    resource_type: str = Field(..., min_length=1, max_length=100)
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
