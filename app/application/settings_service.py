"""Serviço de preferências (threads, worker, pool)."""

from __future__ import annotations

from app.application.models import AppSettings
from app.application.ports import SettingsRepository
from app.domain.mining import validate_pool_url, validate_worker

DEFAULT_WORKER = "solo"


class SettingsService:
    """Lê e atualiza as preferências do usuário, aplicando limites e validações."""

    def __init__(
        self,
        repository: SettingsRepository,
        defaults: AppSettings,
        max_threads: int,
    ) -> None:
        self._repository = repository
        self._defaults = defaults
        self._max_threads = max_threads

    async def get(self) -> AppSettings:
        """Preferências atuais (ou os padrões)."""
        stored = await self._repository.get()
        if stored is None:
            return self._defaults
        return self._normalize(stored)

    async def update(
        self,
        *,
        threads: int | None = None,
        worker: str | None = None,
        pool_url: str | None = None,
        algorithm: str | None = None,
    ) -> AppSettings:
        """Atualiza parcialmente as preferências e devolve o estado final."""
        current = await self.get()
        updated = AppSettings(
            threads=current.threads if threads is None else threads,
            worker=current.worker if worker is None else worker,
            pool_url=current.pool_url if pool_url is None else pool_url,
            algorithm=current.algorithm if algorithm is None else algorithm,
        )
        normalized = self._normalize(updated)
        await self._repository.save(normalized)
        return normalized

    def _normalize(self, settings: AppSettings) -> AppSettings:
        threads = max(1, min(int(settings.threads), self._max_threads))
        worker = settings.worker.strip() or DEFAULT_WORKER
        validate_worker(worker)
        validate_pool_url(settings.pool_url)
        return AppSettings(
            threads=threads,
            worker=worker,
            pool_url=settings.pool_url,
            algorithm=settings.algorithm or self._defaults.algorithm,
        )
