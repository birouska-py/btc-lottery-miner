"""Testes dos value objects de estatística e histórico."""

from __future__ import annotations

from app.domain.history import HistoryEvent
from app.domain.stats import PoolStats


def test_pool_stats_not_found() -> None:
    stats = PoolStats.not_found("bc1qexample", 123.0)
    assert stats.found is False
    assert stats.address == "bc1qexample"
    assert stats.fetched_at == 123.0
    assert stats.workers is None


def test_pool_stats_defaults() -> None:
    stats = PoolStats(address="a", found=True)
    assert stats.hashrates == {}
    assert stats.raw == {}


def test_history_event_defaults() -> None:
    event = HistoryEvent(kind="start", created_at=1.0)
    assert event.detail == {}
    assert event.id is None
