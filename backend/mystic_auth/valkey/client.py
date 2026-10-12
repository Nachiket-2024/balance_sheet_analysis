from valkey.asyncio import Valkey

from ..core.settings import settings

VALKEY_SOCKET_TIMEOUT_SECONDS = 3.0

valkey_client = Valkey.from_url(
    settings.VALKEY_URL,
    decode_responses=True,
    socket_connect_timeout=VALKEY_SOCKET_TIMEOUT_SECONDS,
    socket_timeout=VALKEY_SOCKET_TIMEOUT_SECONDS,
)
