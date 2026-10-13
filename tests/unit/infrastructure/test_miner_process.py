"""Testes do adaptador de processo do cpuminer (subprocesso real controlado)."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from pathlib import Path

import pytest

from app.domain.errors import MinerAlreadyRunningError, MinerError, MinerNotRunningError
from app.domain.mining import MinerState, MiningConfig
from app.infrastructure.miner_process import CpuminerProcess
from tests.conftest import BIP84_ADDRESS

CONFIG = MiningConfig(
    address=BIP84_ADDRESS,
    worker="solo",
    threads=2,
    pool_url="stratum+tcp://solo.ckpool.org:3333",
)


def make_script(tmp_path: Path, name: str, body: str) -> str:
    """Cria um script executável que faz o papel do cpuminer."""
    path = tmp_path / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return str(path)


async def wait_until(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.02)


async def test_start_reads_output_and_stop(tmp_path: Path) -> None:
    script = make_script(
        tmp_path,
        "miner.sh",
        'echo "accepted: 2/3 (66.7%), 1.23 MH/s yes!"\n'
        'echo "rejected: 1"\n'
        'echo "stale: 5"\n'
        'echo ""\n'
        "sleep 30\n",
    )
    process = CpuminerProcess(binary=script, buffer_size=10)

    status = await process.start(CONFIG)
    assert status.state is MinerState.RUNNING
    assert status.pid is not None

    await wait_until(lambda: process.status().shares.stale == 5)
    snapshot = process.status()
    assert snapshot.hashrate == pytest.approx(1.23e6)
    assert snapshot.shares.accepted == 2
    assert snapshot.shares.rejected == 1
    assert process.buffer()

    stopped = await process.stop()
    assert stopped.state is MinerState.STOPPED
    assert stopped.pid is None


async def test_start_with_missing_binary(tmp_path: Path) -> None:
    process = CpuminerProcess(binary=str(tmp_path / "does-not-exist"))
    with pytest.raises(MinerError):
        await process.start(CONFIG)
    snapshot = process.status()
    assert snapshot.state is MinerState.ERROR
    assert snapshot.last_error is not None


async def test_start_with_non_executable_binary(tmp_path: Path) -> None:
    path = tmp_path / "noexec.sh"
    path.write_text("#!/bin/sh\necho hi\n")
    path.chmod(0o644)
    process = CpuminerProcess(binary=str(path))
    with pytest.raises(MinerError):
        await process.start(CONFIG)


async def test_watch_exit_ignores_graceful_stop(tmp_path: Path) -> None:
    script = make_script(tmp_path, "quick.sh", "exit 0\n")
    process = CpuminerProcess(binary=script)
    child = await asyncio.create_subprocess_exec(
        script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    process._state = MinerState.STOPPING  # type: ignore[attr-defined]
    await process._watch_exit(child)  # type: ignore[attr-defined]
    assert process.status().state is MinerState.STOPPING


async def test_start_twice_raises(tmp_path: Path) -> None:
    script = make_script(tmp_path, "miner.sh", "sleep 30\n")
    process = CpuminerProcess(binary=script)
    await process.start(CONFIG)
    with pytest.raises(MinerAlreadyRunningError):
        await process.start(CONFIG)
    await process.stop()


async def test_stop_when_not_running() -> None:
    process = CpuminerProcess(binary="cpuminer")
    with pytest.raises(MinerNotRunningError):
        await process.stop()


async def test_unexpected_exit_sets_error(tmp_path: Path) -> None:
    script = make_script(tmp_path, "crash.sh", "exit 3\n")
    process = CpuminerProcess(binary=script)
    await process.start(CONFIG)
    await wait_until(lambda: process.status().state is MinerState.ERROR)
    assert "código 3" in (process.status().last_error or "")


async def test_stop_kills_stubborn_process(tmp_path: Path) -> None:
    script = make_script(tmp_path, "stubborn.sh", "trap '' TERM\nwhile true; do sleep 1; done\n")
    process = CpuminerProcess(binary=script, stop_timeout=0.5)
    await process.start(CONFIG)
    stopped = await process.stop()
    assert stopped.state is MinerState.STOPPED


async def test_subscribe_streams_and_closes(tmp_path: Path) -> None:
    script = make_script(tmp_path, "miner.sh", 'echo "hello world"\nsleep 30\n')
    process = CpuminerProcess(binary=script)

    stream = process.subscribe()
    first_pending = asyncio.ensure_future(stream.__anext__())
    await asyncio.sleep(0)  # registra a fila do assinante antes do start

    await process.start(CONFIG)
    first = await asyncio.wait_for(first_pending, 5)
    assert first.stream == "system"

    second = await asyncio.wait_for(stream.__anext__(), 5)
    assert "hello world" in second.message

    await stream.aclose()
    await process.stop()


async def test_read_stream_with_none_is_noop() -> None:
    process = CpuminerProcess(binary="cpuminer")
    await process._read_stream(None, "stdout")  # type: ignore[attr-defined]


async def test_publish_drops_when_subscriber_queue_full() -> None:
    process = CpuminerProcess(binary="cpuminer", buffer_size=4)
    stream = process.subscribe()
    pending = asyncio.ensure_future(stream.__anext__())
    await asyncio.sleep(0)  # deixa o gerador registrar a fila do assinante

    for index in range(1100):
        process._publish("system", f"line {index}")  # type: ignore[attr-defined]

    assert len(process.buffer()) == 4

    pending.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await pending
    await stream.aclose()
