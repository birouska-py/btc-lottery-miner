"""Testes do banco SQLite (conexão e migrações)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.infrastructure.database import Database


async def test_connection_before_connect_raises(tmp_path: Path) -> None:
    database = Database(tmp_path / "app.db")
    with pytest.raises(RuntimeError):
        _ = database.connection
    assert database.path == tmp_path / "app.db"


async def test_connect_creates_file_and_migrates(tmp_path: Path) -> None:
    database = Database(tmp_path / "app.db")
    await database.connect()
    assert (tmp_path / "app.db").exists()
    async with database.connection.execute("PRAGMA user_version") as cursor:
        row = await cursor.fetchone()
    assert row is not None and row[0] == 2
    await database.close()


async def test_connect_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "app.db")
    await database.connect()
    first = database.connection
    await database.connect()
    assert database.connection is first
    await database._migrate()  # type: ignore[attr-defined]
    await database.close()


async def test_close_is_safe_when_not_connected(tmp_path: Path) -> None:
    database = Database(tmp_path / "app.db")
    await database.close()
    await database.connect()
    await database.close()
    await database.close()
