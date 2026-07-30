# Background Workers (Taskiq)

## Purpose

Offloads slow, failure-prone I/O: sending email via SMTP: off the request/response cycle, so a signup/verification/password-reset request returns immediately instead of blocking on a mail server round trip.

## Architecture

`backend/mystic_auth/taskiq_tasks/email_tasks.py` defines a single [Taskiq](https://taskiq-python.github.io/) broker:

```python
result_backend = RedisAsyncResultBackend(redis_url=settings.REDIS_URL)

broker: AsyncBroker = ResilientRedisStreamBroker(
    url=settings.REDIS_URL,
).with_result_backend(result_backend).with_middlewares(
    SimpleRetryMiddleware(default_retry_count=3)
)

@broker.task(retry_on_error=True, max_retries=3)
async def send_email_task(to_email: str, subject: str, body: str, is_html: bool = True) -> bool:
    ...
```

Redis is both the broker (a Redis Stream) and the result backend: no separate message-queue infrastructure. The `taskiq_worker` container consumes the same broker, running from the identical `docker/backend.Dockerfile` image as the `backend` service, just with a different `command:` (`taskiq worker mystic_auth.taskiq_tasks.email_tasks:broker`, no `--reload`: the worker doesn't need file-watch): see [Backend Architecture](../architecture/backend.md) for why one image serves three roles (`backend`, `taskiq_worker`, `alembic`).

```mermaid
flowchart LR
    Req["Request handler<br/><small>signup / password-reset</small>"] -- ".kiq(...): returns<br/>immediately" --> Stream[("Redis Stream<br/>broker + result backend")]
    Stream --> Worker["taskiq_worker"]
    Worker -->|SMTP| Gmail[("Gmail SMTP")]
    Worker -.->|"raises on failure,<br/>up to 3 retries"| Stream
```

## Tasks

| Task | Enqueued from | Purpose |
|---|---|---|
| `send_email_task(to_email, subject, body, is_html=True)` | `auth/verify_account/account_verification_service.py`, `auth/password_logic/password_reset_service.py` | Sends the verification email and the password-reset email via the configured SMTP sender (`aiosmtplib`) |

`send_email_task` itself doesn't talk to SMTP directly: it delegates to `emails/email_sender.py::email_sender` (an `EmailSender` protocol with one concrete `SMTPEmailSender` implementation). This is not a plugin system: swapping providers (e.g. SES, SendGrid, Postmark) means writing one new class and pointing `email_sender` at it, without touching the Taskiq task or its callers.

Both call sites build the HTML body via `emails/email_template_service.py::render_transactional_email` (a shared template with the app name/support address baked in from settings), then enqueue with `.kiq(...)`:

```python
await send_email_task.kiq(
    to_email=user.email,
    subject="Verify your account",
    body=render_transactional_email(...),
)
```

`.kiq()` returns as soon as the task is enqueued in Redis: the caller (the signup/password-reset request handler) does not wait for the email to actually send. `send_email_task` logs `Sending email to {to_email}` right before handing off to `email_sender.send`, then `Email sent successfully to {to_email}` once it succeeds, both at INFO level, before returning `True`. It uses `logging_config.py::get_worker_logger()` rather than the usual `get_logger()`, so both lines are terminal-visible (`docker compose logs taskiq_worker`) instead of file-only: unlike an HTTP request, a background task has no access-log line marking when it starts/finishes, so an operator watching the terminal needs these two lines to see a send happen live, the same way Taskiq's own `Executing task ...` line already is.

## Configuration

| Setting | Purpose |
|---|---|
| `REDIS_URL` | Broker + result backend connection |
| `FROM_EMAIL` | SMTP "From" address, also the account authenticating to the SMTP server |
| `GMAIL_APP_PASSWORD` | App password for the `FROM_EMAIL` account (Gmail requires a per-app password for SMTP with 2FA enabled) |
| `SUPPORT_EMAIL` | Optional; used as the email's `Reply-To`, falls back to `FROM_EMAIL` if unset |
| `SMTP_HOST` / `SMTP_PORT` | Optional; default to `smtp.gmail.com`/`587`. Override to point `SMTPEmailSender` at a different SMTP provider |
| `APP_NAME` | Required; product name used in the email template's branding |

## Failure handling and retries

The broker runs `taskiq.SimpleRetryMiddleware`, and `send_email_task` is labeled `retry_on_error=True, max_retries=3`. On failure, `send_email_task` logs the full traceback and **raises** (rather than swallowing the exception): this is what lets the middleware see the failure and re-enqueue the task immediately (no backoff/delay: see the note below), up to 3 attempts total. A transient SMTP failure (a momentary Gmail outage, a network blip) now gets retried automatically instead of silently dropping the email.

A permanent failure (e.g. bad SMTP credentials) still exhausts all 3 attempts: each attempt logs its own traceback, and the middleware itself logs a final "Maximum retries count is reached" warning, so the failure is visible in logs even though nothing pages an operator automatically. No dead-letter queue or external alerting is configured: an operator watching logs would see it, but nothing pages anyone automatically. Left as a deployment-specific follow-up, since this template doesn't assume a specific alerting stack.

**Why no delay between retries**: `taskiq.SmartRetryMiddleware` supports exponential backoff, but only actually delays a retry when a `schedule_source` (a `TaskiqScheduler`) is configured: without one, its "delay" is a no-op label, which would be misleading to add. This project doesn't run a `TaskiqScheduler` (there's nothing else that needs one), so `SimpleRetryMiddleware`'s immediate re-enqueue is the correct, honest choice for the one task this app has.

## Redis stream recovery

`RedisStreamBroker.startup()` eagerly runs `XGROUP CREATE ... MKSTREAM` (atomically creating both the stream and the consumer group) and is `await`ed by Taskiq's own `Receiver.listen()` before the read loop starts. With 2 worker processes (`WorkerArgs.workers` default) both calling `startup()` independently, whichever process loses the `XGROUP CREATE` race gets a `BUSYGROUP` error, which the broker catches and logs at `debug` level.

That protects normal fresh-Redis startup, but it does not protect the worker if the stream or consumer group disappears after startup. A Redis `FLUSHDB`, cache reset, or test run sharing the live worker's Redis DB can delete the `taskiq` stream while workers are blocked in `XREADGROUP`, causing a `NOGROUP` response. `ResilientRedisStreamBroker` wraps the pinned `taskiq-redis` broker and handles that case by logging a warning, re-declaring the consumer group, and resuming listening.

It also handles a dropped Redis connection while blocked in `XREADGROUP` (for example, if Redis is restarted underneath the worker): it logs a warning, waits briefly, and re-enters the listener so the broker gets a fresh Redis connection instead of crashing the worker process. Other Redis errors still propagate.

Regression tests in `tests/backend/mystic_auth/unit/taskiq_tasks/test_email_tasks_unit.py` cover these mechanisms: `mkstream=True` + graceful `BUSYGROUP` handling for startup, re-declaration after a runtime `NOGROUP`, and reconnect after a runtime connection drop.

## Testing

`tests/backend/mystic_auth/unit/taskiq_tasks/test_email_tasks_unit.py` exercises `send_email_task` directly: the success path, the failure-raises-for-retry path, that the broker's retry middleware and the task's `retry_on_error`/`max_retries` labels are actually configured, and the fresh-Redis startup race guard above. The call sites (`account_verification_service.py`, `password_reset_service.py`) are separately tested with `send_email_task.kiq` mocked/patched. See [Testing Overview](../testing/overview.md).

## Troubleshooting

- **Worker not picking up tasks**: confirm `taskiq_worker` can reach `REDIS_URL`: same Redis instance the `backend` container uses. `./scripts/dev-up.sh`, `.\scripts\dev-up.ps1`, and `scripts\dev-up.cmd` now include `taskiq_worker` in their live log tail; `docker compose logs taskiq_worker` still shows only the worker.
- **Emails not arriving**: check `GMAIL_APP_PASSWORD` is a valid App Password (not the account password) and that "Less secure app access" / App Passwords are enabled on the sending Google account; check the dev-up log tail or `docker compose logs taskiq_worker` for the logged traceback (`send_email_task` logs every failure with `logger.error`).
