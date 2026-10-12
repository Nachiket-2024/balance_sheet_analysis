# tests/backend/mystic_auth/integration/audit_log/conftest.py
#
# Runs the real `procrastinate ... worker` CLI as a subprocess for the
# whole test session, pointed at this suite's database. A plain local
# `pytest` run has no separate `procrastinate_worker` container, and audit
# log rows (see authorization_audit_logger.log_decision) only appear once
# some worker consumes the queue. poll_for_entries
# (audit_log_test_accounts.py) polls for exactly that, so without a worker
# draining the queue it always times out and sees nothing.
#
# A real subprocess, not an in-process asyncio worker task: an earlier
# version ran a `procrastinate.worker.Worker` loop as a background asyncio
# task inside the test process, and it reliably deadlocked partway through
# a run, most likely fighting the top-level conftest's per-test connector
# cycling over an event loop. A separate OS process has its own event loop
# entirely, so it can't collide no matter how this suite's fixtures churn.
#
# Scoped to this directory, not the top-level conftest.py: the rest of the
# real-DB suite doesn't defer/poll through the audit log, so there's no
# reason to pay for a worker process there.
import os
import subprocess
import time
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[5] / "backend"


@pytest.fixture(scope="session", autouse=True)
def _run_procrastinate_worker(tmp_path_factory: pytest.TempPathFactory):
    # Same command docker/mystic_auth/compose/docker-compose.dev.yml's procrastinate_worker service runs,
    # with the same cwd (`backend/`, so `mystic_auth...` resolves like it
    # does inside the container's /app), just as a host process against
    # this session's Postgres.
    #
    # PYTHONPATH must be set explicitly to match the container's
    # `PYTHONPATH=/app`: unlike `python -m`, the `procrastinate` console
    # script doesn't add its cwd to sys.path, so without this
    # `import mystic_auth...` fails and the subprocess exits immediately
    # (silently, since nothing here reads its output, so the fixture looked
    # like it started a worker while every test ran with none).
    # EMAIL_ENABLED=false rides along via the env copy, so this real worker
    # doesn't also try to send real verification/reset emails.
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_BACKEND_DIR)
    log_path = tmp_path_factory.mktemp("audit-log-worker") / "procrastinate_worker.log"
    log_file = log_path.open("w")
    proc = subprocess.Popen(
        ["procrastinate", "--app=mystic_auth.procrastinate_tasks.procrastinate_app.app", "worker"],
        cwd=_BACKEND_DIR,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    # No readiness signal on stdout to wait on, so instead of guessing a
    # fixed sleep, poll the same `procrastinate ... healthchecks` command
    # docker/mystic_auth/compose/docker-compose.dev.yml's own healthcheck uses (confirms the DB connection
    # and procrastinate_jobs table are reachable), up to
    # READINESS_TIMEOUT_SECONDS. A fixed 1s sleep here previously raced the
    # first tests in a full run: cold module imports for this subprocess
    # sometimes took longer than that, so the first test(s) deferred a job
    # the worker wasn't listening for yet, and it sat unprocessed until
    # poll_for_entries gave up. That was a real, observed flake, not a bug
    # in the code under test.
    READINESS_TIMEOUT_SECONDS = 15.0
    deadline = time.monotonic() + READINESS_TIMEOUT_SECONDS
    ready = False
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        check = subprocess.run(
            ["procrastinate", "--app=mystic_auth.procrastinate_tasks.procrastinate_app.app", "healthchecks"],
            cwd=_BACKEND_DIR,
            env=env,
            capture_output=True,
            check=False,
        )
        if check.returncode == 0:
            ready = True
            break
        time.sleep(0.2)
    if proc.poll() is not None:
        log_file.close()
        raise RuntimeError(
            f"procrastinate worker subprocess exited immediately (code {proc.returncode}); "
            f"see {log_path}"
        )
    if not ready:
        proc.terminate()
        proc.wait(timeout=10)
        log_file.close()
        raise RuntimeError(
            f"procrastinate worker subprocess did not become ready within "
            f"{READINESS_TIMEOUT_SECONDS}s; see {log_path}"
        )
    yield
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    log_file.close()
