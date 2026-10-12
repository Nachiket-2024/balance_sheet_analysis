"""Procrastinate App + connector setup, split from the task modules so the
`procrastinate.App` instance exists before any `@app.task`/`@app.periodic`
decorator runs. `email_tasks.py`, `account_purge_tasks.py`, and
`session_cleanup_tasks.py` all import `app` from here rather than from each
other, avoiding the circular import a single shared module would otherwise
create between them.
"""
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from importlib import import_module
from typing import Any, cast

from procrastinate import App, PsycopgConnector, exceptions
from procrastinate.app import WorkerOptions
from procrastinate.job_context import JobContext
from procrastinate.jobs import Job
from procrastinate.middleware import WorkerMiddleware, compose
from procrastinate.retry import BaseRetryStrategy, RetryDecision

from ..core.settings import settings

# Procrastinate logs each job's full call args at INFO - for send_email_task
# that's the rendered body, which embeds a raw token. WARNING keeps failure
# visibility (still ERROR) while dropping that from stdout.
logging.getLogger("procrastinate").setLevel(logging.WARNING)


@dataclass(frozen=True)
class TaskLifecycleEvent:
    """Safe metadata emitted once for every worker task attempt.

    The event intentionally excludes task arguments. Email bodies and other
    task arguments can contain credentials or one-time tokens.
    """

    job_id: int
    task_name: str
    queue: str
    attempts: int
    outcome: str
    duration_seconds: float
    error_type: str | None = None


TaskLifecycleListener = Callable[[TaskLifecycleEvent], Awaitable[None] | None]
_task_lifecycle_listeners: list[TaskLifecycleListener] = []


def register_task_lifecycle_listener(listener: TaskLifecycleListener) -> None:
    """Register an app-owned listener for worker task lifecycle events."""
    if listener not in _task_lifecycle_listeners:
        _task_lifecycle_listeners.append(listener)


async def _task_lifecycle_middleware(call_next, context: JobContext, worker):
    started = time.perf_counter()
    outcome = "succeeded"
    error_type = None
    try:
        return await call_next()
    except BaseException as exc:
        outcome = "aborted" if isinstance(exc, exceptions.JobAborted) else "failed"
        error_type = type(exc).__name__
        raise
    finally:
        if context.job.id is None:
            raise RuntimeError("Procrastinate worker context had no job ID")
        event = TaskLifecycleEvent(
            job_id=context.job.id,
            task_name=context.job.task_name,
            queue=context.job.queue,
            attempts=context.job.attempts,
            outcome=outcome,
            duration_seconds=time.perf_counter() - started,
            error_type=error_type,
        )
        for listener in tuple(_task_lifecycle_listeners):
            try:
                result = listener(event)
                if result is not None:
                    await result
            except Exception:
                logging.getLogger(__name__).exception(
                    "Task lifecycle listener failed for job %s", event.job_id
                )


def _load_dotted_callable(path: str) -> Callable[..., Any]:
    module_path, separator, attribute = path.rpartition(":")
    if not separator:
        module_path, _, attribute = path.rpartition(".")
    if not module_path or not attribute:
        raise ValueError(f"Expected dotted callable path, got {path!r}")
    return getattr(import_module(module_path), attribute)


def _configured_paths(value: str) -> list[str]:
    return [path.strip() for path in value.split(",") if path.strip()]


def _qualified_import_path(path: str) -> str:
    """Resolve Docker's top-level paths against the native test package root."""
    package_root = __package__.rsplit(".", 1)[0] if __package__ and "." in __package__ else ""
    if package_root and path.startswith(("mystic_auth.", "app.")):
        namespace = package_root.rsplit(".", 1)[0] if "." in package_root else ""
        return f"{namespace}.{path}" if namespace else path
    return path


class ExponentialBackoffWithJitter(BaseRetryStrategy):
    """Retries `max_attempts` times total, waiting `min(base_delay * 2**attempts,
    max_delay)` seconds plus a random `[0, jitter]` second offset before each
    retry. The jitter keeps many simultaneously-failing jobs (e.g. an SMTP
    outage) from all retrying on the same tick and re-hammering an
    already-struggling dependency at once.
    """

    def __init__(self, *, max_attempts: int, base_delay: float, max_delay: float, jitter: float):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def get_retry_decision(self, *, exception: BaseException, job: Job) -> RetryDecision | None:
        if job.attempts >= self.max_attempts:
            return None
        delay = min(self.base_delay * (2**job.attempts), self.max_delay)
        delay += random.uniform(0, self.jitter)  # nosec B311 - retry backoff jitter, not security/crypto use
        return RetryDecision(retry_in={"seconds": delay})


# Procrastinate needs a bare postgresql:// DSN; DATABASE_URL is SQLAlchemy's
# postgresql+asyncpg:// dialect. settings.procrastinate_database_url
# translates it. This connector opens its own psycopg connection pool,
# entirely separate from the SQLAlchemy engine database.py builds.
connector = PsycopgConnector(
    conninfo=settings.procrastinate_database_url,
    min_size=1,
    max_size=10,
)

_extension_import_paths = [
    _qualified_import_path(path)
    for path in _configured_paths(settings.PROCRASTINATE_TASK_IMPORT_PATHS)
]
_configured_worker_middleware_paths = _configured_paths(settings.PROCRASTINATE_WORKER_MIDDLEWARE_PATHS)
_configured_worker_middleware: list[WorkerMiddleware] | None = None


def _load_configured_worker_middleware() -> list[WorkerMiddleware]:
    global _configured_worker_middleware
    if _configured_worker_middleware is None:
        _configured_worker_middleware = [
            cast(WorkerMiddleware, _load_dotted_callable(path))
            for path in _configured_worker_middleware_paths
        ]
    return _configured_worker_middleware


async def _configured_worker_middleware_wrapper(call_next, context, worker):
    """Load app middleware lazily so it may import the public SDK safely."""
    configured = _load_configured_worker_middleware()
    return await compose(configured, call_next, context, worker)()


_worker_middleware: list[WorkerMiddleware] = [
    _task_lifecycle_middleware,
    _configured_worker_middleware_wrapper,
]
_worker_defaults: WorkerOptions = {"worker_middleware": _worker_middleware}

app = App(
    connector=connector,
    import_paths=[
        _qualified_import_path(path)
        for path in [
        "mystic_auth.procrastinate_tasks.email_tasks",
        "mystic_auth.procrastinate_tasks.account_purge_tasks",
        "mystic_auth.procrastinate_tasks.audit_log_tasks",
        "mystic_auth.procrastinate_tasks.session_cleanup_tasks",
        "mystic_auth.procrastinate_tasks.account_lifecycle_tasks",
        *_extension_import_paths,
        ]
    ],
    worker_defaults=_worker_defaults,
)

# The API process calls `perform_import_paths()` from `app.main` after
# `app.sdk` has finished importing. Doing it here would eagerly import a
# downstream task module while `app.sdk` is still initializing; that module is
# allowed to import the public SDK, which otherwise creates a partial-module
# circular import. The Procrastinate worker performs the imports itself when
# it starts, so this remains correct for both processes.
