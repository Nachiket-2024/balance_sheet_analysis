# Known Issues, Limitations & Technical Debt

Tracked deliberately rather than left as silent gaps. Each entry reflects an active, unresolved limitation in the current implementation: nothing speculative, and nothing already fixed (resolved items live in the relevant feature documentation instead).

## Security

### Database backups are scripted, but not scheduled

**Description**: [Deployment Guide](../deployment/guide.md#backups) documents `scripts/db/db_backup.sh`/`scripts/db/db_restore.sh`, which wrap the `pg_dump`/`psql` commands (environment-driven, Docker-only, no cloud assumptions). What's still missing is a *scheduler*: these scripts still need to be wired into cron, systemd, a host backup feature, or a sidecar, since no specific production host is assumed by this template.

**Impact**: Data loss risk in any real deployment until an operator wires the scripts into a schedule.

**Why it exists**: No specific production host/cloud target is assumed by this template, so there's nothing to hang a cron job on generically.

**Possible fix**: Add a cron entry, systemd timer, host backup feature, or sidecar container that calls `scripts/db/db_backup.sh` on a schedule. This is deployment-specific and left to whoever deploys this.

**Priority**: High for any real production use, N/A for local development.

---

## Configuration

### One global rate-limit threshold for every endpoint

**Description**: `MAX_REQUESTS_PER_WINDOW`/`REQUEST_WINDOW_SECONDS` is one shared setting applied identically to every `@rate_limited(...)` endpoint, including signup, login, OAuth2, and password reset. `/auth/refresh/` is not rate-limited by this mechanism. There is no per-endpoint override.

**Impact**: A threshold tuned for, say, login (a frequently-hit route) may be too permissive or too strict for a rarer route like password-reset-request.

**Why it exists**: Simplicity: one setting to reason about. The login-specific brute-force lockout (`login_protection_service.py`) layers a second, endpoint-specific control on top for the one route that most needs it.

**Possible fix**: Extend `rate_limited(...)` to accept optional per-call overrides, defaulting to the global setting.

**Priority**: Low, since the current layering (generic global limit + login-specific lockout) covers the highest-risk route already.

---

## CI/CD

### No deploy automation

**Description**: `docker-build` in CI verifies that both Dockerfiles build but does not push to a registry or deploy anywhere.

**Why it exists**: This is a template repository with no assumed production target. See [Deployment Guide](../deployment/guide.md#production-host-requirements). Adding a deploy stage would need to assume a specific host.

**Priority**: N/A, an intentional scope boundary, not a gap.

### Performance tests are non-blocking in CI

**Description**: The backend `performance` suite (`tests/backend/mystic_auth/performance`) runs in CI with `continue-on-error: true`, so a failure there is visible but never fails the build.

**Impact**: A genuine performance regression could land on `main` without CI stopping it. Only a human reviewing that job's result would catch it.

**Why it exists**: These tests assert generous regression-alarm thresholds against a real Postgres/Redis, so timing is inherently noisier than a correctness test on shared/loaded runners: a slow CI runner or concurrent load can trip a timing assertion with no actual code regression behind it (observed directly during this repo's own manual test runs).

**Possible fix**: Tighten the thresholds and/or the runner environment until false positives are rare enough to make the job blocking, or move to a dedicated, less noisy performance-testing environment instead of sharing CI's general-purpose runners.

**Priority**: Low. Correctness is still enforced elsewhere through blocking unit, integration, and security suites. This only affects how fast a real performance regression would be noticed.
