"""Ponto de entrada da aplicação FastAPI (composition root + borda HTTP)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import __version__
from app.application.ports import MinerProcess
from app.config import Settings, get_settings
from app.container import Container, build_container
from app.domain.errors import (
    CryptoError,
    DomainError,
    InvalidAddressError,
    InvalidFingerprintError,
    InvalidMnemonicError,
    MinerAlreadyRunningError,
    MinerNotRunningError,
    PoolError,
    PoolNotFoundError,
    ValidationError,
    WalletAlreadyConfiguredError,
    WalletNotConfiguredError,
)
from app.presentation.api import router as api_router

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "presentation" / "static"
TEMPLATES_DIR = BASE_DIR / "presentation" / "templates"

_STATUS_BY_ERROR: dict[type[Exception], int] = {
    ValidationError: 422,
    InvalidMnemonicError: 422,
    InvalidAddressError: 422,
    InvalidFingerprintError: 422,
    WalletNotConfiguredError: 404,
    WalletAlreadyConfiguredError: 409,
    MinerAlreadyRunningError: 409,
    MinerNotRunningError: 409,
    PoolNotFoundError: 404,
    PoolError: 502,
    CryptoError: 400,
}

_ACTIVE_STATES = {"starting", "running", "stopping"}


def _status_for(error: DomainError) -> int:
    for klass in type(error).__mro__:
        if klass in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[klass]
    return 400


async def _shutdown_miner(process: MinerProcess) -> None:
    if process.status().state.value not in _ACTIVE_STATES:
        return
    try:
        await process.stop()
    except MinerNotRunningError:
        return


def create_app(
    settings: Settings | None = None,
    container: Container | None = None,
) -> FastAPI:
    """Monta a aplicação (usado em produção e nos testes)."""
    resolved = container if container is not None else build_container(settings or get_settings())
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await resolved.database.connect()
        try:
            yield
        finally:
            await _shutdown_miner(resolved.process)
            await resolved.pool_client.aclose()
            await resolved.database.close()

    app = FastAPI(
        title="btc-lottery-miner",
        version=__version__,
        summary="Mineração de loteria solo de Bitcoin via CPU, com dashboard web.",
        lifespan=lifespan,
    )
    app.state.container = resolved

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(api_router, prefix="/api")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"version": __version__},
        )

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=_status_for(exc),
            content={"detail": str(exc), "error": type(exc).__name__},
        )

    return app


app = create_app()
