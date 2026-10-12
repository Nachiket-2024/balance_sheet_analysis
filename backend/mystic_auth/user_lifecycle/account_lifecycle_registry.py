"""Downstream account-lifecycle listener registry."""

import inspect
from collections.abc import Awaitable, Callable

from .account_lifecycle_events import AccountLifecycleEvent

AccountLifecycleListener = Callable[[AccountLifecycleEvent], Awaitable[None] | None]
_listeners: list[AccountLifecycleListener] = []


def register_account_lifecycle_listener(listener: AccountLifecycleListener) -> None:
    """Register an idempotent downstream listener."""
    if listener not in _listeners:
        _listeners.append(listener)


async def notify_account_lifecycle_listeners(event: AccountLifecycleEvent) -> None:
    for listener in tuple(_listeners):
        result = listener(event)
        if inspect.isawaitable(result):
            await result
