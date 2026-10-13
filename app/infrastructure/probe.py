"""Adaptadores de rede: teste de conectividade (TCP) e resolução IPv4."""

from __future__ import annotations

import asyncio
import contextlib
import socket
import time
from collections.abc import Callable

from app.domain.connectivity import ConnectionProbe, PoolEndpoint
from app.domain.errors import PoolError


class SocketProber:
    """Testa se dá para abrir uma conexão TCP no endpoint da pool.

    Resolve preferindo **IPv4** (útil quando a rede tem IPv6 anunciado mas sem rota,
    que é a causa clássica do ``Network is unreachable``).
    """

    def __init__(
        self,
        timeout: float = 5.0,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._timeout = timeout
        self._clock = clock

    async def probe(self, endpoint: PoolEndpoint) -> ConnectionProbe:
        """Tenta abrir (e fechar) uma conexão TCP, devolvendo o resultado."""
        loop = asyncio.get_running_loop()
        try:
            addresses = await loop.getaddrinfo(
                endpoint.host,
                endpoint.port,
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            return ConnectionProbe(
                endpoint=endpoint,
                reachable=False,
                error=f"falha de DNS: {exc.strerror or exc}",
            )

        address = str(addresses[0][4][0])
        started = self._clock()
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(address, endpoint.port),
                timeout=self._timeout,
            )
        except TimeoutError:
            return ConnectionProbe(
                endpoint=endpoint,
                reachable=False,
                address=address,
                error="tempo esgotado",
            )
        except OSError as exc:
            return ConnectionProbe(
                endpoint=endpoint,
                reachable=False,
                address=address,
                error=exc.strerror or str(exc),
            )

        latency_ms = round((self._clock() - started) * 1000, 1)
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        return ConnectionProbe(
            endpoint=endpoint,
            reachable=True,
            address=address,
            latency_ms=latency_ms,
        )


class SocketHostResolver:
    """Resolve um host para o primeiro endereço IPv4."""

    async def resolve_ipv4(self, host: str) -> str:
        """Devolve o IPv4 de ``host``; levanta :class:`PoolError` se não resolver."""
        loop = asyncio.get_running_loop()
        try:
            addresses = await loop.getaddrinfo(
                host,
                None,
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise PoolError(
                f"não foi possível resolver '{host}' para IPv4: {exc.strerror or exc}"
            ) from exc
        if not addresses:
            raise PoolError(f"não foi possível resolver '{host}' para IPv4")
        return str(addresses[0][4][0])
