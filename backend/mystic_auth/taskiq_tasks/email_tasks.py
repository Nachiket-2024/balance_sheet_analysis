import traceback
from asyncio import sleep
from typing import Any

from redis.exceptions import ConnectionError, ResponseError
from taskiq import AsyncBroker, SimpleRetryMiddleware
from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker

from ..core.settings import settings
from ..emails.email_sender import email_sender
from ..logging.logging_config import get_worker_logger

logger = get_worker_logger(__name__)

result_backend: RedisAsyncResultBackend[Any] = RedisAsyncResultBackend(redis_url=settings.REDIS_URL)


class ResilientRedisStreamBroker(RedisStreamBroker):
    """Redis Stream broker that recreates its consumer group if Redis loses it."""

    async def listen(self):
        while True:
            try:
                async for message in super().listen():
                    yield message
            except ResponseError as exc:
                if "NOGROUP" not in str(exc):
                    raise

                logger.warning(
                    "Taskiq Redis stream consumer group is missing; re-declaring group before resuming"
                )
                await self._declare_consumer_group()
            except ConnectionError:
                logger.warning("Taskiq Redis connection was closed; reconnecting before resuming")
                await sleep(1)


# SimpleRetryMiddleware re-enqueues a task immediately (no backoff/delay) up
# to a task's own `max_retries` label when the task raises : it does NOT
# add a scheduler-based delay the way SmartRetryMiddleware's docs suggest,
# since that requires a TaskiqScheduler/schedule_source this project doesn't
# run; an immediate retry is the correct, simple fit for the one task here.
broker: AsyncBroker = ResilientRedisStreamBroker(
    url=settings.REDIS_URL,
).with_result_backend(result_backend).with_middlewares(
    SimpleRetryMiddleware(default_retry_count=3)
)


@broker.task(retry_on_error=True, max_retries=3)
async def send_email_task(to_email: str, subject: str, body: str, is_html: bool = True) -> bool:
    """Sends an email via the configured EmailSender. Returns True on success.

    Raises (rather than swallowing the exception) on failure so
    SimpleRetryMiddleware can see it and re-enqueue : up to 3 attempts total.
    Every attempt, including ones that will be retried, logs its own full
    traceback, so a permanent failure that exhausts all retries still leaves
    a clear trail in the logs, not a silently dropped email.
    """
    logger.info("Sending email to %s", to_email)
    try:
        await email_sender.send(to_email, subject, body, is_html)
        logger.info("Email sent successfully to %s", to_email)
        return True

    except Exception:
        logger.error("Error sending email to %s (will retry if attempts remain):\n%s", to_email, traceback.format_exc())
        raise
