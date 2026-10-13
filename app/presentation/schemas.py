"""Schemas de entrada/saída da API (Pydantic)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

WORD_CHOICES = (12, 15, 18, 21, 24)
WordCount = Literal[12, 15, 18, 21, 24]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(_Base):
    """Estado geral do serviço."""

    status: str
    version: str
    miner_state: str


class WalletStatus(_Base):
    """Situação da carteira configurada."""

    configured: bool
    address: str | None = None
    fingerprint: str | None = None
    seed_stored: bool = False
    network: str | None = None


class GenerateRequest(_Base):
    """Parâmetros de geração de seed."""

    words: WordCount = 12


class GenerateResponse(_Base):
    """Seed recém-gerada (exibida apenas a partir daqui)."""

    mnemonic: list[str]
    address: str
    fingerprint: str
    path: str


class ConfirmRequest(_Base):
    """Confirmação da seed e persistência da carteira."""

    mnemonic: str = Field(min_length=1)
    store_seed: bool = False
    passphrase: str | None = None


class ImportAddressRequest(_Base):
    """Importação de um endereço público existente."""

    address: str = Field(min_length=1)


class RevealRequest(_Base):
    """Senha para revelar a seed armazenada."""

    passphrase: str = Field(min_length=1)


class RevealResponse(_Base):
    """Seed revelada."""

    mnemonic: list[str]


class VerifyRequest(_Base):
    """Verificação de uma seed contra a carteira atual."""

    mnemonic: str = Field(min_length=1)


class VerifyResponse(_Base):
    """Resultado da verificação."""

    matches: bool


class SettingsModel(_Base):
    """Preferências do usuário."""

    threads: int = Field(ge=1)
    worker: str
    pool_url: str
    algorithm: str
    force_ipv4: bool


class SettingsUpdate(_Base):
    """Atualização parcial das preferências."""

    threads: int | None = Field(default=None, ge=1)
    worker: str | None = None
    pool_url: str | None = None
    algorithm: str | None = None
    force_ipv4: bool | None = None


class PoolPresetModel(_Base):
    """Pool pré-configurada exibida no seletor."""

    name: str
    url: str


class PoolProbeRequest(_Base):
    """URL da pool a ser testada."""

    pool_url: str = Field(min_length=1)


class PoolProbeModel(_Base):
    """Resultado do teste de conectividade com a pool."""

    url: str
    host: str
    port: int
    scheme: str
    reachable: bool
    address: str | None
    latency_ms: float | None
    error: str | None


class ShareStatsModel(_Base):
    """Contadores de shares."""

    accepted: int
    rejected: int
    stale: int
    best_share: float


class MinerStatusModel(_Base):
    """Estado do minerador exposto pela API."""

    state: str
    pid: int | None
    threads: int
    hashrate: float
    hashrate_human: str
    uptime_seconds: float
    started_at: float | None
    last_error: str | None
    restarts: int
    shares: ShareStatsModel


class StartRequest(_Base):
    """Início da mineração (threads opcionais)."""

    threads: int | None = Field(default=None, ge=1)


class LogModel(_Base):
    """Linha de log."""

    timestamp: float
    stream: str
    message: str


class HistoryModel(_Base):
    """Evento do histórico."""

    id: int | None
    kind: str
    detail: dict[str, Any]
    created_at: float


class PoolStatsModel(_Base):
    """Estatísticas da pool."""

    address: str
    found: bool
    workers: int | None
    shares: int | None
    last_share: int | None
    best_share: float | None
    best_ever: float | None
    hashrates: dict[str, float]
    fetched_at: float
