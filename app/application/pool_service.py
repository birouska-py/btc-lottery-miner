"""Serviço de monitoramento da pool (com cache em disco)."""

from __future__ import annotations

import time

from app.application.ports import (
    Clock,
    PoolStatsClient,
    StatsCacheRepository,
)
from app.application.wallet_service import WalletService
from app.domain.stats import PoolStats


class PoolService:
    """Consulta as estatísticas públicas da pool respeitando um TTL de cache."""

    def __init__(
        self,
        client: PoolStatsClient,
        cache: StatsCacheRepository,
        wallets: WalletService,
        ttl_seconds: int = 30,
        clock: Clock = time.time,
    ) -> None:
        self._client = client
        self._cache = cache
        self._wallets = wallets
        self._ttl = ttl_seconds
        self._clock = clock

    async def get(self, refresh: bool = False) -> PoolStats:
        """Estatísticas da pool para a carteira atual."""
        wallet = await self._wallets.require_wallet()
        address = str(wallet.address)
        now = self._clock()

        cached = await self._cache.get()
        if (
            cached is not None
            and cached.address == address
            and not refresh
            and (now - cached.fetched_at) < self._ttl
        ):
            return cached

        stats = await self._client.fetch(address)
        fresh = PoolStats(
            address=stats.address,
            found=stats.found,
            workers=stats.workers,
            shares=stats.shares,
            last_share=stats.last_share,
            best_share=stats.best_share,
            best_ever=stats.best_ever,
            hashrates=stats.hashrates,
            raw=stats.raw,
            fetched_at=now,
        )
        await self._cache.set(fresh)
        return fresh
