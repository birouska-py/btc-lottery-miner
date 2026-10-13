"""Repositórios SQLite (adaptadores das portas de persistência)."""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from typing import Any

import aiosqlite

from app.application.models import AppSettings
from app.application.ports import Clock
from app.domain.history import HistoryEvent
from app.domain.stats import PoolStats
from app.domain.wallet import Fingerprint, Wallet, WalletAddress
from app.infrastructure.database import Database


class SqliteWalletRepository:
    """Persistência da carteira (linha única ``id = 1``)."""

    def __init__(self, database: Database, clock: Clock = time.time) -> None:
        self._database = database
        self._clock = clock

    async def get(self) -> Wallet | None:
        """Retorna a carteira configurada, se houver."""
        async with self._database.connection.execute(
            "SELECT address, fingerprint, seed_stored, created_at FROM wallet WHERE id = 1"
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        raw_fingerprint = row["fingerprint"]
        return Wallet(
            address=WalletAddress(row["address"]),
            created_at=float(row["created_at"]),
            fingerprint=Fingerprint(raw_fingerprint) if raw_fingerprint else None,
            seed_stored=bool(row["seed_stored"]),
        )

    async def save(self, wallet: Wallet) -> None:
        """Cria/atualiza a carteira."""
        await self._database.connection.execute(
            """
            INSERT INTO wallet (id, address, fingerprint, seed_stored, created_at)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                address = excluded.address,
                fingerprint = excluded.fingerprint,
                seed_stored = excluded.seed_stored,
                created_at = excluded.created_at
            """,
            (
                str(wallet.address),
                str(wallet.fingerprint) if wallet.fingerprint else None,
                1 if wallet.seed_stored else 0,
                wallet.created_at,
            ),
        )
        await self._database.connection.commit()

    async def clear(self) -> None:
        """Remove a carteira."""
        await self._database.connection.execute("DELETE FROM wallet WHERE id = 1")
        await self._database.connection.commit()


class SqliteSecretRepository:
    """Persistência de segredos já cifrados."""

    def __init__(self, database: Database, clock: Clock = time.time) -> None:
        self._database = database
        self._clock = clock

    async def get(self, name: str) -> str | None:
        """Token cifrado associado a ``name``, se existir."""
        async with self._database.connection.execute(
            "SELECT token FROM secrets WHERE name = ?", (name,)
        ) as cursor:
            row = await cursor.fetchone()
        return str(row["token"]) if row is not None else None

    async def set(self, name: str, value: str) -> None:
        """Grava/atualiza um token cifrado."""
        await self._database.connection.execute(
            """
            INSERT INTO secrets (name, token, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                token = excluded.token,
                created_at = excluded.created_at
            """,
            (name, value, self._clock()),
        )
        await self._database.connection.commit()

    async def delete(self, name: str) -> None:
        """Remove um segredo."""
        await self._database.connection.execute("DELETE FROM secrets WHERE name = ?", (name,))
        await self._database.connection.commit()


class SqliteSettingsRepository:
    """Persistência das preferências (linha única ``id = 1``)."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def get(self) -> AppSettings | None:
        """Preferências salvas, se houver."""
        async with self._database.connection.execute(
            "SELECT threads, worker, pool_url, algorithm, force_ipv4 FROM settings WHERE id = 1"
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return AppSettings(
            threads=int(row["threads"]),
            worker=str(row["worker"]),
            pool_url=str(row["pool_url"]),
            algorithm=str(row["algorithm"]),
            force_ipv4=bool(row["force_ipv4"]),
        )

    async def save(self, settings: AppSettings) -> None:
        """Cria/atualiza as preferências."""
        await self._database.connection.execute(
            """
            INSERT INTO settings
                (id, threads, worker, pool_url, algorithm, force_ipv4, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                threads = excluded.threads,
                worker = excluded.worker,
                pool_url = excluded.pool_url,
                algorithm = excluded.algorithm,
                force_ipv4 = excluded.force_ipv4,
                updated_at = excluded.updated_at
            """,
            (
                settings.threads,
                settings.worker,
                settings.pool_url,
                settings.algorithm,
                1 if settings.force_ipv4 else 0,
                time.time(),
            ),
        )
        await self._database.connection.commit()


class SqliteHistoryRepository:
    """Histórico de execução."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def add(self, event: HistoryEvent) -> None:
        """Registra um evento."""
        await self._database.connection.execute(
            "INSERT INTO history (kind, detail, created_at) VALUES (?, ?, ?)",
            (event.kind, json.dumps(dict(event.detail)), event.created_at),
        )
        await self._database.connection.commit()

    async def list(self, limit: int = 50) -> Sequence[HistoryEvent]:
        """Últimos eventos (mais recentes primeiro)."""
        async with self._database.connection.execute(
            "SELECT id, kind, detail, created_at FROM history ORDER BY id DESC LIMIT ?",
            (max(1, limit),),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._to_event(row) for row in rows]

    @staticmethod
    def _to_event(row: aiosqlite.Row) -> HistoryEvent:
        detail: dict[str, Any] = json.loads(row["detail"])
        return HistoryEvent(
            id=int(row["id"]),
            kind=str(row["kind"]),
            detail=detail,
            created_at=float(row["created_at"]),
        )


class SqliteStatsCacheRepository:
    """Cache em disco das estatísticas da pool."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def get(self) -> PoolStats | None:
        """Estatística cacheada, se houver."""
        async with self._database.connection.execute(
            "SELECT payload, fetched_at FROM pool_stats LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        payload: dict[str, Any] = json.loads(row["payload"])
        return PoolStats(
            address=str(payload["address"]),
            found=bool(payload["found"]),
            workers=payload.get("workers"),
            shares=payload.get("shares"),
            last_share=payload.get("last_share"),
            best_share=payload.get("best_share"),
            best_ever=payload.get("best_ever"),
            hashrates=payload.get("hashrates", {}),
            raw=payload.get("raw", {}),
            fetched_at=float(row["fetched_at"]),
        )

    async def set(self, stats: PoolStats) -> None:
        """Grava/atualiza as estatísticas."""
        payload = json.dumps(
            {
                "address": stats.address,
                "found": stats.found,
                "workers": stats.workers,
                "shares": stats.shares,
                "last_share": stats.last_share,
                "best_share": stats.best_share,
                "best_ever": stats.best_ever,
                "hashrates": dict(stats.hashrates),
                "raw": dict(stats.raw),
            }
        )
        await self._database.connection.execute(
            """
            INSERT INTO pool_stats (address, payload, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(address) DO UPDATE SET
                payload = excluded.payload,
                fetched_at = excluded.fetched_at
            """,
            (stats.address, payload, stats.fetched_at),
        )
        await self._database.connection.commit()
