"""Testes dos value objects de conectividade."""

from __future__ import annotations

import pytest

from app.domain.connectivity import ConnectionProbe, PoolEndpoint
from app.domain.errors import ValidationError


def test_parse_stratum_url() -> None:
    endpoint = PoolEndpoint.parse("stratum+tcp://solo.ckpool.org:3333")
    assert endpoint.host == "solo.ckpool.org"
    assert endpoint.port == 3333
    assert endpoint.scheme == "stratum+tcp"
    assert str(endpoint) == "stratum+tcp://solo.ckpool.org:3333"


def test_parse_ssl_and_strips_spaces() -> None:
    endpoint = PoolEndpoint.parse("  stratum+ssl://pool.example.com:4334 ")
    assert endpoint.scheme == "stratum+ssl"
    assert endpoint.port == 4334


def test_with_host_replaces_only_host() -> None:
    endpoint = PoolEndpoint.parse("stratum+tcp://solo.ckpool.org:3333")
    resolved = endpoint.with_host("203.0.113.10")
    assert str(resolved) == "stratum+tcp://203.0.113.10:3333"
    assert resolved.port == 3333


@pytest.mark.parametrize(
    "url",
    [
        "http://solo.ckpool.org:3333",
        "stratum+tcp://solo.ckpool.org",
        "stratum+tcp://:3333",
        "stratum+tcp://solo.ckpool.org:abc",
        "stratum+tcp://solo.ckpool.org:99999",
    ],
)
def test_parse_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        PoolEndpoint.parse(url)


def test_dataclass_validation() -> None:
    with pytest.raises(ValidationError):
        PoolEndpoint(host="", port=3333)
    with pytest.raises(ValidationError):
        PoolEndpoint(host="h", port=0)
    with pytest.raises(ValidationError):
        PoolEndpoint(host="h", port=3333, scheme="ftp")


def test_connection_probe_defaults() -> None:
    probe = ConnectionProbe(endpoint=PoolEndpoint(host="h", port=1), reachable=False)
    assert probe.address is None
    assert probe.latency_ms is None
    assert probe.error is None
