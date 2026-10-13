"""Domínio de mineração — configuração, estado e estatísticas do minerador."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.errors import ValidationError
from app.domain.wallet import WalletAddress

_WORKER_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,32}$")
_HASHRATE_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[kKmMgGtTpP]?)(?:hash|Hash|HASH|[Hh])?/[sS]"
)
_HASHRATE_UNITS: dict[str, float] = {
    "": 1.0,
    "k": 1e3,
    "m": 1e6,
    "g": 1e9,
    "t": 1e12,
    "p": 1e15,
}
_VALID_SCHEMES = ("stratum+tcp://", "stratum+ssl://", "stratum://")


def validate_worker(worker: str) -> None:
    """Valida o nome do worker aceito pela pool."""
    if not _WORKER_RE.match(worker):
        raise ValidationError("o nome do worker aceita apenas [A-Za-z0-9_.-] (1..32)")


def validate_pool_url(pool_url: str) -> None:
    """Valida o esquema da URL da pool."""
    if not pool_url.startswith(_VALID_SCHEMES):
        raise ValidationError("a URL da pool deve usar stratum+tcp:// ou stratum+ssl://")


class MinerState(StrEnum):
    """Estados possíveis do processo minerador."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class HashRate:
    """Taxa de hash (H/s) com parsing tolerante à saída do cpuminer."""

    hashes_per_second: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.hashes_per_second) or self.hashes_per_second < 0:
            raise ValidationError("hashrate deve ser um número finito e não negativo")

    @classmethod
    def parse(cls, text: str) -> HashRate | None:
        """Extrai um hashrate de um trecho textual (ex.: ``1.23 MH/s``)."""
        match = _HASHRATE_RE.search(text)
        if match is None:
            return None
        value = float(match.group("value"))
        unit = match.group("unit").lower()
        return cls(value * _HASHRATE_UNITS[unit])

    def __str__(self) -> str:
        units = ("H/s", "kH/s", "MH/s", "GH/s", "TH/s", "PH/s")
        value = self.hashes_per_second
        index = 0
        while value >= 1000 and index < len(units) - 1:
            value /= 1000
            index += 1
        return f"{value:.2f} {units[index]}"


@dataclass(frozen=True, slots=True)
class MiningConfig:
    """Parâmetros de uma execução do minerador."""

    address: str
    worker: str
    threads: int
    pool_url: str
    algorithm: str = "sha256d"
    password: str = "x"

    def __post_init__(self) -> None:
        WalletAddress(self.address)
        validate_worker(self.worker)
        if self.threads < 1:
            raise ValidationError("é necessário ao menos 1 thread")
        validate_pool_url(self.pool_url)
        if not self.algorithm:
            raise ValidationError("algoritmo é obrigatório")

    @property
    def username(self) -> str:
        """Usuário enviado à pool no formato ``endereço.worker``."""
        return f"{self.address}.{self.worker}"

    def as_command(self, binary: str) -> list[str]:
        """Monta a linha de comando do cpuminer."""
        return [
            binary,
            "-a",
            self.algorithm,
            "-o",
            self.pool_url,
            "-u",
            self.username,
            "-p",
            self.password,
            "-t",
            str(self.threads),
        ]


@dataclass(frozen=True, slots=True)
class ShareStats:
    """Contadores de shares reportados pelo cpuminer."""

    accepted: int = 0
    rejected: int = 0
    stale: int = 0
    best_share: float = 0.0


@dataclass(frozen=True, slots=True)
class LogEntry:
    """Linha de log emitida pelo processo (ou pelo sistema)."""

    timestamp: float
    stream: str
    message: str


@dataclass(slots=True)
class MinerStatus:
    """Estado observável do minerador."""

    state: MinerState = MinerState.STOPPED
    pid: int | None = None
    threads: int = 0
    hashrate: float = 0.0
    shares: ShareStats = field(default_factory=ShareStats)
    started_at: float | None = None
    last_error: str | None = None
    restarts: int = 0

    def uptime(self, now: float) -> float:
        """Segundos desde o início da execução atual (0 se parado)."""
        if self.started_at is None or self.state not in (MinerState.RUNNING, MinerState.STARTING):
            return 0.0
        return max(0.0, now - self.started_at)
