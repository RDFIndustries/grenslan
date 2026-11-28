"""Connection-level outbound enforcement (AD-398, AD-400, AD-401, PC-022).

Destinations are checked on the address actually connected to, on every
redirect hop, independently of the URL a caller supplies. All traffic stays on
loopback: fixture destinations are reached only through destinations that
explicitly allow a private address.
"""

from __future__ import annotations

import ipaddress
import socket
import ssl
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from outbound_fixtures import FixtureServer, StaticResolver, fixture_server

from grenslan.network.addresses import address_permitted
from grenslan.network.backend import PolicyBackend
from grenslan.network.client import Credential, OutboundClient, OutboundError, outbound_ssl_context
from grenslan.network.policy import DestinationDenied, NetworkPolicy

from tls_fixtures import TlsMaterial, make_tls_material

LOOPBACK = ["127.0.0.1"]


def scope(*destinations: dict[str, Any], public_web: bool = False, allow_outbound_http: bool = False) -> NetworkPolicy:
    return NetworkPolicy.from_scope(
        {"destinations": list(destinations), "public_web": public_web, "allow_outbound_http": allow_outbound_http}
    )


def dest(host: str, port: int, scheme: str = "http", *, private: bool = True) -> dict[str, Any]:
    return {"scheme": scheme, "host": host, "port": port, "allow_private_address": private}


def client(policy: NetworkPolicy, resolver: StaticResolver, **kwargs: Any) -> OutboundClient:
    kwargs.setdefault("ssl_context", outbound_ssl_context())
    return OutboundClient(policy, resolver=resolver, **kwargs)


@pytest.fixture
def server() -> Iterator[FixtureServer]:
    with fixture_server() as running:
        yield running


@pytest.fixture
def tls(tmp_path: Path) -> TlsMaterial:
    return make_tls_material(tmp_path, hostnames=("fixture.test", "other.test"))


# Address classification


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1", "100.64.0.1", "169.254.169.254", "0.0.0.0",  # noqa: S104 - an address under test, not a bind
        "255.255.255.255", "224.0.0.1", "198.18.0.1", "::1", "::", "fe80::1", "fc00::1", "fd00:ec2::254",
        "::ffff:127.0.0.1", "::ffff:169.254.169.254", "64:ff9b::7f00:1", "64:ff9b::a9fe:a9fe", "2002:7f00:1::1",
        "2001:0:4136:e378:8000:63bf:80ff:fffe", "ff02::1",
    ],
)  # fmt: skip
def test_non_public_address_classes_are_denied(address: str) -> None:
    assert not address_permitted(ipaddress.ip_address(address))


@pytest.mark.parametrize("address", ["93.184.215.14", "2606:2800:21f:cb07:6820:80da:af6b:8b2c", "8.8.8.8"])
def test_public_addresses_are_permitted(address: str) -> None:
    assert address_permitted(ipaddress.ip_address(address))


# URL checks before any connection


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        pytest.param("https://elsewhere.test/", "not an approved destination", id="unlisted-host"),
        pytest.param("https://api.example.test:8443/", "not an approved destination", id="wrong-port"),
        pytest.param("http://api.example.test:443/", "plain http", id="plain-http"),
        pytest.param("ftp://api.example.test/", "scheme", id="scheme"),
        pytest.param("file:///etc/passwd", "scheme", id="file"),
        pytest.param("https://user:pw@api.example.test/", "user information", id="userinfo"),
        pytest.param("https:///no-host", "host", id="no-host"),
        pytest.param("https://api.example.test:0/", "port", id="port-zero"),
        pytest.param("https://[::ffff:127.0.0.1]/", "not an approved destination", id="mapped-literal"),
    ],
)
def test_urls_outside_the_scope_are_denied(url: str, reason: str) -> None:
    policy = scope(dest("api.example.test", 443, "https", private=False))
    with pytest.raises(DestinationDenied, match=reason):
        policy.check_url(url)


def test_host_names_are_compared_case_insensitively_without_trailing_dot() -> None:
    policy = scope(dest("api.example.test", 443, "https", private=False))
    assert policy.check_url("https://API.Example.Test./search").host == "api.example.test"


def test_public_web_admits_any_public_host_on_the_standard_https_port() -> None:
    assert scope(public_web=True).check_url("https://anything.test/").port == 443
    assert scope(public_web=True).check_url("https://anything.test:443/").port == 443


@pytest.mark.parametrize(
    "url", ["https://anything.test:8443/", "https://anything.test:80/", "https://anything.test:22/"]
)
def test_public_web_does_not_admit_other_https_ports(url: str) -> None:
    with pytest.raises(DestinationDenied, match="not an approved destination"):
        scope(public_web=True, allow_outbound_http=True).check_url(url)


@pytest.mark.parametrize("allow_outbound_http", [False, True])
def test_public_web_never_admits_plain_http(allow_outbound_http: bool) -> None:
    with pytest.raises(DestinationDenied):
        scope(public_web=True, allow_outbound_http=allow_outbound_http).check_url("http://anything.test/")


def test_plain_http_is_limited_to_listed_local_network_destinations() -> None:
    local = dest("printer.lan", 80)
    assert scope(local, allow_outbound_http=True).check_url("http://printer.lan/").allow_private
    with pytest.raises(DestinationDenied, match="plain http is not permitted"):
        scope(local).check_url("http://printer.lan/")
    with pytest.raises(DestinationDenied, match="local network"):
        scope(dest("api.example.test", 80, private=False), allow_outbound_http=True).check_url(
            "http://api.example.test/"
        )


async def test_plain_http_destinations_may_not_resolve_to_public_addresses() -> None:
    resolver = StaticResolver({"printer.lan": ["93.184.215.14"]})
    backend = PolicyBackend(scope(dest("printer.lan", 80), allow_outbound_http=True), resolver)
    backend._inner = _NeverConnect()  # type: ignore[assignment]
    with pytest.raises(DestinationDenied, match="prohibited address"):
        await backend.connect_tcp("printer.lan", 80)


async def test_connections_to_plain_http_destinations_need_outbound_http() -> None:
    resolver = StaticResolver({"printer.lan": LOOPBACK})
    backend = PolicyBackend(scope(dest("printer.lan", 80)), resolver)
    backend._inner = _NeverConnect()  # type: ignore[assignment]
    with pytest.raises(DestinationDenied, match="not an approved destination"):
        await backend.connect_tcp("printer.lan", 80)
    assert resolver.lookups == []


async def test_an_https_destination_allowing_private_addresses_may_still_be_public() -> None:
    resolver = StaticResolver({"api.example.test": ["93.184.215.14"]})
    backend = PolicyBackend(scope(dest("api.example.test", 443, "https")), resolver)
    backend._inner = _Reached()  # type: ignore[assignment]
    with pytest.raises(_ConnectionAttempted, match=r"93\.184\.215\.14"):  # the address check passed
        await backend.connect_tcp("api.example.test", 443)


def test_a_listed_destination_may_use_another_port_alongside_public_web() -> None:
    policy = scope(dest("api.example.test", 8443, "https", private=False), public_web=True)
    assert policy.check_url("https://api.example.test:8443/").port == 8443


# Connection-level enforcement


async def test_approved_private_destination_is_reached(server: FixtureServer) -> None:
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    async with client(scope(dest("fixture.test", server.port), allow_outbound_http=True), resolver) as outbound:
        response = await outbound.request("GET", f"http://fixture.test:{server.port}/hello", timeout=5)
    assert (response.status, response.body) == (200, b"ok")
    assert server.routes.seen[0].headers["host"] == f"fixture.test:{server.port}"


@pytest.mark.parametrize(
    "answers",
    [
        pytest.param(["127.0.0.1"], id="private"),
        pytest.param(["93.184.215.14", "127.0.0.1"], id="one-private-answer"),
        pytest.param(["::ffff:127.0.0.1"], id="mapped"),
    ],
)
async def test_names_resolving_to_private_addresses_are_denied_without_connecting(
    server: FixtureServer, answers: list[str]
) -> None:
    resolver = StaticResolver({"fixture.test": answers})
    backend = PolicyBackend(scope(dest("fixture.test", server.port, "https", private=False)), resolver)
    with pytest.raises(DestinationDenied, match="prohibited address"):
        await backend.connect_tcp("fixture.test", server.port)
    assert server.routes.seen == []


async def test_public_web_does_not_reach_private_addresses() -> None:
    resolver = StaticResolver({"rebound.test": LOOPBACK})
    backend = PolicyBackend(scope(public_web=True), resolver)
    with pytest.raises(DestinationDenied, match="prohibited address"):
        await backend.connect_tcp("rebound.test", 443)


@pytest.mark.parametrize(("port", "allow_outbound_http"), [(8443, True), (80, False), (80, True)])
async def test_the_backend_admits_public_web_only_on_standard_ports(port: int, allow_outbound_http: bool) -> None:
    resolver = StaticResolver({"anything.test": ["93.184.215.14"]})
    backend = PolicyBackend(scope(public_web=True, allow_outbound_http=allow_outbound_http), resolver)
    backend._inner = _NeverConnect()  # type: ignore[assignment]
    with pytest.raises(DestinationDenied, match="not an approved destination"):
        await backend.connect_tcp("anything.test", port)
    assert resolver.lookups == []


class _NeverConnect:
    async def connect_tcp(self, *args: Any) -> None:
        raise AssertionError("a connection was attempted")


class _ConnectionAttempted(Exception):
    pass


class _Reached:
    async def connect_tcp(self, address: str, *args: Any) -> None:
        raise _ConnectionAttempted(address)


async def test_metadata_addresses_are_denied_even_for_private_destinations() -> None:
    resolver = StaticResolver({"metadata.test": ["169.254.169.254"]})
    async with client(scope(dest("metadata.test", 80), allow_outbound_http=True), resolver) as outbound:
        with pytest.raises(DestinationDenied, match="prohibited address"):
            await outbound.request("GET", "http://metadata.test/latest/", timeout=5)


async def test_a_name_without_addresses_is_a_resolution_failure() -> None:
    async with client(scope(dest("missing.test", 80), allow_outbound_http=True), StaticResolver({})) as outbound:
        with pytest.raises(OutboundError) as caught:
            await outbound.request("GET", "http://missing.test/", timeout=5)
    assert caught.value.kind == "unresolved"
    assert not isinstance(caught.value, DestinationDenied)


async def test_each_connection_resolves_once_and_uses_the_checked_answer(server: FixtureServer) -> None:
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    async with client(scope(dest("fixture.test", server.port), allow_outbound_http=True), resolver) as outbound:
        await outbound.request("GET", f"http://fixture.test:{server.port}/", timeout=5)
    assert resolver.lookups == ["fixture.test"]


async def test_proxy_environment_variables_are_ignored(server: FixtureServer, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    async with client(scope(dest("fixture.test", server.port), allow_outbound_http=True), resolver) as outbound:
        assert (await outbound.request("GET", f"http://fixture.test:{server.port}/", timeout=5)).status == 200


# Redirects


def redirect(server: FixtureServer, path: str, location: str, status: int = 302) -> None:
    server.routes.responses[path] = (status, [("Location", location)], b"")


async def test_redirects_to_approved_destinations_are_followed_and_recorded(server: FixtureServer) -> None:
    redirect(server, "/start", "/end")
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    async with client(scope(dest("fixture.test", server.port), allow_outbound_http=True), resolver) as outbound:
        response = await outbound.request("GET", f"http://fixture.test:{server.port}/start", timeout=5)
    assert response.url == f"http://fixture.test:{server.port}/end"
    assert response.redirects == (f"http://fixture.test:{server.port}/start",)


@pytest.mark.parametrize(
    "location",
    [
        pytest.param("http://elsewhere.test/", id="unlisted-host"),
        pytest.param("file:///etc/passwd", id="file-scheme"),
        pytest.param("http://127.0.0.1:{port}/", id="ip-literal-of-approved-name"),
    ],
)
async def test_redirects_outside_the_scope_are_denied(server: FixtureServer, location: str) -> None:
    redirect(server, "/start", location.format(port=server.port))
    resolver = StaticResolver({"fixture.test": LOOPBACK, "elsewhere.test": LOOPBACK})
    async with client(scope(dest("fixture.test", server.port), allow_outbound_http=True), resolver) as outbound:
        with pytest.raises(DestinationDenied):
            await outbound.request("GET", f"http://fixture.test:{server.port}/start", timeout=5)
    assert [seen.path for seen in server.routes.seen] == ["/start"]


async def test_redirect_limit_is_enforced(server: FixtureServer) -> None:
    redirect(server, "/loop", "/loop")
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    policy = scope(dest("fixture.test", server.port), allow_outbound_http=True)
    async with client(policy, resolver, max_redirects=3) as outbound:
        with pytest.raises(OutboundError) as caught:
            await outbound.request("GET", f"http://fixture.test:{server.port}/loop", timeout=5)
    assert caught.value.kind == "redirect_limit"
    assert len(server.routes.seen) == 4


async def test_a_redirect_without_location_is_returned_as_is(server: FixtureServer) -> None:
    server.routes.responses["/bare"] = (302, [], b"")
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    async with client(scope(dest("fixture.test", server.port), allow_outbound_http=True), resolver) as outbound:
        assert (await outbound.request("GET", f"http://fixture.test:{server.port}/bare", timeout=5)).status == 302


@pytest.mark.parametrize(("status", "method", "body"), [(303, "GET", b""), (302, "GET", b""), (307, "POST", b"q=1")])
async def test_redirect_method_and_body_follow_http_semantics(
    server: FixtureServer, status: int, method: str, body: bytes
) -> None:
    redirect(server, "/form", "/next", status)
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    async with client(scope(dest("fixture.test", server.port), allow_outbound_http=True), resolver) as outbound:
        await outbound.request(
            "POST", f"http://fixture.test:{server.port}/form", body=b"q=1",
            headers=[("Content-Type", "application/x-www-form-urlencoded")], timeout=5,
        )  # fmt: skip
    following = server.routes.seen[1]
    assert (following.method, following.body) == (method, body)


# Credentials


async def test_credentials_are_sent_only_to_their_origin_and_never_after_leaving_it() -> None:
    with fixture_server() as first, fixture_server() as second:
        origin = f"http://fixture.test:{first.port}"
        redirect(first, "/start", f"http://other.test:{second.port}/away")
        redirect(second, "/away", f"{origin}/back")
        resolver = StaticResolver({"fixture.test": LOOPBACK, "other.test": LOOPBACK})
        policy = scope(dest("fixture.test", first.port), dest("other.test", second.port), allow_outbound_http=True)
        credential = Credential(origin, (("Authorization", "Bearer fixture-token-not-a-secret"),))
        async with client(policy, resolver) as outbound:
            await outbound.request("GET", f"{origin}/start", credential=credential, timeout=5)
        start, back = first.routes.seen
        assert start.headers["authorization"] == "Bearer fixture-token-not-a-secret"
        assert "authorization" not in second.routes.seen[0].headers
        assert "authorization" not in back.headers


async def test_credentials_for_another_origin_are_not_sent(server: FixtureServer) -> None:
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    credential = Credential("https://fixture.test", (("Authorization", "Bearer fixture-token-not-a-secret"),))
    async with client(scope(dest("fixture.test", server.port), allow_outbound_http=True), resolver) as outbound:
        await outbound.request("GET", f"http://fixture.test:{server.port}/", credential=credential, timeout=5)
    assert "authorization" not in server.routes.seen[0].headers


def test_credential_origin_must_be_an_origin() -> None:
    with pytest.raises(ValueError, match="origin"):
        Credential("https://fixture.test/path", (("Authorization", "x"),))


# TLS


async def test_https_is_verified_against_the_configured_trust(tls: TlsMaterial) -> None:
    with fixture_server(tls) as running:
        resolver = StaticResolver({"fixture.test": LOOPBACK})
        policy = scope(dest("fixture.test", running.port, "https"))
        async with client(policy, resolver, ssl_context=tls.client_context()) as outbound:
            response = await outbound.request("GET", f"https://fixture.test:{running.port}/", timeout=5)
    assert response.status == 200


@pytest.mark.parametrize("host", ["fixture.test", "unnamed.test"])
async def test_untrusted_or_mismatched_certificates_fail_as_tls_errors(tls: TlsMaterial, host: str) -> None:
    with fixture_server(tls) as running:
        resolver = StaticResolver({host: LOOPBACK})
        trust = outbound_ssl_context() if host == "fixture.test" else tls.client_context()
        async with client(scope(dest(host, running.port, "https")), resolver, ssl_context=trust) as outbound:
            with pytest.raises(OutboundError) as caught:
                await outbound.request("GET", f"https://{host}:{running.port}/", timeout=5)
    assert caught.value.kind == "tls"
    assert running.routes.seen == []


def test_a_context_without_verification_is_refused() -> None:
    context = outbound_ssl_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with pytest.raises(ValueError, match="verif"):
        OutboundClient(scope(public_web=True), ssl_context=context)


def test_a_context_accepting_tls_below_1_2_is_refused() -> None:
    context = outbound_ssl_context()
    context.minimum_version = ssl.TLSVersion.MINIMUM_SUPPORTED
    with pytest.raises(ValueError, match=r"1\.2"):
        OutboundClient(scope(public_web=True), ssl_context=context)


# Bounds


async def test_responses_larger_than_the_limit_are_refused(server: FixtureServer) -> None:
    server.routes.responses["/big"] = (200, [], b"x" * 2048)
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    policy = scope(dest("fixture.test", server.port), allow_outbound_http=True)
    async with client(policy, resolver, max_response_bytes=1024) as outbound:
        with pytest.raises(OutboundError) as caught:
            await outbound.request("GET", f"http://fixture.test:{server.port}/big", timeout=5)
    assert caught.value.kind == "too_large"


@pytest.fixture
def silent_port() -> Iterator[int]:
    """A listener that accepts connections and never answers."""
    listener = socket.create_server(("127.0.0.1", 0))
    held: list[socket.socket] = []
    stop = threading.Event()

    def accept() -> None:
        listener.settimeout(0.1)
        while not stop.is_set():
            try:
                held.append(listener.accept()[0])
            except TimeoutError:
                continue

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    yield listener.getsockname()[1]
    stop.set()
    thread.join()
    for connection in held:
        connection.close()
    listener.close()


async def test_requests_are_bounded_by_their_timeout(silent_port: int) -> None:
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    async with client(scope(dest("fixture.test", silent_port), allow_outbound_http=True), resolver) as outbound:
        with pytest.raises(OutboundError) as caught:
            await outbound.request("GET", f"http://fixture.test:{silent_port}/", timeout=0.3)
    assert caught.value.kind == "timeout"


async def test_connection_refused_is_a_connect_failure() -> None:
    with socket.create_server(("127.0.0.1", 0)) as probe:
        port = probe.getsockname()[1]
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    async with client(scope(dest("fixture.test", port), allow_outbound_http=True), resolver) as outbound:
        with pytest.raises(OutboundError) as caught:
            await outbound.request("GET", f"http://fixture.test:{port}/", timeout=5)
    assert caught.value.kind == "connect"


async def test_redirect_from_https_to_plain_http_is_denied_without_outbound_http(tls: TlsMaterial) -> None:
    with fixture_server(tls) as secure, fixture_server() as plain:
        redirect(secure, "/start", f"http://fixture.test:{plain.port}/downgraded")
        resolver = StaticResolver({"fixture.test": LOOPBACK})
        policy = scope(dest("fixture.test", secure.port, "https"), dest("fixture.test", plain.port, "http"))
        async with client(policy, resolver, ssl_context=tls.client_context()) as outbound:
            with pytest.raises(DestinationDenied, match="plain http"):
                await outbound.request("GET", f"https://fixture.test:{secure.port}/start", timeout=5)
        assert plain.routes.seen == []


@pytest.mark.parametrize("name", ["Authorization", "cookie", "Proxy-Authorization"])
async def test_credential_headers_cannot_be_passed_as_ordinary_headers(name: str) -> None:
    async with OutboundClient(scope(public_web=True), resolver=StaticResolver({})) as outbound:
        with pytest.raises(ValueError, match="Credential"):
            await outbound.request("GET", "https://example.test/", headers=[(name, "x")], timeout=1)


# The connection layer, independently of the URL checks


async def test_the_backend_refuses_unlisted_targets_before_resolving() -> None:
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    backend = PolicyBackend(scope(dest("fixture.test", 80)), resolver)
    with pytest.raises(DestinationDenied, match="not an approved destination"):
        await backend.connect_tcp("other.test", 80)
    with pytest.raises(DestinationDenied, match="not an approved destination"):
        await backend.connect_tcp("fixture.test", 81)
    assert resolver.lookups == []


async def test_the_backend_refuses_unix_sockets() -> None:
    with pytest.raises(DestinationDenied):
        await PolicyBackend(scope(public_web=True), StaticResolver({})).connect_unix_socket("/run/anything.sock")


class _Stream:
    def __init__(self, peer: tuple[str, int]) -> None:
        self.peer = peer
        self.closed = False

    def get_extra_info(self, name: str) -> Any:
        return self if name == "socket" else None

    def getpeername(self) -> tuple[str, int]:
        return self.peer

    async def aclose(self) -> None:
        self.closed = True


class _Inner:
    def __init__(self, stream: _Stream) -> None:
        self.stream = stream

    async def connect_tcp(self, host: str, port: int, *args: Any) -> _Stream:
        return self.stream


@pytest.mark.parametrize("peer", [("127.0.0.2", 8080), ("127.0.0.1", 9090)])
async def test_a_connection_whose_peer_differs_from_the_checked_address_is_closed(peer: tuple[str, int]) -> None:
    stream = _Stream(peer)
    policy = scope(dest("fixture.test", 8080), allow_outbound_http=True)
    backend = PolicyBackend(policy, StaticResolver({"fixture.test": LOOPBACK}))
    backend._inner = _Inner(stream)  # type: ignore[assignment]
    with pytest.raises(DestinationDenied, match="peer"):
        await backend.connect_tcp("fixture.test", 8080)
    assert stream.closed
