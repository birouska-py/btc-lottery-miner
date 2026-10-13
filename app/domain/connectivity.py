"""Conectividade com a pool — value objects para testar o endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from app.domain.errors import ValidationError

_ALLOWED_SCHEMES = ("stratum+tcp", "stratum+ssl", "stratum")


@dataclass(frozen=True, slots=True)
class PoolEndpoint:
    """Endereço ``host:porta`` de uma pool (extraído da URL stratum)."""

    host: str
    port: int
    scheme: str = "stratum+tcp"

    def __post_init__(self) -> None:
        if self.scheme not in _ALLOWED_SCHEMES:
            raise ValidationError("a URL da pool deve usar stratum+tcp:// ou stratum+ssl://")
        if not self.host:
            raise ValidationError("a URL da pool precisa de um host")
        if not 1 <= self.port <= 65535:
            raise ValidationError("porta inválida na URL da pool")

    @classmethod
    def parse(cls, url: str) -> PoolEndpoint:
        """Interpreta uma URL stratum (ex.: ``stratum+tcp://host:3333``)."""
        parts = urlsplit(url.strip())
        if parts.scheme not in _ALLOWED_SCHEMES:
            raise ValidationError("a URL da pool deve usar stratum+tcp:// ou stratum+ssl://")
        if not parts.hostname:
            raise ValidationError("a URL da pool precisa de um host")
        try:
            port = parts.port
        except ValueError as exc:  # porta fora do intervalo
            raise ValidationError("porta inválida na URL da pool") from exc
        if port is None:
            raise ValidationError("a URL da pool precisa de uma porta (ex.: :3333)")
        return cls(host=parts.hostname, port=port, scheme=parts.scheme)

    def with_host(self, host: str) -> PoolEndpoint:
        """Cópia do endpoint trocando o host (usado ao forçar IPv4)."""
        return PoolEndpoint(host=host, port=self.port, scheme=self.scheme)

    def __str__(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"


@dataclass(frozen=True, slots=True)
class ConnectionProbe:
    """Resultado de um teste de conectividade TCP contra um endpoint."""

    endpoint: PoolEndpoint
    reachable: bool
    address: str | None = None
    latency_ms: float | None = None
    error: str | None = None
