"""Endpoints REST e SSE do dashboard."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from app import __version__
from app.application.models import AppSettings
from app.domain.history import HistoryEvent
from app.domain.mining import HashRate, LogEntry, MinerStatus
from app.domain.stats import PoolStats
from app.domain.wallet import Mnemonic, Wallet
from app.presentation import schemas
from app.presentation.deps import ContainerDep

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.get("/health", response_model=schemas.HealthResponse)
async def health(container: ContainerDep) -> schemas.HealthResponse:
    """Estado geral do serviço (para healthcheck do container)."""
    snapshot = await container.mining.status()
    return schemas.HealthResponse(
        status="ok",
        version=__version__,
        miner_state=snapshot.state.value,
    )


@router.get("/wallet", response_model=schemas.WalletStatus)
async def get_wallet(container: ContainerDep) -> schemas.WalletStatus:
    """Situação da carteira configurada."""
    return _wallet_status(await container.wallets.get_wallet())


@router.post("/wallet/generate", response_model=schemas.GenerateResponse)
async def generate_wallet(
    payload: schemas.GenerateRequest,
    container: ContainerDep,
) -> schemas.GenerateResponse:
    """Gera uma nova seed (não persiste; exibida apenas uma vez)."""
    generated = await container.wallets.generate(payload.words)
    return schemas.GenerateResponse(
        mnemonic=list(generated.mnemonic.words),
        address=str(generated.address),
        fingerprint=str(generated.fingerprint),
        path=generated.path,
    )


@router.post("/wallet/confirm", response_model=schemas.WalletStatus)
async def confirm_wallet(
    payload: schemas.ConfirmRequest,
    container: ContainerDep,
) -> schemas.WalletStatus:
    """Confirma a seed e persiste o endereço derivado."""
    wallet = await container.wallets.confirm(
        Mnemonic(payload.mnemonic),
        store_seed=payload.store_seed,
        passphrase=payload.passphrase,
    )
    return _wallet_status(wallet)


@router.post("/wallet/import/address", response_model=schemas.WalletStatus)
async def import_address(
    payload: schemas.ImportAddressRequest,
    container: ContainerDep,
) -> schemas.WalletStatus:
    """Importa um endereço público existente."""
    wallet = await container.wallets.import_address(payload.address)
    return _wallet_status(wallet)


@router.post("/wallet/reveal", response_model=schemas.RevealResponse)
async def reveal_seed(
    payload: schemas.RevealRequest,
    container: ContainerDep,
) -> schemas.RevealResponse:
    """Revela a seed armazenada (exige a senha)."""
    mnemonic = await container.wallets.reveal_seed(payload.passphrase)
    return schemas.RevealResponse(mnemonic=list(mnemonic.words))


@router.post("/wallet/verify", response_model=schemas.VerifyResponse)
async def verify_seed(
    payload: schemas.VerifyRequest,
    container: ContainerDep,
) -> schemas.VerifyResponse:
    """Compara uma seed com a impressão digital gravada."""
    matches = await container.wallets.verify(Mnemonic(payload.mnemonic))
    return schemas.VerifyResponse(matches=matches)


@router.delete("/wallet", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wallet(container: ContainerDep) -> Response:
    """Remove a carteira e a seed armazenada."""
    await container.wallets.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/settings", response_model=schemas.SettingsModel)
async def get_settings(container: ContainerDep) -> schemas.SettingsModel:
    """Preferências atuais."""
    return _settings_model(await container.preferences.get())


@router.put("/settings", response_model=schemas.SettingsModel)
async def update_settings(
    payload: schemas.SettingsUpdate,
    container: ContainerDep,
) -> schemas.SettingsModel:
    """Atualiza parcialmente as preferências."""
    updated = await container.preferences.update(
        threads=payload.threads,
        worker=payload.worker,
        pool_url=payload.pool_url,
        algorithm=payload.algorithm,
    )
    return _settings_model(updated)


@router.post("/miner/start", response_model=schemas.MinerStatusModel)
async def start_miner(
    payload: schemas.StartRequest,
    container: ContainerDep,
) -> schemas.MinerStatusModel:
    """Inicia a mineração."""
    return _status_model(await container.mining.start(payload.threads))


@router.post("/miner/stop", response_model=schemas.MinerStatusModel)
async def stop_miner(container: ContainerDep) -> schemas.MinerStatusModel:
    """Para a mineração."""
    return _status_model(await container.mining.stop())


@router.get("/miner/status", response_model=schemas.MinerStatusModel)
async def miner_status(container: ContainerDep) -> schemas.MinerStatusModel:
    """Estado atual do minerador."""
    return _status_model(await container.mining.status())


@router.get("/miner/history", response_model=list[schemas.HistoryModel])
async def miner_history(
    container: ContainerDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[schemas.HistoryModel]:
    """Histórico de execução."""
    events = await container.mining.history(limit)
    return [_history_model(event) for event in events]


@router.get("/miner/logs")
async def miner_logs(request: Request, container: ContainerDep) -> StreamingResponse:
    """Streaming de logs em tempo real (Server-Sent Events)."""

    async def event_source() -> AsyncIterator[str]:
        for entry in container.mining.buffer():
            yield _sse(entry)
        async for entry in container.mining.subscribe():
            if await request.is_disconnected():
                break
            yield _sse(entry)

    return StreamingResponse(event_source(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/pool/stats", response_model=schemas.PoolStatsModel)
async def pool_stats(
    container: ContainerDep,
    refresh: bool = False,
) -> schemas.PoolStatsModel:
    """Estatísticas públicas da pool (com cache)."""
    return _pool_model(await container.pool.get(refresh=refresh))


def _wallet_status(wallet: Wallet | None) -> schemas.WalletStatus:
    if wallet is None:
        return schemas.WalletStatus(configured=False)
    return schemas.WalletStatus(
        configured=True,
        address=str(wallet.address),
        fingerprint=str(wallet.fingerprint) if wallet.fingerprint else None,
        seed_stored=wallet.seed_stored,
        network=wallet.network,
    )


def _settings_model(settings: AppSettings) -> schemas.SettingsModel:
    return schemas.SettingsModel(
        threads=settings.threads,
        worker=settings.worker,
        pool_url=settings.pool_url,
        algorithm=settings.algorithm,
    )


def _status_model(snapshot: MinerStatus) -> schemas.MinerStatusModel:
    return schemas.MinerStatusModel(
        state=snapshot.state.value,
        pid=snapshot.pid,
        threads=snapshot.threads,
        hashrate=snapshot.hashrate,
        hashrate_human=str(HashRate(snapshot.hashrate)),
        uptime_seconds=snapshot.uptime(time.time()),
        started_at=snapshot.started_at,
        last_error=snapshot.last_error,
        restarts=snapshot.restarts,
        shares=schemas.ShareStatsModel(
            accepted=snapshot.shares.accepted,
            rejected=snapshot.shares.rejected,
            stale=snapshot.shares.stale,
            best_share=snapshot.shares.best_share,
        ),
    )


def _history_model(event: HistoryEvent) -> schemas.HistoryModel:
    return schemas.HistoryModel(
        id=event.id,
        kind=event.kind,
        detail=dict(event.detail),
        created_at=event.created_at,
    )


def _pool_model(stats: PoolStats) -> schemas.PoolStatsModel:
    return schemas.PoolStatsModel(
        address=stats.address,
        found=stats.found,
        workers=stats.workers,
        shares=stats.shares,
        last_share=stats.last_share,
        best_share=stats.best_share,
        best_ever=stats.best_ever,
        hashrates=dict(stats.hashrates),
        fetched_at=stats.fetched_at,
    )


def _sse(entry: LogEntry) -> str:
    payload = {
        "timestamp": entry.timestamp,
        "stream": entry.stream,
        "message": entry.message,
    }
    return f"data: {json.dumps(payload)}\n\n"
