"""Fakes em memória usados nos testes de aplicação e de API."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from app.application.models import AppSettings
from app.domain.connectivity import ConnectionProbe, PoolEndpoint
from app.domain.errors import MinerAlreadyRunningError, MinerError, MinerNotRunningError
from app.domain.history import HistoryEvent
from app.domain.mining import LogEntry, MinerState, MinerStatus, MiningConfig
from app.domain.stats import PoolStats
from app.domain.wallet import Wallet


class MemoryWalletRepository:
    """Repositório de carteira em memória."""

    def __init__(self) -> None:
        self.wallet: Wallet | None = None

    async def get(self) -> Wallet | None:
        return self.wallet

    async def save(self, wallet: Wallet) -> None:
        self.wallet = wallet

    async def clear(self) -> None:
        self.wallet = None


class MemorySecretRepository:
    """Repositório de segredos em memória."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, name: str) -> str | None:
        return self.values.get(name)

    async def set(self, name: str, value: str) -> None:
        self.values[name] = value

    async def delete(self, name: str) -> None:
        self.values.pop(name, None)


class MemorySettingsRepository:
    """Preferências em memória."""

    def __init__(self) -> None:
        self.settings: AppSettings | None = None

    async def get(self) -> AppSettings | None:
        return self.settings

    async def save(self, settings: AppSettings) -> None:
        self.settings = settings


class MemoryHistoryRepository:
    """Histórico em memória."""

    def __init__(self) -> None:
        self.events: list[HistoryEvent] = []

    async def add(self, event: HistoryEvent) -> None:
        self.events.append(event)

    async def list(self, limit: int = 50) -> Sequence[HistoryEvent]:
        return list(reversed(self.events))[:limit]


class MemoryStatsCacheRepository:
    """Cache de estatísticas em memória."""

    def __init__(self) -> None:
        self.stats: PoolStats | None = None

    async def get(self) -> PoolStats | None:
        return self.stats

    async def set(self, stats: PoolStats) -> None:
        self.stats = stats


class FakeMinerProcess:
    """Processo minerador simulado e controlável."""

    def __init__(
        self,
        status: MinerStatus | None = None,
        fail_start: MinerError | None = None,
        stream: Sequence[LogEntry] = (),
    ) -> None:
        self._status = status or MinerStatus()
        self._fail_start = fail_start
        self._stream = list(stream)
        self._buffer: list[LogEntry] = []
        self.started_configs: list[MiningConfig] = []
        self.stop_error: MinerError | None = None

    async def start(self, config: MiningConfig) -> MinerStatus:
        if self._fail_start is not None:
            raise self._fail_start
        if self._status.state in (MinerState.STARTING, MinerState.RUNNING):
            raise MinerAlreadyRunningError("o minerador já está em execução")
        self.started_configs.append(config)
        self._status = MinerStatus(
            state=MinerState.RUNNING,
            pid=4242,
            threads=config.threads,
            hashrate=1_500_000.0,
            started_at=1000.0,
        )
        return self._status

    async def stop(self) -> MinerStatus:
        if self.stop_error is not None:
            raise self.stop_error
        if self._status.state != MinerState.RUNNING:
            raise MinerNotRunningError("o minerador não está em execução")
        self._status = MinerStatus(state=MinerState.STOPPED)
        return self._status

    def status(self) -> MinerStatus:
        return self._status

    def buffer(self) -> Sequence[LogEntry]:
        return tuple(self._buffer)

    def subscribe(self) -> AsyncIterator[LogEntry]:
        return self._stream_entries()

    async def _stream_entries(self) -> AsyncIterator[LogEntry]:
        for entry in self._stream:
            yield entry

    def push(self, entry: LogEntry) -> None:
        self._buffer.append(entry)


class FakePoolClient:
    """Cliente de pool simulado."""

    def __init__(self, stats: PoolStats | None = None, error: Exception | None = None) -> None:
        self.stats = stats
        self.error = error
        self.calls = 0
        self.closed = False

    async def fetch(self, address: str) -> PoolStats:
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.stats is not None:
            return self.stats
        return PoolStats(
            address=address,
            found=True,
            workers=1,
            shares=42,
            best_share=1.5e11,
            hashrates={"hashrate1m": 2_000_000.0},
            raw={"shares": 42},
            fetched_at=1000.0,
        )

    async def aclose(self) -> None:
        self.closed = True


class FakeProber:
    """Testador de conectividade simulado."""

    def __init__(
        self,
        result: ConnectionProbe | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[PoolEndpoint] = []

    async def probe(self, endpoint: PoolEndpoint) -> ConnectionProbe:
        self.calls.append(endpoint)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return ConnectionProbe(
            endpoint=endpoint,
            reachable=True,
            address="203.0.113.10",
            latency_ms=12.5,
        )


class FakeResolver:
    """Resolvedor IPv4 simulado."""

    def __init__(self, ip: str = "203.0.113.10", error: Exception | None = None) -> None:
        self.ip = ip
        self.error = error
        self.calls: list[str] = []

    async def resolve_ipv4(self, host: str) -> str:
        self.calls.append(host)
        if self.error is not None:
            raise self.error
        return self.ip
