"""Testes dos repositórios SQLite."""

from __future__ import annotations

from app.application.models import AppSettings
from app.domain.history import HistoryEvent
from app.domain.stats import PoolStats
from app.domain.wallet import Fingerprint, Wallet, WalletAddress
from app.infrastructure.database import Database
from app.infrastructure.repositories import (
    SqliteHistoryRepository,
    SqliteSecretRepository,
    SqliteSettingsRepository,
    SqliteStatsCacheRepository,
    SqliteWalletRepository,
)
from tests.conftest import BIP84_ADDRESS


async def test_wallet_repository_roundtrip(database: Database) -> None:
    repository = SqliteWalletRepository(database)
    assert await repository.get() is None

    wallet = Wallet(
        address=WalletAddress(BIP84_ADDRESS),
        created_at=10.0,
        fingerprint=Fingerprint("a" * 64),
        seed_stored=True,
    )
    await repository.save(wallet)
    stored = await repository.get()
    assert stored is not None
    assert str(stored.address) == BIP84_ADDRESS
    assert stored.fingerprint == Fingerprint("a" * 64)
    assert stored.seed_stored is True

    await repository.save(Wallet(address=WalletAddress(BIP84_ADDRESS), created_at=20.0))
    updated = await repository.get()
    assert updated is not None and updated.fingerprint is None and updated.seed_stored is False

    await repository.clear()
    assert await repository.get() is None


async def test_secret_repository_roundtrip(database: Database) -> None:
    repository = SqliteSecretRepository(database)
    assert await repository.get("seed") is None
    await repository.set("seed", "token-1")
    assert await repository.get("seed") == "token-1"
    await repository.set("seed", "token-2")
    assert await repository.get("seed") == "token-2"
    await repository.delete("seed")
    assert await repository.get("seed") is None


async def test_settings_repository_roundtrip(database: Database) -> None:
    repository = SqliteSettingsRepository(database)
    assert await repository.get() is None
    settings = AppSettings(
        threads=4,
        worker="w",
        pool_url="stratum+tcp://x:1",
        algorithm="sha256d",
        force_ipv4=True,
    )
    await repository.save(settings)
    stored = await repository.get()
    assert stored == settings
    assert stored is not None and stored.force_ipv4 is True


async def test_history_repository_orders_and_parses(database: Database) -> None:
    repository = SqliteHistoryRepository(database)
    await repository.add(HistoryEvent(kind="start", created_at=1.0, detail={"threads": 2}))
    await repository.add(HistoryEvent(kind="stop", created_at=2.0))
    events = await repository.list(limit=10)
    assert [event.kind for event in events] == ["stop", "start"]
    assert events[0].id is not None
    assert events[0].detail == {}
    assert events[1].detail == {"threads": 2}


async def test_stats_cache_repository_roundtrip(database: Database) -> None:
    repository = SqliteStatsCacheRepository(database)
    assert await repository.get() is None
    stats = PoolStats(
        address=BIP84_ADDRESS,
        found=True,
        workers=2,
        shares=99,
        best_share=1.5e11,
        hashrates={"hashrate1m": 1_000_000.0},
        raw={"shares": 99},
        fetched_at=50.0,
    )
    await repository.set(stats)
    cached = await repository.get()
    assert cached is not None
    assert cached.shares == 99
    assert cached.hashrates == {"hashrate1m": 1_000_000.0}
    assert cached.fetched_at == 50.0
