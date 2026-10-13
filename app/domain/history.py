"""Histórico de execução do minerador."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class HistoryEvent:
    """Evento persistido no histórico (start/stop/erro/restart)."""

    kind: str
    created_at: float
    detail: Mapping[str, Any] = field(default_factory=dict)
    id: int | None = None
