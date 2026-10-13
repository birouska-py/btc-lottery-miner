"""Banco SQLite persistente com migrações versionadas.

O arquivo vive em ``LOTTERY_DATA_DIR/app.db`` (volume Docker). As migrações são
aplicadas de forma idempotente usando ``PRAGMA user_version`` como controle.
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS wallet (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    address     TEXT    NOT NULL,
    fingerprint TEXT,
    seed_stored INTEGER NOT NULL DEFAULT 0,
    created_at  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    threads    INTEGER NOT NULL,
    worker     TEXT    NOT NULL,
    pool_url   TEXT    NOT NULL,
    algorithm  TEXT    NOT NULL,
    updated_at REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS secrets (
    name       TEXT PRIMARY KEY,
    token      TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    detail     TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS pool_stats (
    address    TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    fetched_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS history_created_at_idx ON history (created_at DESC);
"""

_MIGRATIONS: tuple[tuple[int, str], ...] = ((1, _SCHEMA_V1),)


class Database:
    """Gerencia a conexão e o esquema do SQLite."""

    def __init__(self, path: Path, timeout: float = 5.0) -> None:
        self._path = path
        self._timeout = timeout
        self._connection: aiosqlite.Connection | None = None

    @property
    def connection(self) -> aiosqlite.Connection:
        """Conexão ativa (uso interno dos repositórios)."""
        if self._connection is None:
            raise RuntimeError("database não conectado")
        return self._connection

    @property
    def path(self) -> Path:
        """Caminho do arquivo do banco."""
        return self._path

    async def connect(self) -> None:
        """Abre a conexão, aplica PRAGMAs e migra o esquema (idempotente)."""
        if self._connection is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = await aiosqlite.connect(self._path, timeout=self._timeout)
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA journal_mode=WAL")
        await connection.execute("PRAGMA foreign_keys=ON")
        await connection.execute("PRAGMA synchronous=NORMAL")
        self._connection = connection
        await self._migrate()

    async def close(self) -> None:
        """Fecha a conexão, se aberta."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def _migrate(self) -> None:
        version = await self._user_version()
        for target, script in _MIGRATIONS:
            if target > version:
                await self.connection.executescript(script)
                await self.connection.execute(f"PRAGMA user_version={target}")
                await self.connection.commit()

    async def _user_version(self) -> int:
        async with self.connection.execute("PRAGMA user_version") as cursor:
            row = await cursor.fetchone()
        return int(row[0]) if row is not None else 0
