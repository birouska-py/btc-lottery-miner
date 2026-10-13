"""Controle assíncrono do processo ``cpuminer``.

Gerencia o subprocesso, faz *streaming* não-bloqueante de ``stdout``/``stderr``,
interpreta hashrate/shares e publica os logs para os assinantes (SSE).
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import time
from collections import deque
from collections.abc import AsyncIterator, Sequence

from app.application.ports import Clock
from app.domain.errors import MinerAlreadyRunningError, MinerError, MinerNotRunningError
from app.domain.mining import HashRate, LogEntry, MinerState, MinerStatus, MiningConfig, ShareStats

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_ACCEPTED_RE = re.compile(r"accepted:\s*(\d+)\s*/\s*(\d+)")
_REJECTED_RE = re.compile(r"rejected:\s*(\d+)")
_STALE_RE = re.compile(r"stale:\s*(\d+)")


class CpuminerProcess:
    """Adaptador que controla um processo ``cpuminer`` (uma instância por aplicação)."""

    def __init__(
        self,
        binary: str = "cpuminer",
        buffer_size: int = 500,
        stop_timeout: float = 10.0,
        clock: Clock = time.time,
    ) -> None:
        self._binary = binary
        self._buffer: deque[LogEntry] = deque(maxlen=buffer_size)
        self._subscribers: set[asyncio.Queue[LogEntry]] = set()
        self._stop_timeout = stop_timeout
        self._clock = clock

        self._process: asyncio.subprocess.Process | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._state = MinerState.STOPPED
        self._pid: int | None = None
        self._threads = 0
        self._hashrate = 0.0
        self._shares = ShareStats()
        self._started_at: float | None = None
        self._last_error: str | None = None
        self._restarts = 0

    async def start(self, config: MiningConfig) -> MinerStatus:
        """Inicia o processo do cpuminer."""
        if self._state in (MinerState.STARTING, MinerState.RUNNING):
            raise MinerAlreadyRunningError("o minerador já está em execução")

        self._state = MinerState.STARTING
        self._last_error = None
        self._shares = ShareStats()
        self._hashrate = 0.0
        self._threads = config.threads
        command = config.as_command(self._binary)

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError) as exc:
            self._state = MinerState.ERROR
            self._last_error = f"não foi possível executar '{self._binary}': {exc}"
            self._publish("system", self._last_error)
            raise MinerError(self._last_error) from exc

        self._process = process
        self._pid = process.pid
        self._started_at = self._clock()
        self._state = MinerState.RUNNING
        self._tasks = [
            asyncio.create_task(self._read_stream(process.stdout, "stdout")),
            asyncio.create_task(self._read_stream(process.stderr, "stderr")),
            asyncio.create_task(self._watch_exit(process)),
        ]
        self._publish("system", f"minerador iniciado (pid {process.pid}, {config.threads} threads)")
        return self.status()

    async def stop(self) -> MinerStatus:
        """Encerra o processo com terço de tolerância (SIGTERM → SIGKILL)."""
        process = self._process
        if process is None or process.returncode is not None:
            self._state = MinerState.STOPPED
            raise MinerNotRunningError("o minerador não está em execução")

        self._state = MinerState.STOPPING
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=self._stop_timeout)
        except TimeoutError:
            process.kill()
            await process.wait()

        await self._cancel_tasks()
        self._state = MinerState.STOPPED
        self._pid = None
        self._started_at = None
        self._process = None
        self._publish("system", "minerador parado")
        return self.status()

    def status(self) -> MinerStatus:
        """Snapshot do estado atual."""
        return MinerStatus(
            state=self._state,
            pid=self._pid,
            threads=self._threads,
            hashrate=self._hashrate,
            shares=self._shares,
            started_at=self._started_at,
            last_error=self._last_error,
            restarts=self._restarts,
        )

    def buffer(self) -> Sequence[LogEntry]:
        """Últimas linhas de log mantidas em memória."""
        return tuple(self._buffer)

    def subscribe(self) -> AsyncIterator[LogEntry]:
        """Assina o stream de logs (usar como *async generator*)."""
        return self._stream()

    async def _stream(self) -> AsyncIterator[LogEntry]:
        queue: asyncio.Queue[LogEntry] = asyncio.Queue(maxsize=1000)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)

    async def _read_stream(
        self,
        stream: asyncio.StreamReader | None,
        name: str,
    ) -> None:
        if stream is None:
            return
        while True:
            raw = await stream.readline()
            if not raw:
                break
            line = _ANSI_RE.sub("", raw.decode("utf-8", errors="replace")).strip()
            if not line:
                continue
            self._observe(line)
            self._publish(name, line)

    def _observe(self, line: str) -> None:
        rate = HashRate.parse(line)
        if rate is not None:
            self._hashrate = rate.hashes_per_second
        accepted = _ACCEPTED_RE.search(line)
        if accepted is not None:
            shares_accepted = int(accepted.group(1))
            total = int(accepted.group(2))
            self._shares = ShareStats(
                accepted=shares_accepted,
                rejected=max(0, total - shares_accepted),
                stale=self._shares.stale,
                best_share=self._shares.best_share,
            )
        rejected = _REJECTED_RE.search(line)
        if rejected is not None:
            self._shares = ShareStats(
                accepted=self._shares.accepted,
                rejected=int(rejected.group(1)),
                stale=self._shares.stale,
                best_share=self._shares.best_share,
            )
        stale = _STALE_RE.search(line)
        if stale is not None:
            self._shares = ShareStats(
                accepted=self._shares.accepted,
                rejected=self._shares.rejected,
                stale=int(stale.group(1)),
                best_share=self._shares.best_share,
            )

    async def _watch_exit(self, process: asyncio.subprocess.Process) -> None:
        return_code = await process.wait()
        if self._state == MinerState.STOPPING:
            return
        self._state = MinerState.ERROR
        self._last_error = f"processo finalizou inesperadamente (código {return_code})"
        self._publish("system", self._last_error)

    async def _cancel_tasks(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks = []

    def _publish(self, stream: str, message: str) -> None:
        entry = LogEntry(timestamp=self._clock(), stream=stream, message=message)
        self._buffer.append(entry)
        for queue in self._subscribers:
            try:
                queue.put_nowait(entry)
            except asyncio.QueueFull:
                continue
