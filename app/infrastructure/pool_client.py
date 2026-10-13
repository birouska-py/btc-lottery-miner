"""Cliente das estatísticas públicas da pool (CKPool)."""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

from app.application.ports import Clock
from app.domain.errors import PoolError
from app.domain.stats import PoolStats

_RATE_RE = re.compile(r"^(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[kKmMgGtTpP]?)\s*(?:[Hh]/[Ss])?$")
_RATE_UNITS: dict[str, float] = {
    "": 1.0,
    "k": 1e3,
    "m": 1e6,
    "g": 1e9,
    "t": 1e12,
    "p": 1e15,
}
_HASHRATE_KEYS = ("hashrate1m", "hashrate5m", "hashrate1hr", "hashrate1d", "hashrate7d")


def _parse_rate(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _RATE_RE.match(str(value).strip())
    if match is None:
        return None
    return float(match.group("value")) * _RATE_UNITS[match.group("unit").lower()]


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class CkPoolClient:
    """Consulta ``<base>/users/<endereço>`` e normaliza a resposta."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
        clock: Clock = time.time,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._clock = clock

    async def fetch(self, address: str) -> PoolStats:
        """Busca as estatísticas do endereço; 404 vira :class:`PoolStats` vazio."""
        url = f"{self._base_url}/users/{address}"
        try:
            response = await self._client.get(url)
        except httpx.HTTPError as exc:
            raise PoolError(f"falha ao consultar a pool: {exc}") from exc

        if response.status_code == httpx.codes.NOT_FOUND:
            return PoolStats.not_found(address, self._clock())
        if response.status_code != httpx.codes.OK:
            raise PoolError(f"a pool respondeu com status {response.status_code}")

        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise PoolError("resposta inválida (JSON) da pool") from exc
        if not isinstance(payload, dict):
            raise PoolError("resposta inesperada da pool")

        hashrates = {
            key: rate
            for key in _HASHRATE_KEYS
            if (rate := _parse_rate(payload.get(key))) is not None
        }
        return PoolStats(
            address=address,
            found=True,
            workers=_parse_int(payload.get("workers")),
            shares=_parse_int(payload.get("shares")),
            last_share=_parse_int(payload.get("lastshare")),
            best_share=_parse_float(payload.get("bestshare")),
            best_ever=_parse_float(payload.get("bestever")),
            hashrates=hashrates,
            raw=payload,
            fetched_at=self._clock(),
        )

    async def aclose(self) -> None:
        """Fecha o cliente HTTP subjacente (apenas se foi criado aqui)."""
        if self._owns_client:
            await self._client.aclose()
