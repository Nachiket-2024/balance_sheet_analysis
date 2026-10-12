# Backend Security and Performance Tests
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

Security tests are not broad happy-path tests. Each one expresses a threat
model and checks that an attacker-controlled input cannot cross a privilege or
data boundary. Performance tests are informational regression checks. They
help identify an accidental cost increase, but they are not production load
tests and should not be used as a capacity guarantee.

---

## Security tests

- `tests/backend/mystic_auth/security/test_batch_authorization_abuse_security.py`
  sends oversized or abusive batch authorization requests and verifies that
  limits and independent decisions prevent amplification. It must never allow
  an oversized/unauthenticated batch to trigger evaluation or expose a denied
  policy name.
- `tests/backend/mystic_auth/security/test_context_spoofing_security.py`
  attempts to forge request or resource context and verifies that policy
  evaluation uses trusted server-built context. Client-supplied proxy IP or
  time must never change an authorization decision.
- `tests/backend/mystic_auth/security/test_invalid_condition_payload_security.py`
  submits malformed or unsafe policy conditions and verifies fail-closed
  validation rather than evaluator bypass. Malformed, oversized, or deeply
  nested input must never crash the service, bypass evaluation, or persist.
- `tests/backend/mystic_auth/security/test_least_privilege_db_role.py`
  runs database actions through the restricted application role and verifies
  the role has only the intended privileges. It is skipped when the restricted
  deployment database is not configured. The application role must never run
  DDL, create/alter roles, or be a superuser.
- `tests/backend/mystic_auth/security/test_permission_grant_escalation_security.py`
  attempts to grant permissions the caller cannot grant and verifies the
  grant guard blocks escalation. A caller must never self-grant a sensitive
  action, and one denied bulk item must never authorize that item.
- `tests/backend/mystic_auth/security/test_policy_tampering_security.py`
  attempts unauthorized changes to protected or baseline policy data. Baseline
  policies must never be renamed/deleted and the last protected holder must
  never be removed.
- `tests/backend/mystic_auth/security/test_privilege_escalation_security.py`
  combines role, policy, direct-grant, and protected-user operations to verify
  that ordinary callers cannot grant themselves privileged capabilities. No ordinary caller may
  mint, assign, roll back, or repoint a policy into an unheld sensitive action.

Together these files protect input validation, authorization context, grant
authority, database deployment privileges, and bootstrap-policy integrity.

---

## Performance tests

- `tests/backend/mystic_auth/performance/test_authorization_performance.py`
  measures repeated and batch authorization checks so query count or cache
  regressions are visible. Its timing is an early-warning budget, not a
  correctness or production-capacity proof; shared-runner jitter can fail it.
- `tests/backend/mystic_auth/performance/test_login_and_audit_log_performance.py`
  measures concurrent login and audit-log query paths, including the database
  work that can make security controls expensive. Its timing is likewise
  environment-dependent and does not prove absence of a security timing leak.

The real-account browser matrix has a separate known timing issue: WebKit can
race cookie commit immediately after a successful `page.request.post`, so the
test retries `/auth/me` once after 150 ms. This is a browser fixture timing
race, not an authorization failure; repeated failures after the retry are real
failures. See the matrix entry in [Frontend Browser E2E Tests](frontend-e2e.md).

These tests are commonly run with a non-blocking CI policy because timing is
environment-sensitive. A failure should trigger investigation, not an
automatic claim that the security or functional contract is broken.

---

## See also

- [Backend Test Map](backend.md)
- [Backend Unit Tests](backend-unit.md)
- [Backend Integration Tests](backend-integration.md)
- [Backend Test Map](backend.md)
- [Testing Overview](overview.md)
