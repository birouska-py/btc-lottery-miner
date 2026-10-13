"""Testes do serviço de preferências."""

from __future__ import annotations

import pytest

from app.application.models import AppSettings
from app.application.settings_service import SettingsService
from app.domain.errors import ValidationError
from tests.fakes import MemorySettingsRepository

DEFAULTS = AppSettings(
    threads=2,
    worker="solo",
    pool_url="stratum+tcp://solo.ckpool.org:3333",
    algorithm="sha256d",
)


def make_service(
    repository: MemorySettingsRepository | None = None,
    max_threads: int = 8,
) -> SettingsService:
    return SettingsService(repository or MemorySettingsRepository(), DEFAULTS, max_threads)


async def test_get_returns_defaults_when_empty() -> None:
    assert await make_service().get() == DEFAULTS


async def test_update_partial_persists() -> None:
    repository = MemorySettingsRepository()
    service = make_service(repository)
    updated = await service.update(threads=5, worker="rig")
    assert updated.threads == 5
    assert updated.worker == "rig"
    assert updated.pool_url == DEFAULTS.pool_url
    assert repository.settings == updated


async def test_threads_are_clamped_to_bounds() -> None:
    service = make_service(max_threads=4)
    assert (await service.update(threads=99)).threads == 4
    assert (await service.update(threads=0)).threads == 1


async def test_empty_worker_falls_back_to_default() -> None:
    assert (await make_service().update(worker="   ")).worker == "solo"


async def test_invalid_worker_and_pool_are_rejected() -> None:
    service = make_service()
    with pytest.raises(ValidationError):
        await service.update(worker="a b")
    with pytest.raises(ValidationError):
        await service.update(pool_url="ftp://pool")


async def test_get_normalizes_stored_values() -> None:
    repository = MemorySettingsRepository()
    repository.settings = AppSettings(
        threads=999,
        worker="",
        pool_url="stratum+tcp://x:1",
        algorithm="",
    )
    normalized = await make_service(repository, max_threads=3).get()
    assert normalized.threads == 3
    assert normalized.worker == "solo"
    assert normalized.algorithm == DEFAULTS.algorithm
