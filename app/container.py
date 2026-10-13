"""Composition root — monta os adaptadores e serviços da aplicação."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.mining_service import MiningService
from app.application.models import AppSettings
from app.application.pool_service import PoolService
from app.application.settings_service import DEFAULT_WORKER, SettingsService
from app.application.wallet_service import WalletService
from app.config import Settings
from app.infrastructure.crypto import Argon2KeyDeriver, PassphraseCipher
from app.infrastructure.database import Database
from app.infrastructure.miner_process import CpuminerProcess
from app.infrastructure.pool_client import CkPoolClient
from app.infrastructure.repositories import (
    SqliteHistoryRepository,
    SqliteSecretRepository,
    SqliteSettingsRepository,
    SqliteStatsCacheRepository,
    SqliteWalletRepository,
)
from app.infrastructure.wallet_deriver import Bip84Deriver

ALGORITHM = "sha256d"


@dataclass(frozen=True, slots=True)
class Container:
    """Conjunto de dependências construídas para a aplicação."""

    settings: Settings
    database: Database
    wallets: WalletService
    preferences: SettingsService
    mining: MiningService
    pool: PoolService
    process: CpuminerProcess
    pool_client: CkPoolClient


def build_container(settings: Settings) -> Container:
    """Cria o grafo de dependências."""
    database = Database(settings.db_path)
    derivar = Bip84Deriver()
    cipher = PassphraseCipher(Argon2KeyDeriver())

    wallets = WalletService(
        deriver=derivar,
        wallets=SqliteWalletRepository(database),
        secrets=SqliteSecretRepository(database),
        cipher=cipher,
    )
    preferences = SettingsService(
        repository=SqliteSettingsRepository(database),
        defaults=AppSettings(
            threads=settings.default_threads,
            worker=DEFAULT_WORKER,
            pool_url=settings.default_pool_url,
            algorithm=ALGORITHM,
        ),
        max_threads=settings.max_threads,
    )
    process = CpuminerProcess(
        binary=settings.cpuminer_bin,
        buffer_size=settings.log_buffer_size,
    )
    mining = MiningService(
        process=process,
        wallets=wallets,
        settings=preferences,
        history=SqliteHistoryRepository(database),
    )
    pool_client = CkPoolClient(
        base_url=settings.ckpool_base_url,
        timeout=settings.request_timeout_seconds,
    )
    pool = PoolService(
        client=pool_client,
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
        process=process,
        pool_client=pool_client,
    )
