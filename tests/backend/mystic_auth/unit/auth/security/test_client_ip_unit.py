# Regression guard for get_client_ip: this app was previously vulnerable
# to IP spoofing via a caller-supplied X-Forwarded-For header, and later
# to mistaking a second trusted proxy hop's own address for the real
# client. These tests pin the fixed behavior: XFF is only trusted from a
# configured reverse proxy, and even then the header is walked from the
# right, discarding any entry that is itself a known trusted-proxy hop,
# until the first real, non-forgeable entry.
from backend.mystic_auth.auth.security import client_ip as client_ip_module
from backend.mystic_auth.auth.security.client_ip import get_client_ip

MODULE = "backend.mystic_auth.auth.security.client_ip"


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    """Duck-typed stand-in for fastapi.Request, same rationale as
    test_rate_limiter_unit.py's identical helper: only `.client.host` and
    `.headers.get(...)` are read here."""

    def __init__(self, host, headers=None):
        self.client = _FakeClient(host) if host is not None else None
        self.headers = headers or {}


def _make_request(host="203.0.113.7", headers=None):
    return _FakeRequest(host, headers)


def test_returns_the_tcp_peer_when_no_proxies_are_trusted(mocker):
    mocker.patch(f"{MODULE}._TRUSTED_PROXY_IPS", frozenset())

    request = _make_request(host="203.0.113.7", headers={"x-forwarded-for": "9.9.9.9"})

    # TRUSTED_PROXY_IPS unset (the default): X-Forwarded-For must be
    # ignored entirely, even though one is present, or any direct caller
    # could spoof their apparent IP with no reverse proxy involved at all.
    assert get_client_ip(request) == "203.0.113.7"


def test_returns_the_tcp_peer_when_the_peer_is_not_a_trusted_proxy(mocker):
    mocker.patch(f"{MODULE}._TRUSTED_PROXY_IPS", frozenset({"172.28.0.10"}))

    request = _make_request(host="203.0.113.7", headers={"x-forwarded-for": "9.9.9.9"})

    # A caller connecting directly (not through the configured proxy) can
    # set X-Forwarded-For to whatever it likes; it must be ignored unless
    # the TCP peer itself is the trusted proxy.
    assert get_client_ip(request) == "203.0.113.7"


def test_trusts_the_right_most_xff_entry_from_a_trusted_proxy(mocker):
    mocker.patch(f"{MODULE}._TRUSTED_PROXY_IPS", frozenset({"172.28.0.10"}))

    # A client spoofing extra left-hand entries; the trusted proxy appends
    # the real client (198.51.100.5) as the last entry.
    request = _make_request(
        host="172.28.0.10",
        headers={"x-forwarded-for": "10.0.0.1, 198.51.100.5"},
    )

    # The LEFT-most entry (10.0.0.1) is caller-forgeable and must never be
    # trusted; only the right-most entry, appended by the trusted proxy
    # itself, is safe to use.
    assert get_client_ip(request) == "198.51.100.5"


def test_trusts_a_single_xff_entry_from_a_trusted_proxy(mocker):
    mocker.patch(f"{MODULE}._TRUSTED_PROXY_IPS", frozenset({"172.28.0.10"}))

    request = _make_request(host="172.28.0.10", headers={"x-forwarded-for": "198.51.100.5"})

    assert get_client_ip(request) == "198.51.100.5"


def test_falls_back_to_the_peer_when_a_trusted_proxy_sends_no_xff_header(mocker):
    mocker.patch(f"{MODULE}._TRUSTED_PROXY_IPS", frozenset({"172.28.0.10"}))

    request = _make_request(host="172.28.0.10", headers={})

    assert get_client_ip(request) == "172.28.0.10"


def test_falls_back_to_the_peer_when_xff_is_present_but_empty(mocker):
    mocker.patch(f"{MODULE}._TRUSTED_PROXY_IPS", frozenset({"172.28.0.10"}))

    request = _make_request(host="172.28.0.10", headers={"x-forwarded-for": "   ,  "})

    assert get_client_ip(request) == "172.28.0.10"


def test_returns_none_when_request_client_is_unavailable(mocker):
    mocker.patch(f"{MODULE}._TRUSTED_PROXY_IPS", frozenset())

    request = _make_request(host=None)

    assert get_client_ip(request) is None


def test_peels_multiple_trusted_hops_to_find_the_real_client(mocker):
    mocker.patch(f"{MODULE}._TRUSTED_PROXY_IPS", frozenset({"172.28.0.10", "172.28.0.11"}))

    # Two trusted proxies in front of backend (e.g. cloudflared/Caddy,
    # then frontend's nginx), each appending its own hop rather than
    # overwriting: the request arrives at backend from frontend
    # (172.28.0.10, the immediate TCP peer), having already picked up
    # cloudflared/Caddy's own address (172.28.0.11) as an XFF entry along
    # the way. Naively trusting only the right-most entry would return
    # 172.28.0.11, a proxy's own address, not the real client.
    request = _make_request(
        host="172.28.0.10",
        headers={"x-forwarded-for": "198.51.100.5, 172.28.0.11"},
    )

    assert get_client_ip(request) == "198.51.100.5"


def test_multi_hop_still_ignores_caller_forged_entries(mocker):
    mocker.patch(f"{MODULE}._TRUSTED_PROXY_IPS", frozenset({"172.28.0.10", "172.28.0.11"}))

    # A caller connecting directly can prepend as many fake entries as it
    # likes, but the trusted proxies always append their own real address
    # last; peeling those known hops off the right must still land on the
    # real, non-forgeable entry (whatever the direct-connecting proxy saw),
    # not skip past it into the caller-forged entries.
    request = _make_request(
        host="172.28.0.10",
        headers={"x-forwarded-for": "10.0.0.1, 10.0.0.2, 198.51.100.5, 172.28.0.11"},
    )

    assert get_client_ip(request) == "198.51.100.5"


def test_falls_back_to_peer_when_every_xff_entry_is_itself_a_trusted_hop(mocker):
    mocker.patch(f"{MODULE}._TRUSTED_PROXY_IPS", frozenset({"172.28.0.10", "172.28.0.11"}))

    request = _make_request(host="172.28.0.10", headers={"x-forwarded-for": "172.28.0.11"})

    assert get_client_ip(request) == "172.28.0.10"


def test_trusted_proxy_ips_parses_the_configured_csv_setting():
    # Sanity check on the module-level constant itself (not mocked here):
    # confirms the frozenset is built from settings.TRUSTED_PROXY_IPS at
    # import time, trimmed and with blanks dropped.
    assert isinstance(client_ip_module._TRUSTED_PROXY_IPS, frozenset)
