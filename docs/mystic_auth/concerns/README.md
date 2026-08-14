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

## Background Workers

### No dead-letter queue or alerting for permanently-failed emails

**Description**: `send_email_task` ([Background Email Delivery](../background-workers/taskiq.md)) retries up to 3 times with backoff, but a permanent failure (bad SMTP credentials, a bounced/invalid address) still exhausts all attempts and the email is simply dropped. Each attempt logs a full traceback and the middleware logs a final "Maximum retries count is reached" warning, but nothing stores the failed job anywhere queryable, and nothing pages an operator.

**Impact**: A permanently-failed verification or password-reset email is only discoverable by an operator actively reading logs. There is no way to list or replay failed sends after the fact.

**Why it exists**: This template doesn't assume a specific alerting stack (PagerDuty, Slack webhook, etc.), so wiring one up would bake in an opinion the template doesn't otherwise take.

**Possible fix**: Write failed jobs (to_email, subject, error) to a Postgres table or a separate Redis list on final retry exhaustion, so they're queryable/replayable; optionally push a metric or alert from that write.

**Priority**: Low at current scale (one task type, low email volume); worth revisiting before relying on this for anything higher-stakes than dev/small deployments.

### `taskiq_scheduler` is a single point of failure for retry delivery

**Description**: `SmartRetryMiddleware` writes each retry's due-time to a Redis-backed `schedule_source`, but only the `taskiq_scheduler` container polls that store and re-enqueues due retries. If `taskiq_scheduler` is down, the first attempt still runs and still logs its failure, but the scheduled retry silently never fires: no error is raised anywhere, since nothing is meant to be reading the schedule source at that moment.

**Impact**: A failed email send goes unretried for as long as `taskiq_scheduler` is down, with no direct signal beyond noticing the container isn't healthy (`docker compose ps taskiq_scheduler`) or the absence of a "sending" log line that should have followed.

**Why it exists**: `taskiq`'s scheduler is a separate process by design (see [Background Email Delivery: why a separate scheduler process](../background-workers/taskiq.md#failure-handling-and-retries)); running only one instance of it is the simplest option, but reintroduces a single point of failure the way the immediate-retry `SimpleRetryMiddleware` this replaced didn't have.

**Possible fix**: Run more than one `taskiq_scheduler` replica (safe: `TaskiqScheduler` polling is idempotent against the same schedule source), or add a healthcheck-based alert distinct from the general container-restart policy.

**Priority**: Low at current scale; the container's own `restart: unless-stopped` policy and healthcheck already recover from crashes, this only matters for the window between a crash and the restart.

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
