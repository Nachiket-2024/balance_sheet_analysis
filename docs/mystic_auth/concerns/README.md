# Known Issues, Limitations & Technical Debt
---

Tracked deliberately rather than left as silent gaps. Each entry reflects an active, unresolved limitation in the current implementation: nothing speculative, and nothing already fixed (resolved items live in the relevant feature documentation instead).

---

## Security

---

### Database backups are scheduled, integrity-checked, and shipped to Backblaze B2, but there's still no point-in-time recovery

**Description**: `docker-compose.prod.yml` and every `docker-compose.local-prod-*.yml` variant run a `db_backup` service by default: a loop that calls `pg_dump --format=custom` on an interval (`BACKUP_INTERVAL_HOURS`), immediately verifies the dump with `pg_restore --list`, writes it to `./backups`, and uploads it to a configured Backblaze B2 bucket with `rclone`, deleting local dumps older than `BACKUP_RETENTION_DAYS`. `scripts/mystic_auth/db/database-backup/database-backup.sh` (manual/on-demand backups) uses the same `DUMP_FILE` upload hook. Dump, verification, and upload failures are reported through the Sentry-compatible Bugsink DSN as well as causing the backup command/service to fail. `scripts/mystic_auth/db/backup-verification/backup-freshness-check.sh` separately verifies that the required local dump artifacts are present, non-empty, and within the configured age window.

**Impact**: One recovery-model limitation remains, plus deployment-specific B2 operations:
- **No point-in-time recovery**: this is periodic full dumps only, so worst-case data loss is up to `BACKUP_INTERVAL_HOURS` of writes, not "up to the last transaction" the way WAL-based continuous archiving gives you.
- **B2 is configuration-dependent**: production-shaped Compose modes refuse to start without `BACKUP_UPLOAD_COMMAND`, but the bucket, application key, and destination ownership remain deployment-specific. The freshness script cannot prove that an off-host object exists; the B2 bucket still needs its own monitoring. The first 10 GB is free without a billing method, but usage above the free allowance is not free. This repository's configured local-prod-ngrok B2 path has been tested by uploading both databases and fully restoring both from downloaded remote objects.

**What PITR means**: Point-in-time recovery continuously archives PostgreSQL's write-ahead logs (WAL), allowing an operator to restore to a selected timestamp, such as immediately before an accidental deletion. The current full-dump schedule instead restores the most recent completed dump; with a 24-hour interval, the theoretical recovery-point objective (RPO) can be almost 24 hours. This is acceptable for local or low-criticality deployments when the documented dump, freshness, off-host-copy, and restore-drill checks are performed. PITR becomes appropriate when losing more than a small number of minutes of writes is unacceptable, or when audit/business requirements demand transaction-level recovery.

**Why PITR is not enabled yet**: integrating WAL archiving requires a dedicated tool (`pgBackRest`, `WAL-G`) or a managed PostgreSQL provider, plus retention, key management, WAL storage, restore testing, and monitoring. That is more operational surface area than this periodic dump loop was designed for. The current B2 upload, Bugsink failure reporting, and full remote restore are verified; each deployment still has to create and protect its own bucket and application key, then repeat the restore check after deployment.

**Possible fix**: For real uptime/RPO requirements, replace the whole mechanism with `pgBackRest`/`WAL-G` or a managed Postgres provider's own backup feature instead of extending this loop further.

**Priority**: Low/Medium for a deployment beyond local/self-hosted testing - lower than before now that off-host shipping just needs one env var set, rather than a missing mechanism. Still Medium if PITR-level RPO actually matters for the data involved (this app stores password hashes, sessions, audit logs). Low/N/A for local development or a throwaway deployment.

---

### Secrets rotation is only half-automated

**Description**: `scripts/mystic_auth/env-tools/rotate-secrets/` rotates `SECRET_KEY` and `BUGSINK_SECRET_KEY` cleanly, since both are pure env-file values with no live-database counterpart to update. `POSTGRES_PASSWORD`, `APP_DB_PASSWORD`, and `BUGSINK_SUPERUSER_PASSWORD` are documented in that script's own header as needing a manual live-database step (`ALTER USER ... PASSWORD`, then restarting the dependent services) instead, since rotating those requires touching a running Postgres role, not just a file.

**Impact**: An operator rotating credentials has to know, separately from the tool, which three fields need that extra manual step. Skipping it (assuming the rotate script alone was enough) leaves the env file and the live database role out of sync, and the affected service fails to authenticate on its next restart.

**Why it exists**: The rotate script only ever touches env files, deliberately, so it never needs live database credentials or a running stack to work. Extending it to also run the `ALTER USER` step means giving it DB connectivity and admin rights it doesn't otherwise need, a real increase in what the script can do and what could go wrong if run against the wrong target.

**Possible fix**: A guided companion script (or an extra flag on the existing one) that, for these three fields only, connects to the live database with the current credentials, runs the `ALTER USER` statement, writes the new value to the env file, and restarts the dependent service, all as one confirmed step instead of a manual runbook.

**Priority**: Low. The manual step is documented at the point of use, and the failure mode (a service failing to authenticate) is loud and immediate, not silent.

---

## Dependencies

---

### Dependency updates are manual by design

**Description**: No automated dependency-update bot is used. `pip-audit`/`npm audit` in CI catch known CVEs in whatever versions are currently pinned, while version updates are reviewed and batched manually.

**Why it exists**: This repo ran Dependabot earlier and turned it off. Its PRs updated packages independently of each other (for example bumping TypeScript without ESLint's TypeScript-parsing plugins in the same PR), which produced breakage from version skew between packages that need to move together, not from the updates themselves. Manual, batched updates (bumping a related group together, then running the full test suite once) avoid that failure mode, at the cost of updates happening less often.

**Impact**: A non-CVE release will wait for the next deliberate maintenance pass. Known-CVE coverage remains available through `pip-audit`/`npm audit`.

**Operating choice**: Keep dependency updates manual and batched. Automated update PRs are intentionally out of scope because related packages need to move together and this repository does not want a bot opening independent version-skew changes.

**Priority**: Low. Known-CVE coverage already exists via `pip-audit`/`npm audit`; this gap is specifically about staying current on non-CVE releases.

---

## CI/CD

---

### No deploy automation

**Description**: `docker-build` in CI verifies that both Dockerfiles build but does not push to a registry or deploy anywhere.

**Why it exists**: This is a template repository with no assumed production target. See [Deployment Guide](../deployment/production-host.md). Adding a deploy stage would need to assume a specific host.

**Priority**: N/A, an intentional scope boundary, not a gap.

---

### Performance tests are non-blocking in CI

**Description**: The backend `performance` suite (`tests/backend/mystic_auth/performance`) runs in CI with `continue-on-error: true`, so a failure there is visible but never fails the build.

**Impact**: A genuine performance regression could land on `main` without CI stopping it. Only a human reviewing that job's result would catch it.

**Why it exists**: These tests assert generous regression-alarm thresholds against a real Postgres/Valkey, so timing is inherently noisier than a correctness test on shared/loaded runners: a slow CI runner or concurrent load can trip a timing assertion with no actual code regression behind it (observed directly during this repo's own manual test runs).

**Possible fix**: Tighten the thresholds and/or the runner environment until false positives are rare enough to make the job blocking, or move to a dedicated, less noisy performance-testing environment instead of sharing CI's general-purpose runners.

**Priority**: Low. Correctness is still enforced elsewhere through blocking unit, integration, and security suites. This only affects how fast a real performance regression would be noticed.

### Lighthouse baseline is local and has no INP sample

**Description**: An earlier production frontend build was measured with
Lighthouse 12.8.2 against the rebuilt local ngrok stack, using an authenticated local
operator for the protected routes. The original mobile runs reported login
LCP 4.943 s, dashboard LCP 5.017 s, and audit log LCP 4.735 s. Their
diagnostics identified the page greeting or audit-log subtitle as the LCP
element, with about 89-91% of LCP in render delay, no API load delay, and no
image or font load delay. The initial bundle also loaded all four language
packs before the first render.

The fix keeps English translations on the initial path, loads the other
language packs only when selected, and preloads the production stylesheet
without making it render-blocking. The HTML boot shell remains visible until
the first application frame, so the browser can paint a small accessible
loading surface while the authenticated app shell and route code start. A
single authenticated mobile Lighthouse 13.5.0 run against the rebuilt current
local-prod-ngrok stack reported login LCP 4.265 s, dashboard LCP 4.255 s, and
audit log LCP 4.214 s - slower than the earlier local values on all three
pages, and unusual in its own right: three otherwise-different pages
converging on nearly the same number is not what a real page-specific
regression looks like. That run was flagged as unconfirmed rather than
recorded as a regression, and repeated under a controlled measurement
instead of another full Lighthouse pass: a direct `PerformanceObserver`
largest-contentful-paint reading (Chrome DevTools Protocol, 4x CPU
throttling, a Fast-3G-equivalent network profile, the LCP value read after a
6-second settle window so an async-loaded table's own paint counts), two
runs per page. That came back low-variance and consistent with the original
baseline: login ~2.71-2.75 s, dashboard ~2.88-2.90 s, audit log ~2.99-3.06 s.
Login in particular improved over its original 4.021 s. The single slow
Lighthouse run is treated as measurement noise (this machine ran many
concurrent Docker rebuilds and Chromium instances around that time, not a
controlled environment), not a real regression from the boot-shell changes -
`/health/ready` responded in ~5 ms locally, unaffected. Treat
either single-run number as a lab data point, not a certified value: a
downstream deployment should repeat this against its real domain, device
profile, and a quiet, dedicated measurement environment before setting a
performance budget.

The earlier desktop results were: login LCP 0.947 s, CLS 0.000, score 0.99;
dashboard LCP 1.006 s, CLS 0.000, score 0.98; audit log LCP 0.956 s, CLS
0.000, score 0.98. Lighthouse did not report INP for these navigation-mode
runs because they contained no real user interaction. An INP value needs a
Lighthouse timespan or user-flow run that records an interaction.

**Impact**: The confirmed mobile LCP (the low-variance repeated measurement,
not the single anomalous Lighthouse run) is ~2.7-3.1 s across all three
pages, below 4 s and improved on login specifically versus the original
baseline. It remains above the 2.5 s good threshold. The boot shell provides
the first visible loading surface while the app initializes. The authenticated
page content still needs a real-device measurement before a stricter budget
is set. The desktop values remain below the good threshold.

**Why it exists**: The template does not have a fixed production host or
network profile. The initial mobile problem was client startup work, not a
slow authenticated API response. A downstream deployment should repeat the
measurement against its real domain and authenticated pages before setting a
performance budget.

**Priority**: Medium before a public launch; low for local development.

---

## Operations and scale

---

### Horizontal scaling is documented but not a maintained deployment

**Description**: Production-shaped Compose files are designed for one host.
Worker sizing uses the host's available cores. The deployment guide now
documents the multi-host path in [Running multiple backend containers](../deployment/environment.md#8-running-multiple-backend-containers):
shared Postgres and Valkey, one migration runner, cookie-based sessions with
no sticky-session requirement, and a load balancer using `/health/ready`.
There is still no maintained provider-specific deployment or working
multi-host Compose example.

**Impact**: A service that outgrows one VPS needs an architecture decision for
shared Postgres, Valkey, worker concurrency, migrations, sticky-free sessions,
health checks, and deployment coordination.

**Possible fix**: Validate the documented topology in a downstream deployment
or a separate reference deployment rather than assuming one provider in the
template.

**Priority**: Low for the template; high only when one host is approaching its
capacity limit.

---

### Automated keyboard coverage is not full accessibility coverage

**Description**: The Playwright axe scan covers common markup, contrast, and
ARIA problems. The Chromium browser pass covered the pre-auth flows, OAuth,
password reset, dashboard, users, audit-log tabs, settings, account deletion,
CRUD dialogs, Escape handling, and focus restoration. The targeted dialog
tests passed for moving focus into dialogs and returning it to the trigger.
The keyboard pass also checked route controls, OAuth reachability, audit-log
tabs, and keyboard activation of pre-auth actions. Focus-visible styles were
checked against the focusable components and shared button/input variants.
Orca 50.2, AT-SPI2, and speech-dispatcher are installed on this host, but this
session has no audio device and Orca reports no running desktop application.
No human screen-reader listening pass is therefore claimed.

**Impact**: A clean automated scan and passing browser assertions are useful
evidence, but they are not a claim of full WCAG conformance. Screen-reader
announcement quality and a human keyboard pass with real assistive technology
remain open. No screen-reader coverage is claimed.

**Possible fix**: Run Orca from a graphical Linux session with working audio,
then repeat the signup, login, and one CRUD flow. Repeat the full keyboard pass
after substantial UI changes and add stable regression tests for specific bugs
that are found. Keep testing application-owned routes separately.

**Priority**: Medium before a public launch; low for internal tooling.

---
