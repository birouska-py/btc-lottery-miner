"""Fixtures compartilhadas de teste."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from app.application.mining_service import MiningService
from app.application.models import AppSettings
from app.application.pool_service import PoolService
from app.application.settings_service import SettingsService
from app.application.wallet_service import WalletService
from app.config import Settings
from app.container import ALGORITHM, Container
from app.infrastructure.crypto import PassphraseCipher, Pbkdf2KeyDeriver
from app.infrastructure.database import Database
from app.infrastructure.repositories import (
    SqliteHistoryRepository,
    SqliteSecretRepository,
    SqliteSettingsRepository,
    SqliteStatsCacheRepository,
    SqliteWalletRepository,
)
from app.infrastructure.wallet_deriver import Bip84Deriver
from app.main import create_app
from tests.fakes import FakeMinerProcess, FakePoolClient

#: Vetor oficial BIP-84 (sem passphrase).
BIP84_MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon about"
)
BIP84_ADDRESS = "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Configuração apontando para um diretório temporário."""
    return Settings(
        data_dir=tmp_path,
        default_threads=2,
        max_threads=8,
        pool_stats_ttl_seconds=30,
        cpuminer_bin="cpuminer",
    )


@pytest.fixture
async def database(settings: Settings) -> AsyncIterator[Database]:
    """Banco SQLite real em arquivo temporário."""
    db = Database(settings.db_path)
    await db.connect()
    yield db
    await db.close()


@pytest.fixture
def cipher() -> PassphraseCipher:
    """Cifra real com parâmetros rápidos (PBKDF2 de baixa iteração)."""
    return PassphraseCipher(Pbkdf2KeyDeriver(iterations=500))


@pytest.fixture
def fake_process() -> FakeMinerProcess:
    """Processo minerador simulado."""
    return FakeMinerProcess()


@pytest.fixture
def fake_pool_client() -> FakePoolClient:
    """Cliente de pool simulado."""
    return FakePoolClient()


@pytest.fixture
def container(
    settings: Settings,
    database: Database,
    fake_process: FakeMinerProcess,
    fake_pool_client: FakePoolClient,
) -> Container:
    """Container com infraestrutura real (SQLite) e adaptadores externos simulados."""
    wallets = WalletService(
        deriver=Bip84Deriver(),
        wallets=SqliteWalletRepository(database),
        secrets=SqliteSecretRepository(database),
        cipher=PassphraseCipher(Pbkdf2KeyDeriver(iterations=500)),
    )
    preferences = SettingsService(
        repository=SqliteSettingsRepository(database),
        defaults=AppSettings(
            threads=settings.default_threads,
            worker="solo",
            pool_url=settings.default_pool_url,
            algorithm=ALGORITHM,
        ),
        max_threads=settings.max_threads,
    )
    mining = MiningService(
        process=fake_process,
        wallets=wallets,
        settings=preferences,
        history=SqliteHistoryRepository(database),
    )
    pool = PoolService(
        client=fake_pool_client,
        cache=SqliteStatsCacheRepository(database),
        wallets=wallets,
        ttl_seconds=settings.pool_stats_ttl_seconds,
    )
    return Container(
        settings=settings,
        database=database,
        wallets=wallets,
        preferences=preferences,
        mining=mining,
        pool=pool,
        process=fake_process,
        pool_client=fake_pool_client,
    )


@pytest.fixture
def app(container: Container):
    """Aplicação FastAPI montada com o container de teste."""
    return create_app(container=container)


@pytest.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    """Cliente HTTP falando com a app via ASGI (sem rede real)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
