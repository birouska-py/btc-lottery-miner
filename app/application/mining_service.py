"""Serviço de mineração — orquestra carteira, preferências e o processo cpuminer."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Sequence

from app.application.ports import (
    Clock,
    HistoryRepository,
    HostResolver,
    MinerProcess,
)
from app.application.settings_service import SettingsService
from app.application.wallet_service import WalletService
from app.domain.connectivity import PoolEndpoint
from app.domain.history import HistoryEvent
from app.domain.mining import LogEntry, MinerStatus, MiningConfig


class MiningService:
    """Casos de uso de start/stop/status/histórico e streaming de logs."""

    def __init__(
        self,
        process: MinerProcess,
        wallets: WalletService,
        settings: SettingsService,
        history: HistoryRepository,
        resolver: HostResolver,
        clock: Clock = time.time,
    ) -> None:
        self._process = process
        self._wallets = wallets
        self._settings = settings
        self._history = history
        self._resolver = resolver
        self._clock = clock

    async def start(self, threads: int | None = None) -> MinerStatus:
        """Inicia a mineração (opcionalmente ajustando as threads)."""
        wallet = await self._wallets.require_wallet()
        preferences = await self._settings.get()
        if threads is not None:
            preferences = await self._settings.update(threads=threads)

        pool_url = preferences.pool_url
        if preferences.force_ipv4:
            endpoint = PoolEndpoint.parse(pool_url)
            resolved = await self._resolver.resolve_ipv4(endpoint.host)
            pool_url = str(endpoint.with_host(resolved))

        config = MiningConfig(
            address=str(wallet.address),
            worker=preferences.worker,
            threads=preferences.threads,
            pool_url=pool_url,
            algorithm=preferences.algorithm,
        )
        status = await self._process.start(config)
        await self._history.add(
            HistoryEvent(
                kind="start",
                created_at=self._clock(),
                detail={
                    "threads": config.threads,
                    "worker": config.worker,
                    "pool_url": preferences.pool_url,
                    "force_ipv4": preferences.force_ipv4,
                },
            )
        )
        return status

    async def stop(self) -> MinerStatus:
        """Para a mineração."""
        status = await self._process.stop()
        await self._history.add(
            HistoryEvent(kind="stop", created_at=self._clock(), detail={})
        )
        return status

    def status(self) -> MinerStatus:
        """Estado atual do minerador."""
        return self._process.status()

    async def history(self, limit: int = 50) -> Sequence[HistoryEvent]:
        """Últimos eventos de execução."""
        return await self._history.list(limit)

    def subscribe(self) -> AsyncIterator[LogEntry]:
        """Assina o stream de logs em tempo real."""
        return self._process.subscribe()

    def buffer(self) -> Sequence[LogEntry]:
        """Últimas linhas de log em memória."""
        return self._process.buffer()
