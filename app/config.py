"""Configuração da aplicação (camada de composição).

Centraliza a leitura de variáveis de ambiente (prefixo ``LOTTERY_``) e do arquivo
``.env``. Nenhum segredo é lido aqui: a *seed* e chaves derivadas vivem apenas no
banco criptografado dentro do volume persistente.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração tipada e validada da aplicação."""

    model_config = SettingsConfigDict(
        env_prefix="LOTTERY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Field(default=Path("data"))
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080, ge=1, le=65535)

    default_pool_url: str = Field(default="stratum+tcp://solo.ckpool.org:3333")
    ckpool_base_url: str = Field(default="https://solo.ckpool.org")

    default_threads: int = Field(default=1, ge=1)
    max_threads: int = Field(default=256, ge=1)

    log_buffer_size: int = Field(default=500, ge=1)
    pool_stats_ttl_seconds: int = Field(default=30, ge=0)
    request_timeout_seconds: float = Field(default=10.0, gt=0)

    cpuminer_bin: str = Field(default="cpuminer")

    @property
    def db_path(self) -> Path:
        """Caminho do banco SQLite persistente dentro do volume."""
        return self.data_dir / "app.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna a configuração singleton (cacheada)."""
    return Settings()
