# Backend Unit Tests
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

These tests isolate one backend responsibility. A unit test may use a fake
repository, mocked service, or constructed request, but it should make the
decision under test visible: inputs, collaborator calls, returned value, and
security-sensitive side effects. These tests do not establish that a complete
HTTP request can reach the code or that a database transaction commits.

Paths below are relative to the repository root. Files are named individually
so a failure can be understood without opening the source module.

---

## Application and API routes

- `tests/backend/app/test_main_global_exception_handler_unit.py` verifies safe
  conversion and reporting of unexpected application exceptions.
- `tests/backend/app/test_main_lifecycle_unit.py` verifies signal relay and
  application lifespan startup/shutdown behavior.
- `tests/backend/app/test_core_settings.py` and
  `tests/backend/app/test_settings.py` verify settings boundaries and
  environment-derived configuration.
- `tests/backend/app/test_app_sdk_module_identity.py` verifies the app SDK
  module identity boundary.
- `tests/backend/mystic_auth/unit/api/audit_log_routes/test_audit_log_me_route_unit.py`
  verifies the current-user audit-log route and its self-scope response.
- `tests/backend/mystic_auth/unit/api/audit_log_routes/test_user_security_audit_log_route_unit.py`
  verifies security-event route authorization and response construction.
- `tests/backend/mystic_auth/unit/api/get_or_404/test_get_or_404_unit.py`
  verifies the shared lookup helper's not-found conversion.
- `tests/backend/mystic_auth/unit/api/health_routes/test_health_routes_unit.py`
  verifies health response shape and dependency status mapping.
- `tests/backend/mystic_auth/unit/api/user_routes/test_user_policies_me_route_unit.py`
  verifies the current user's effective-policy endpoint.

### PBAC routes

- `test_batch_authorization_route_unit.py` verifies batch decision request
  validation and response mapping.
- `test_bulk_policy_routes_unit.py` verifies bulk policy assignment and its
  per-item result handling.
- `test_bulk_system_user_guard_unit.py` verifies protected system users cannot
  be changed through bulk operations.
- `test_permission_assignment_system_user_guard_unit.py` verifies the same
  protected-user rule for direct permission grants.
- `test_permission_routes_condition_validation_unit.py` verifies condition
  payload validation before a permission grant is accepted.
- `test_policy_assignment_authorization_security_unit.py` verifies that the
  caller may assign only policies allowed by the authorization rules.
- `test_policy_assignment_system_user_guard_unit.py` verifies policy changes
  cannot target the protected bootstrap user.
- `test_policy_crud_authorization_security_unit.py` verifies policy create,
  update, and delete authorization boundaries.
- `test_policy_history_unit.py` verifies policy history entries and rollback
  or audit metadata formatting.
- `test_policy_routes_condition_validation_unit.py` verifies policy condition
  validation on route input.

The PBAC route files above live in
`tests/backend/mystic_auth/unit/api/pbac_routes/`.

---

## Authentication and sessions

### Current user, login, and logout

- `auth/current_user/test_current_user_handler_unit.py` verifies current-user
  identity loading and inactive-user handling.
- `auth/current_user/test_current_user_handler_active_sessions.py` verifies
  active-session data added to the current-user response.
- `auth/login/test_auth_schemas_unit.py` verifies login input normalization
  and schema validation.
- `auth/login/test_login_handler_unit.py` verifies login orchestration,
  generic failures, cookies, and audit outcomes.
- `auth/login/test_login_service_unit.py` verifies credential checks, dummy
  hash timing, lockout decisions, and successful session creation.
- `auth/logout/test_logout_handler_unit.py` verifies current-session logout
  response and cookie clearing.
- `auth/logout_all/test_logout_all_handler_unit.py` verifies logout-all
  authorization, session revocation, and response behavior.
- `auth/manage_sessions/test_session_revoke_handler_unit.py` verifies one
  session revoke request and its safety checks.

### OAuth, passwords, and account verification

- `auth/oauth2/test_oauth2_callback_state_validation_unit.py` verifies OAuth
  state and callback validation against replay or mismatch.
- `auth/oauth2/test_oauth2_login_handler_unit.py` verifies OAuth login request
  construction and error handling.
- `auth/oauth2/test_oauth2_service_unit.py` verifies provider exchange,
  identity linking, and PKCE-related service decisions.
- `auth/password_logic/test_password_reset_unit.py` verifies reset-token
  creation, expiry, and one-time consumption.
- `auth/password_logic/test_password_service_unit.py` verifies password
  hashing, validation, and change decisions.
- `auth/password_reset_confirm/test_password_reset_confirm_handler_unit.py`
  verifies reset confirmation input, token use, and failure responses.
- `auth/password_reset_request/test_password_reset_request_handler_unit.py`
  verifies reset request normalization and non-disclosing responses.
- `auth/signup/test_signup_unit.py` verifies signup defaults, normalization,
  and initial account state.
- `auth/verify_account/test_account_verification_handler_unit.py` verifies
  verification request and confirmation response behavior.
- `auth/verify_account/test_account_verification_service_unit.py` verifies
  token validation, expiry, and account activation decisions.
- `auth/verify_account/test_user_verification_service_unit.py` verifies
  user-verification state transitions and notification decisions.

### Tokens and request security

- `auth/refresh_token_logic/test_refresh_token_handler_unit.py` verifies
  refresh request orchestration and cookie response behavior.
- `auth/refresh_token_logic/test_refresh_token_unit.py` verifies rotation,
  expiry, replay detection, and token-chain revocation.
- `auth/refresh_token_logic/test_refresh_token_valkey_unavailable_unit.py`
  verifies fail-closed behavior when token-version/revocation state is unavailable.
- `auth/token_logic/test_jwt_service_jti_revocation_unit.py` verifies JTI
  revocation checks and durable claims handling.
- `auth/token_logic/test_jwt_service_revocation_unit.py` verifies token
  revocation and version invalidation.
- `auth/token_logic/test_jwt_service_unit.py` verifies JWT creation,
  decoding, claims, and expiry validation.
- `auth/token_logic/test_token_cookie_handler_unit.py` verifies secure cookie
  attributes, clearing, and environment-aware flags.
- `auth/token_logic/test_token_version_store_unit.py` verifies token-version
  reads and writes used to invalidate sessions.
- `auth/token_logic/test_token_revocation_version_model_unit.py` verifies the
  token-revocation-version model metadata and column contract.
- `auth/security/test_client_ip_unit.py` verifies trusted proxy and client-IP
  extraction rules.
- `auth/security/test_login_protection_unit.py` verifies account/IP lockout
  thresholds and recovery behavior.
- `auth/security/test_rate_limiter_service_dashboard_unit.py` verifies
  dashboard aggregation of rate-limit state.
- `auth/security/test_rate_limiter_unit.py` verifies fixed-window decisions,
  retry metadata, and fail-safe behavior.

---

## Authorization and PBAC core

- `authorization/caching/test_authorization_cache_service_unit.py` verifies
  cache keys, hits, misses, invalidation, and fail-safe cache behavior.
- `authorization/conditions/test_condition_schema_consistency_unit.py`
  verifies condition schemas agree with the permission catalog.
- `authorization/conditions/test_condition_validator_unit.py` verifies type,
  operator, and required-field validation for conditions.
- `authorization/conditions/test_policy_conditions_network_security_unit.py`
  verifies network and security condition evaluation.
- `authorization/conditions/test_policy_conditions_temporal_unit.py`
  verifies time-window and temporal condition evaluation.
- `authorization/conditions/test_policy_conditions_unit.py` verifies the
  common condition evaluator and its allow/deny outcomes.
- `authorization/context/test_request_context_builder_unit.py` verifies the
  trusted request context supplied to policy evaluation.
- `authorization/dependencies/test_authorization_dependency_unit.py`
  verifies route dependency wiring and denial behavior.
- `authorization/evaluators/test_authorization_decision_unit.py` verifies
  normalized allow/deny decisions and explanations.
- `authorization/evaluators/test_policy_evaluator_detailed_unit.py` verifies
  detailed policy matching, conditions, and decision reasons.
- `authorization/evaluators/test_policy_evaluator_unit.py` verifies effective
  policy evaluation and precedence.
- `authorization/policies/test_default_policies_unit.py` verifies the shipped
  policy definitions, permissions, and protected bootstrap policy.
- `authorization/repositories/test_policy_query_repository_unit.py` verifies
  policy queries, filters, and effective-grant retrieval.
- `authorization/repositories/test_policy_repository_caching_unit.py`
  verifies repository cache interaction around policy writes.
- `authorization/repositories/test_user_permission_repository_unit.py`
  verifies direct grants and effective user permissions.
- `authorization/services/test_authorization_audit_logger_unit.py` verifies
  authorization decision audit records.
- `authorization/services/test_authorization_grant_guard_context_unit.py`
  verifies grant-context restrictions that prevent privilege escalation.
- `authorization/services/test_authorization_service_audit_log_unit.py`
  verifies service-level audit logging for authorization changes.
- `authorization/services/test_authorization_service_batch_unit.py` verifies
  batch checks, ordering, and independent results.
- `authorization/services/test_authorization_service_direct_grants_unit.py`
  verifies direct permission grant and revoke behavior.
- `authorization/services/test_authorization_service_unit.py` verifies the
  main authorization service orchestration and fail-closed behavior.
- `authorization/services/test_bulk_notification_unit.py` verifies bulk
  operation notification aggregation and failure handling.
- `authorization/test_permission_catalog_schema_unit.py` verifies permission
  catalog shape and metadata.
- `authorization/test_policy_schema_unit.py` verifies policy input/output
  schemas and validation rules.

---

## Infrastructure, users, and workers

The user-schema unit coverage includes the current brand-color validation
example and the full normalization/error contract. Backend host-test fixtures
also read the configured Postgres and Valkey host-port variables, so native
tests remain valid when another local project uses the defaults.

- `audit_log/test_audit_log_repository_unit.py` verifies audit persistence
  queries, filters, pagination, and metadata handling.
- `audit_log/test_security_audit_service_unit.py` verifies security-event
  recording and query preparation.
- `core/test_env_examples_parity_unit.py` verifies environment examples stay
  aligned with settings.
- `core/test_settings_unit.py` verifies settings validation and derived values.
- `database/test_base_unit.py` verifies ORM base configuration.
- `database/test_connection_unit.py` verifies database engine and session
  configuration.
- `emails/test_email_normalization_unit.py` verifies address normalization.
- `emails/test_email_sender_unit.py` verifies sender construction and failure
  handling.
- `emails/test_email_template_service_unit.py` verifies template rendering
  and required context.
- `error_monitoring/test_sentry_service_unit.py` verifies optional Sentry
  setup, DSN loading, and exception reporting.
- `logging/test_correlation_id_middleware_unit.py` verifies correlation IDs
  across request and response logs.
- `logging/test_logging_config_unit.py` verifies handler profiles and format
  configuration.
- `logging/test_logging_middleware_unit.py` verifies access logging and
  sensitive-field handling.
- `core/test_secret_provider_unit.py` verifies the one-secret provider boundary,
  invalid environment-name rejection, and missing-secret failures.
- `procrastinate_tasks/test_account_purge_tasks_unit.py` verifies purge-task
  scheduling and idempotent account cleanup.
- `procrastinate_tasks/test_account_lifecycle_tasks_unit.py` verifies lifecycle
  event delivery and dispatcher retry behavior.
- `procrastinate_tasks/test_procrastinate_app_unit.py` verifies worker lifecycle
  metadata, retry-preserving failures, and best-effort observer handling.
- `procrastinate_tasks/test_audit_log_tasks_unit.py` verifies background audit
  log work and retry behavior.
- `procrastinate_tasks/test_email_tasks_unit.py` verifies queued email task
  payloads and retry handling.
- `procrastinate_tasks/test_session_cleanup_tasks_unit.py` verifies stale
  session cleanup scheduling.
- `tests/backend/mystic_auth/unit/scripts/test_create_system_user_unit.py`
  verifies protected system-user creation and bootstrap safeguards.
- `tests/backend/mystic_auth/unit/scripts/test_create_unconditioned_policies_unit.py`
  verifies default role-based access policy creation and repeatability.
- `tests/backend/mystic_auth/unit/scripts/test_authorization_maintenance_scripts_unit.py`
  verifies targeted/all-user cache invalidation, duplicate-email reporting,
  conditioned-grant conflict selection, and both CLI output paths.
- `user/test_user_base_crud_filters_unit.py` verifies user filtering and
  scoped query predicates.
- `user/test_user_base_crud_joins_and_crud_unit.py` verifies joins and common
  user CRUD operations.
- `user/test_user_email_crud_unit.py` verifies email lookup and update rules.
- `user/test_user_lifecycle_crud_unit.py` verifies lifecycle state mutations.
- `user/test_user_model_unit.py` verifies model defaults and invariants.
- `user/test_user_role_crud_unit.py` verifies role assignment queries and
  constraints.
- `user/test_user_schema_unit.py` verifies user input/output schemas.
- `user_lifecycle/test_account_deletion_confirm_handler_unit.py` verifies
  deletion-confirmation request handling.
- `user_lifecycle/test_account_deletion_service_unit.py` verifies deletion
  authorization and state transition decisions.
- `user_lifecycle/test_account_lifecycle_events_unit.py` verifies lifecycle
  payload round-tripping, listener delivery, and retry-visible failures.
- `user_lifecycle/test_user_purge_service_unit.py` verifies irreversible purge
  ordering and cleanup scope.
- `user_lifecycle/test_user_self_deletion_service_unit.py` verifies the
  self-service deletion path and protected-user guards.
- `user_session/test_session_events_unit.py` verifies session event payloads
  for the live session stream.
- `user_session/test_session_events_failure_unit.py` verifies fail-closed lease
  admission, publisher failures, invalid tokens, buffered events, and stream
  cleanup on unexpected errors or shutdown.
- `user_session/test_session_geolocation_unit.py` verifies geolocation parsing
  and privacy-safe fallback behavior.
- `user_session/test_session_repository_unit.py` verifies session queries,
  revocation, and cleanup operations.
- `user_session/test_session_service_unit.py` verifies session lifecycle
  orchestration and current-session protection.
- `valkey/test_valkey_client_unit.py` verifies client creation, reuse, and
  unavailable-service behavior.

---

## See also

- [Backend Test Map](backend.md)
- [Backend Integration Tests](backend-integration.md)
- [Backend Security and Performance](backend-security-performance.md)
- [Backend Test Map](backend.md)
- [Testing Overview](overview.md)
