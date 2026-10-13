"""Camada de domínio — regras de negócio puras, sem dependências de infraestrutura."""

from __future__ import annotations

from app.domain.connectivity import ConnectionProbe, PoolEndpoint
from app.domain.errors import (
    CryptoError,
    DecryptionError,
    DomainError,
    InvalidAddressError,
    InvalidFingerprintError,
    InvalidMnemonicError,
    MinerAlreadyRunningError,
    MinerError,
    MinerNotRunningError,
    PoolError,
    PoolNotFoundError,
    ValidationError,
    WalletAlreadyConfiguredError,
    WalletNotConfiguredError,
)
from app.domain.history import HistoryEvent
from app.domain.mining import (
    HashRate,
    LogEntry,
    MinerState,
    MinerStatus,
    MiningConfig,
    ShareStats,
)
from app.domain.stats import PoolStats
from app.domain.wallet import Fingerprint, Mnemonic, Wallet, WalletAddress

__all__ = [
    "ConnectionProbe",
    "CryptoError",
    "DecryptionError",
    "DomainError",
    "Fingerprint",
    "HashRate",
    "HistoryEvent",
    "InvalidAddressError",
    "InvalidFingerprintError",
    "InvalidMnemonicError",
    "LogEntry",
    "MinerAlreadyRunningError",
    "MinerError",
    "MinerNotRunningError",
    "MinerState",
    "MinerStatus",
    "MiningConfig",
    "Mnemonic",
    "PoolEndpoint",
    "PoolError",
    "PoolNotFoundError",
    "PoolStats",
    "ShareStats",
    "ValidationError",
    "Wallet",
    "WalletAddress",
    "WalletAlreadyConfiguredError",
    "WalletNotConfiguredError",
]
