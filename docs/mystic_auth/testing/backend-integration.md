# Backend Integration Tests
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

These 48 pytest modules exercise MysticAuth through real application
boundaries. Fixtures create database rows, issue requests, and use Valkey when
the workflow depends on sessions, rate limits, authorization caching, or
background state. The purpose is to prove that separately correct units still
behave correctly when transactions, persistence, cache invalidation, and
concurrent requests interact.

Test-account helpers that assign policies directly through the repository pass
the affected user's email so the authorization cache is invalidated exactly as
it is for an API assignment. This is required before issuing requests as the
newly privileged account; otherwise a cached pre-assignment policy list can
produce a misleading `403` in an otherwise valid integration test.

---

## Audit log

- `audit_log/test_audit_log_automatic_logging_integration.py` verifies that
  important authentication and authorization actions automatically create
  audit records with the right actor, target, outcome, and metadata.
- `audit_log/test_audit_log_query_api_integration.py` verifies authenticated
  audit-log querying, pagination, sorting, and scope restrictions.
- `audit_log/test_audit_log_query_edge_cases_integration.py` verifies empty
  results, malformed filters, boundary dates, and unusual pagination inputs.
- `audit_log/test_security_audit_log_integration.py` verifies security-event
  creation and access through the security audit API.
- `audit_log/test_security_audit_log_queries.py` verifies category, actor,
  event, date, and text query behavior for security events.

## Authentication

- `auth/test_login_integration.py` verifies the complete login request,
  password check, token issuance, cookie state, and audit outcome.
- `auth/test_login_lockout_race_integration.py` verifies concurrent failed
  logins cannot bypass account or IP lockout thresholds.
- `auth/test_login_security_controls_integration.py` verifies rate limiting,
  generic errors, lockout, and security audit behavior together.
- `auth/test_logout_integration.py` verifies session invalidation and cookie
  clearing for logout and logout-all paths.
- `auth/test_oauth_integration.py` verifies provider callback handling,
  account linking, PKCE/state validation, and duplicate identity behavior.
- `auth/test_password_reset_integration.py` verifies reset email initiation,
  token confirmation, expiry, replay prevention, and password change effects.
- `auth/test_protected_action_reservation_integration.py` verifies that
  sensitive actions reserve and consume the expected session/auth state.
- `auth/test_refresh_token_integration.py` verifies refresh rotation,
  replay-chain revocation, cookies, and persistence across requests.
- `auth/test_signup_verify_concurrency_integration.py` verifies concurrent
  signup and verification requests do not create inconsistent accounts.

## Authorization and PBAC

- `authorization/test_authorization_cache_invalidation_integration.py`
  verifies policy, role, and direct-grant changes invalidate cached decisions.
- `authorization/test_authorization_check_integration.py` verifies route-level
  allow/deny decisions against persisted roles, policies, and grants.
- `authorization/test_bulk_permission_assignment_integration.py` verifies
  bulk direct-permission assignment, per-item results, and transactions.
- `authorization/test_bulk_policy_assignment_integration.py` verifies bulk
  policy assignment, partial failures, and authorization of the operation.
- `authorization/test_bulk_role_assignment_integration.py` verifies role bulk
  updates and their effect on effective permissions.
- `authorization/test_context_based_authorization_integration.py` verifies
  conditions using request, resource, network, and temporal context.
- `authorization/test_permission_assignment_integration.py` verifies direct
  grant and revoke persistence and effective permission changes.
- `authorization/test_permission_catalog_integration.py` verifies the exposed
  permission catalog matches persisted and default definitions.
- `authorization/test_permission_catalog_usage_integration.py` verifies usage
  counts and references reported for catalog permissions.
- `authorization/test_policy_action_revocation_integration.py` verifies that
  revoking one policy action removes only the intended effective action.
- `authorization/test_policy_action_separation_integration.py` verifies
  action-level separation between related policy permissions.
- `authorization/test_policy_assignment_integration.py` verifies policy
  assignment, removal, and resulting effective permissions.
- `authorization/test_policy_concurrency_integration.py` verifies concurrent
  policy mutations do not lose updates or bypass constraints.
- `authorization/test_policy_crud_integration.py` verifies policy creation,
  update, deletion, validation, and audit history through the API.
- `authorization/test_policy_list_integration.py` verifies policy listing,
  filtering, pagination, and authorization boundaries.
- `authorization/test_purge_cache_invalidation_integration.py` verifies user
  purge removes authorization cache state and stale grants.

## Core and rate limits

- `core/test_health_integration.py` verifies health endpoints against actual
  dependency checks and deployment configuration.
- `core/test_security_headers_integration.py` verifies security headers,
  CORS behavior, and response policy at the application boundary.
- `rate_limits/test_rate_limit_dashboard_edge_cases_integration.py` verifies
  malformed keys, scan limits, empty data, and safe dashboard aggregation.
- `rate_limits/test_rate_limit_routes_integration.py` verifies listing,
  filtering, reset idempotency, concurrency, and rate-limit permissions.

## Users and lifecycle

- `user/test_account_purge_task_integration.py` verifies scheduled purge work
  removes expired accounts and dependent data.
- `user/test_user_account_lifecycle_integration.py` verifies deletion,
  reactivation, and lifecycle permissions across persisted state.
- `user/test_user_admin_lifecycle_valkey_outage_integration.py` verifies safe
  permission-protected lifecycle behavior when Valkey is unavailable.
- `user/test_user_admin_listing_integration.py` verifies permission-protected listing,
  filtering, pagination, and effective access data.
- `user/test_user_admin_management_integration.py` verifies permission-protected profile,
  role, status, and permission-management operations.
- `user/test_user_export_integration.py` verifies authorized export contents,
  filtering, and data handling.
- `user/test_user_list_and_update_integration.py` verifies user listing and
  update authorization, validation, and persistence.
- `user/test_user_self_service_account_deletion_integration.py` verifies the
  authenticated user's deletion flow and protected-account rules.
- `user/test_user_self_service_logout_after_password_change_integration.py`
  verifies password change invalidates the expected sessions.
- `user/test_user_self_service_routes_integration.py` verifies profile,
  password, and self-service routes with persisted user state.

## Sessions

- `user_session/test_manage_sessions_concurrency_integration.py` verifies
  concurrent session revocation remains consistent.
- `user_session/test_manage_sessions_integration.py` verifies session listing,
  current-device labeling, revoke behavior, and authorization.
- `user_session/test_session_geolocation_integration.py` verifies persisted
  geolocation lookup and privacy-safe fallback behavior.
- `user_session/test_session_row_cleanup_integration.py` verifies stale session
  rows are removed without deleting active sessions.

---

## See also

- [Backend Test Map](backend.md)
- [Backend Unit Tests](backend-unit.md)
- [Backend Security and Performance](backend-security-performance.md)
- [Backend Test Map](backend.md)
- [Testing Overview](overview.md)
