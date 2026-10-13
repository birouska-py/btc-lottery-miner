"""Domínio de estatísticas da pool."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PoolStats:
    """Estatísticas públicas da pool para um endereço (cache em disco)."""

    address: str
    found: bool
    workers: int | None = None
    shares: int | None = None
    last_share: int | None = None
    best_share: float | None = None
    best_ever: float | None = None
    hashrates: Mapping[str, float] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)
    fetched_at: float = 0.0

    @classmethod
    def not_found(cls, address: str, fetched_at: float) -> PoolStats:
        """Estatísticas para um endereço que a pool ainda não reconhece."""
        return cls(address=address, found=False, fetched_at=fetched_at)
