"""Testes do cliente de estatísticas da pool (CKPool)."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.domain.errors import PoolError
from app.infrastructure.pool_client import CkPoolClient, _parse_float, _parse_int, _parse_rate
from tests.conftest import BIP84_ADDRESS

BASE_URL = "https://solo.ckpool.org"
URL = f"{BASE_URL}/users/{BIP84_ADDRESS}"


async def test_fetch_parses_payload() -> None:
    payload = {
        "hashrate1m": "1.5T",
        "hashrate5m": "1.2T",
        "hashrate1hr": None,
        "hashrate1d": "500G",
        "hashrate7d": "100G",
        "workers": 2,
        "shares": 123,
        "lastshare": 1_700_000_000,
        "bestshare": 1.5e11,
        "bestever": 2.0e11,
    }
    with respx.mock(assert_all_called=True) as mock:
        mock.get(URL).mock(return_value=httpx.Response(200, json=payload))
        client = CkPoolClient(BASE_URL)
        stats = await client.fetch(BIP84_ADDRESS)
        await client.aclose()

    assert stats.found is True
    assert stats.workers == 2
    assert stats.shares == 123
    assert stats.last_share == 1_700_000_000
    assert stats.hashrates["hashrate1m"] == 1.5e12
    assert "hashrate1hr" not in stats.hashrates
    assert stats.raw["shares"] == 123


async def test_fetch_not_found() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(URL).mock(return_value=httpx.Response(404))
        client = CkPoolClient(BASE_URL)
        stats = await client.fetch(BIP84_ADDRESS)
        await client.aclose()
    assert stats.found is False
    assert stats.address == BIP84_ADDRESS


async def test_fetch_server_error() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(URL).mock(return_value=httpx.Response(500))
        client = CkPoolClient(BASE_URL)
        with pytest.raises(PoolError):
            await client.fetch(BIP84_ADDRESS)
        await client.aclose()


async def test_fetch_invalid_json() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(URL).mock(return_value=httpx.Response(200, text="<html>oops</html>"))
        client = CkPoolClient(BASE_URL)
        with pytest.raises(PoolError):
            await client.fetch(BIP84_ADDRESS)
        await client.aclose()


async def test_fetch_non_dict_payload() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(URL).mock(return_value=httpx.Response(200, json=[1, 2, 3]))
        client = CkPoolClient(BASE_URL)
        with pytest.raises(PoolError):
            await client.fetch(BIP84_ADDRESS)
        await client.aclose()


async def test_fetch_transport_error() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock.get(URL).mock(side_effect=httpx.ConnectError("boom"))
        client = CkPoolClient(BASE_URL)
        with pytest.raises(PoolError):
            await client.fetch(BIP84_ADDRESS)
        await client.aclose()


async def test_aclose_does_not_close_injected_client() -> None:
    async with httpx.AsyncClient() as injected:
        client = CkPoolClient(BASE_URL, client=injected)
        await client.aclose()
        assert not injected.is_closed


def test_parse_rate_helpers() -> None:
    assert _parse_rate(1500) == 1500.0
    assert _parse_rate("2M") == 2_000_000.0
    assert _parse_rate("0") == 0.0
    assert _parse_rate("n/a") is None
    assert _parse_rate(None) is None
    assert _parse_int("7") == 7
    assert _parse_int("x") is None
    assert _parse_int(None) is None
    assert _parse_float("1.5") == 1.5
    assert _parse_float("x") is None
    assert _parse_float(None) is None
