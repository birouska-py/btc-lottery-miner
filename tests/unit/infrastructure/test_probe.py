"""Testes dos adaptadores de rede (probe TCP e resolução IPv4)."""

from __future__ import annotations

import asyncio

import pytest

from app.domain.connectivity import PoolEndpoint
from app.domain.errors import PoolError
from app.infrastructure.probe import SocketHostResolver, SocketProber


async def test_probe_reachable_against_local_server() -> None:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()

    server = await asyncio.start_server(handler, host="127.0.0.1", port=0)
    assert server.sockets is not None
    port = server.sockets[0].getsockname()[1]
    try:
        probe = await SocketProber(timeout=2.0).probe(PoolEndpoint(host="127.0.0.1", port=port))
    finally:
        server.close()
        await server.wait_closed()

    assert probe.reachable is True
    assert probe.address == "127.0.0.1"
    assert probe.latency_ms is not None
    assert probe.error is None


async def test_probe_unreachable_port() -> None:
    probe = await SocketProber(timeout=1.0).probe(PoolEndpoint(host="127.0.0.1", port=1))
    assert probe.reachable is False
    assert probe.error is not None


async def test_probe_dns_failure() -> None:
    probe = await SocketProber(timeout=1.0).probe(
        PoolEndpoint(host="host-that-does-not-exist.invalid", port=3333)
    )
    assert probe.reachable is False
    assert probe.error is not None
    assert "DNS" in probe.error


async def test_probe_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_open_connection(*args: object, **kwargs: object) -> None:
        raise TimeoutError

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)
    probe = await SocketProber(timeout=0.1).probe(PoolEndpoint(host="127.0.0.1", port=3333))
    assert probe.reachable is False
    assert probe.error == "tempo esgotado"


async def test_resolver_returns_ipv4() -> None:
    assert await SocketHostResolver().resolve_ipv4("127.0.0.1") == "127.0.0.1"


async def test_resolver_error_on_unknown_host() -> None:
    with pytest.raises(PoolError):
        await SocketHostResolver().resolve_ipv4("host-that-does-not-exist.invalid")


async def test_resolver_error_on_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    loop = asyncio.get_running_loop()

    async def fake_getaddrinfo(*args: object, **kwargs: object) -> list[object]:
        return []

    monkeypatch.setattr(loop, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(PoolError):
        await SocketHostResolver().resolve_ipv4("example.com")
