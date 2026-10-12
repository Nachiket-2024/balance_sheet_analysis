from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.procrastinate_tasks import procrastinate_app as module


@pytest.fixture(autouse=True)
def clear_extension_registries():
    listeners = module._task_lifecycle_listeners[:]
    module._task_lifecycle_listeners.clear()
    yield
    module._task_lifecycle_listeners[:] = listeners


@pytest.mark.asyncio
async def test_lifecycle_listener_receives_safe_success_metadata():
    listener = AsyncMock()
    module.register_task_lifecycle_listener(listener)
    context = SimpleNamespace(
        job=SimpleNamespace(id=17, task_name="app.tasks.reconcile", queue="default", attempts=1)
    )

    result = await module._task_lifecycle_middleware(lambda: _success(), context, None)

    assert result == "ok"
    event = listener.await_args.args[0]
    assert event.job_id == 17
    assert event.task_name == "app.tasks.reconcile"
    assert event.outcome == "succeeded"
    assert event.error_type is None
    assert event.duration_seconds >= 0


@pytest.mark.asyncio
async def test_lifecycle_listener_sees_failure_without_changing_task_error():
    listener = AsyncMock()
    module.register_task_lifecycle_listener(listener)
    context = SimpleNamespace(
        job=SimpleNamespace(id=18, task_name="app.tasks.reconcile", queue="default", attempts=2)
    )

    with pytest.raises(RuntimeError, match="boom"):
        await module._task_lifecycle_middleware(lambda: _failure(), context, None)

    event = listener.await_args.args[0]
    assert event.outcome == "failed"
    assert event.error_type == "RuntimeError"
    assert event.attempts == 2


@pytest.mark.asyncio
async def test_listener_failure_does_not_fail_the_task():
    listener = AsyncMock(side_effect=RuntimeError("observer unavailable"))
    module.register_task_lifecycle_listener(listener)
    context = SimpleNamespace(
        job=SimpleNamespace(id=19, task_name="app.tasks.reconcile", queue="default", attempts=1)
    )

    assert await module._task_lifecycle_middleware(lambda: _success(), context, None) == "ok"


async def _success():
    return "ok"


async def _failure():
    raise RuntimeError("boom")
