"""Testes do serviço de estatísticas e conectividade da pool."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.application.pool_service import PoolService
from app.application.wallet_service import WalletService
from app.domain.errors import PoolError, ValidationError, WalletNotConfiguredError
from app.domain.stats import PoolStats
from app.domain.wallet import Mnemonic
from app.infrastructure.crypto import PassphraseCipher, Pbkdf2KeyDeriver
from app.infrastructure.wallet_deriver import Bip84Deriver
from tests.conftest import BIP84_ADDRESS, BIP84_MNEMONIC
from tests.fakes import (
    FakePoolClient,
    FakeProber,
    MemorySecretRepository,
    MemoryStatsCacheRepository,
    MemoryWalletRepository,
)


class MutableClock:
    """Relógio controlável para testar o TTL do cache."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@dataclass
class Wiring:
    """Dependências montadas para os testes."""

    pool: PoolService
    client: FakePoolClient
    prober: FakeProber
    cache: MemoryStatsCacheRepository
    wallets: WalletService
    clock: MutableClock


def make_service(ttl: int = 30, error: Exception | None = None) -> Wiring:
    clock = MutableClock()
    client = FakePoolClient(error=error)
    prober = FakeProber()
    cache = MemoryStatsCacheRepository()
    wallets = WalletService(
        deriver=Bip84Deriver(),
        wallets=MemoryWalletRepository(),
        secrets=MemorySecretRepository(),
        cipher=PassphraseCipher(Pbkdf2KeyDeriver(iterations=200)),
        clock=clock,
    )
    pool = PoolService(
        client,
        cache,
        wallets,
        prober=prober,
        ttl_seconds=ttl,
        clock=clock,
    )
    return Wiring(
        pool=pool,
        client=client,
        prober=prober,
        cache=cache,
        wallets=wallets,
        clock=clock,
    )


async def test_requires_wallet() -> None:
    with pytest.raises(WalletNotConfiguredError):
        await make_service().pool.get()


async def test_fetches_and_caches() -> None:
    wiring = make_service()
    await wiring.wallets.import_address(BIP84_ADDRESS)

    stats = await wiring.pool.get()
    assert stats.address == BIP84_ADDRESS
    assert stats.fetched_at == 1000.0
    assert wiring.client.calls == 1
    assert wiring.cache.stats is not None


async def test_cache_hit_within_ttl() -> None:
    wiring = make_service()
    await wiring.wallets.import_address(BIP84_ADDRESS)

    await wiring.pool.get()
    wiring.clock.now += 10
    await wiring.pool.get()
    assert wiring.client.calls == 1


async def test_refresh_forces_fetch() -> None:
    wiring = make_service()
    await wiring.wallets.import_address(BIP84_ADDRESS)

    await wiring.pool.get()
    await wiring.pool.get(refresh=True)
    assert wiring.client.calls == 2


async def test_ttl_expiry_forces_fetch() -> None:
    wiring = make_service(ttl=30)
    await wiring.wallets.import_address(BIP84_ADDRESS)

    await wiring.pool.get()
    wiring.clock.now += 31
    await wiring.pool.get()
    assert wiring.client.calls == 2


async def test_different_address_invalidates_cache() -> None:
    wiring = make_service()
    await wiring.wallets.import_address(BIP84_ADDRESS)
    wiring.cache.stats = PoolStats(address="bc1qoutro", found=True, fetched_at=1000.0)

    await wiring.pool.get()
    assert wiring.client.calls == 1


async def test_client_error_propagates() -> None:
    wiring = make_service(error=PoolError("indisponível"))
    await wiring.wallets.import_address(BIP84_ADDRESS)
    with pytest.raises(PoolError):
        await wiring.pool.get()


async def test_reuses_mnemonic_derived_wallet() -> None:
    wiring = make_service()
    await wiring.wallets.confirm(Mnemonic(BIP84_MNEMONIC))
    stats = await wiring.pool.get()
    assert stats.address == BIP84_ADDRESS


async def test_probe_parses_endpoint_and_delegates() -> None:
    wiring = make_service()
    probe = await wiring.pool.probe("stratum+tcp://solo.ckpool.org:3333")
    assert probe.reachable is True
    assert probe.address == "203.0.113.10"
    assert probe.latency_ms == 12.5
    assert wiring.prober.calls[0].host == "solo.ckpool.org"
    assert wiring.prober.calls[0].port == 3333


async def test_probe_rejects_invalid_url() -> None:
    wiring = make_service()
    with pytest.raises(ValidationError):
        await wiring.pool.probe("http://nope")
