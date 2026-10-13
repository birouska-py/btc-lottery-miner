"""Camada de infraestrutura — adaptadores concretos das portas de aplicação."""

from __future__ import annotations

from app.infrastructure.crypto import Argon2KeyDeriver, KeyDeriver, PassphraseCipher
from app.infrastructure.database import Database
from app.infrastructure.miner_process import CpuminerProcess
from app.infrastructure.pool_client import CkPoolClient
from app.infrastructure.probe import SocketHostResolver, SocketProber
from app.infrastructure.repositories import (
    SqliteHistoryRepository,
    SqliteSecretRepository,
    SqliteSettingsRepository,
    SqliteStatsCacheRepository,
    SqliteWalletRepository,
)
from app.infrastructure.wallet_deriver import Bip84Deriver

__all__ = [
    "Argon2KeyDeriver",
    "Bip84Deriver",
    "CkPoolClient",
    "CpuminerProcess",
    "Database",
    "KeyDeriver",
    "PassphraseCipher",
    "SocketHostResolver",
    "SocketProber",
    "SqliteHistoryRepository",
    "SqliteSecretRepository",
    "SqliteSettingsRepository",
    "SqliteStatsCacheRepository",
    "SqliteWalletRepository",
]
