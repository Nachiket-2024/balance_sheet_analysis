# Known Issues, Limitations & Technical Debt

Tracked deliberately rather than left as silent gaps. Each entry reflects an active, unresolved limitation in the current implementation: nothing speculative, and nothing already fixed (resolved items live in the relevant feature documentation instead).

## Security

### Database backups are scripted, but not scheduled

**Description**: [Deployment Guide](../deployment/guide.md#backups) documents `scripts/db_backup.sh`/`scripts/db_restore.sh`, which wrap the `pg_dump`/`psql` commands (environment-driven, Docker-only, no cloud assumptions). What's still missing is a *scheduler*: these scripts still need to be wired into cron/systemd/a managed provider's backup feature/a sidecar, since no specific production host/cloud target is assumed by this template.

**Impact**: Data loss risk in any real deployment until an operator wires the scripts into a schedule.

**Why it exists**: No specific production host/cloud target is assumed by this template, so there's nothing to hang a cron job on generically.

**Possible fix**: Add a cron entry / systemd timer / managed Postgres provider's built-in backups / sidecar container that calls `scripts/db_backup.sh` on a schedule; this is provider-specific, left to whoever deploys this.

**Priority**: High for any real production use, N/A for local development.

## Configuration

### One global rate-limit threshold for every endpoint

**Description**: `MAX_REQUESTS_PER_WINDOW`/`REQUEST_WINDOW_SECONDS` is one shared setting applied identically to every `@rate_limited(...)` endpoint (signup, login, OAuth2, password reset, etc., but not `/auth/refresh/`, which isn't rate-limited by this mechanism at all); there's no per-endpoint override.

**Impact**: A threshold tuned for, say, login (a frequently-hit route) may be too permissive or too strict for a rarer route like password-reset-request.

**Why it exists**: Simplicity: one setting to reason about. The login-specific brute-force lockout (`login_protection_service.py`) layers a second, endpoint-specific control on top for the one route that most needs it.

**Possible fix**: Extend `rate_limited(...)` to accept optional per-call overrides, defaulting to the global setting.

**Priority**: Low, since the current layering (generic global limit + login-specific lockout) covers the highest-risk route already.

## CI/CD

### No deploy automation

**Description**: `docker-build` in CI verifies both Dockerfiles build but does not push to a registry or deploy anywhere.

**Why it exists**: Deliberate: this is a template repository with no assumed production target (see [Deployment Guide](../deployment/guide.md#free--low-cost-hosting-options) for provider-agnostic options); adding a deploy stage would need to assume a specific host.

**Priority**: N/A, an intentional scope boundary, not a gap.
