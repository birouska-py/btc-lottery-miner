"""Portas (interfaces) que a infraestrutura implementa.

Mantém a camada de aplicação independente de FastAPI, SQLite, HTTP e subprocessos,
o que torna tudo testável com *fakes* em memória.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from typing import Protocol, runtime_checkable

from app.application.models import AppSettings
from app.domain.connectivity import ConnectionProbe, PoolEndpoint
from app.domain.history import HistoryEvent
from app.domain.mining import LogEntry, MinerStatus, MiningConfig
from app.domain.stats import PoolStats
from app.domain.wallet import DerivationPath, Fingerprint, Mnemonic, Wallet, WalletAddress

Clock = Callable[[], float]


@runtime_checkable
class EndpointProber(Protocol):
    """Testa a conectividade TCP contra um endpoint de pool."""

    async def probe(self, endpoint: PoolEndpoint) -> ConnectionProbe: ...


@runtime_checkable
class HostResolver(Protocol):
    """Resolve um host para um endereço IPv4 (usado ao forçar IPv4)."""

    async def resolve_ipv4(self, host: str) -> str: ...


@runtime_checkable
class MnemonicDeriver(Protocol):
    """Geração/derivação de carteiras (BIP-39/BIP-84)."""

    def generate(self, words: int = 12) -> Mnemonic: ...

    def validate(self, mnemonic: Mnemonic) -> None:
        """Valida o checksum; levanta :class:`InvalidMnemonicError` se inválido."""
        ...

    def derive_address(
        self,
        mnemonic: Mnemonic,
        path: DerivationPath,
        passphrase: str = "",
    ) -> WalletAddress: ...

    def fingerprint(self, mnemonic: Mnemonic) -> Fingerprint: ...


@runtime_checkable
class SecretCipher(Protocol):
    """Cifra autenticada (AES-GCM) para dados em repouso."""

    def encrypt(self, secret: str, plaintext: str) -> str: ...

    def decrypt(self, secret: str, token: str) -> str: ...


@runtime_checkable
class WalletRepository(Protocol):
    """Persistência da carteira (dados públicos)."""

    async def get(self) -> Wallet | None: ...

    async def save(self, wallet: Wallet) -> None: ...

    async def clear(self) -> None: ...


@runtime_checkable
class SecretRepository(Protocol):
    """Persistência de segredos cifrados (seed armazenada opcionalmente)."""

    async def get(self, name: str) -> str | None: ...

    async def set(self, name: str, value: str) -> None: ...

    async def delete(self, name: str) -> None: ...


@runtime_checkable
class SettingsRepository(Protocol):
    """Preferências do usuário."""

    async def get(self) -> AppSettings | None: ...

    async def save(self, settings: AppSettings) -> None: ...


@runtime_checkable
class HistoryRepository(Protocol):
    """Histórico de execução."""

    async def add(self, event: HistoryEvent) -> None: ...

    async def list(self, limit: int = 50) -> Sequence[HistoryEvent]: ...


@runtime_checkable
class StatsCacheRepository(Protocol):
    """Cache das estatísticas da pool."""

    async def get(self) -> PoolStats | None: ...

    async def set(self, stats: PoolStats) -> None: ...


@runtime_checkable
class MinerProcess(Protocol):
    """Controle do processo externo do cpuminer."""

    async def start(self, config: MiningConfig) -> MinerStatus: ...

    async def stop(self) -> MinerStatus: ...

    def status(self) -> MinerStatus: ...

    def buffer(self) -> Sequence[LogEntry]: ...

    def subscribe(self) -> AsyncIterator[LogEntry]: ...


@runtime_checkable
class PoolStatsClient(Protocol):
    """Cliente das estatísticas públicas da pool."""

    async def fetch(self, address: str) -> PoolStats: ...
