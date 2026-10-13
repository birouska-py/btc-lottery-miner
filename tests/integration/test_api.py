"""Testes de integração da API (REST + SSE) via ASGI."""

from __future__ import annotations

import httpx

from app.container import Container
from app.domain.errors import MinerError, MinerNotRunningError
from app.domain.mining import LogEntry, MinerState, MinerStatus
from app.main import create_app
from app.presentation.api import miner_logs
from tests.conftest import BIP84_ADDRESS
from tests.fakes import FakeMinerProcess


async def configure_wallet(client: httpx.AsyncClient) -> str:
    """Gera e confirma uma carteira, devolvendo o endereço."""
    generated = await client.post("/api/wallet/generate", json={"words": 12})
    mnemonic = " ".join(generated.json()["mnemonic"])
    confirmed = await client.post("/api/wallet/confirm", json={"mnemonic": mnemonic})
    return confirmed.json()["address"]


async def test_index_and_static(client: httpx.AsyncClient) -> None:
    index = await client.get("/")
    assert index.status_code == 200
    assert "btc-lottery-miner" in index.text

    static = await client.get("/static/app.js")
    assert static.status_code == 200
    assert "EventSource" in static.text


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["miner_state"] == "stopped"


async def test_wallet_not_configured(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/wallet")
    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "address": None,
        "fingerprint": None,
        "seed_stored": False,
        "network": None,
    }


async def test_wallet_lifecycle(client: httpx.AsyncClient) -> None:
    generated = await client.post("/api/wallet/generate", json={"words": 12})
    assert generated.status_code == 200
    payload = generated.json()
    assert len(payload["mnemonic"]) == 12
    assert payload["path"] == "m/84'/0'/0'/0/0"
    mnemonic = " ".join(payload["mnemonic"])

    confirmed = await client.post("/api/wallet/confirm", json={"mnemonic": mnemonic})
    assert confirmed.status_code == 200
    wallet = confirmed.json()
    assert wallet["configured"] is True
    assert wallet["address"] == payload["address"]
    assert wallet["network"] == "mainnet"

    verified = await client.post("/api/wallet/verify", json={"mnemonic": mnemonic})
    assert verified.json() == {"matches": True}

    deleted = await client.delete("/api/wallet")
    assert deleted.status_code == 204
    assert (await client.get("/api/wallet")).json()["configured"] is False


async def test_generate_rejects_invalid_word_count(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/wallet/generate", json={"words": 13})
    assert response.status_code == 422


async def test_confirm_rejects_invalid_mnemonic(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/wallet/confirm", json={"mnemonic": "abandon about"})
    assert response.status_code == 422


async def test_confirm_store_seed_requires_passphrase(client: httpx.AsyncClient) -> None:
    generated = await client.post("/api/wallet/generate", json={"words": 12})
    mnemonic = " ".join(generated.json()["mnemonic"])
    response = await client.post(
        "/api/wallet/confirm",
        json={"mnemonic": mnemonic, "store_seed": True},
    )
    assert response.status_code == 422


async def test_reveal_seed_flow(client: httpx.AsyncClient) -> None:
    generated = await client.post("/api/wallet/generate", json={"words": 12})
    mnemonic = " ".join(generated.json()["mnemonic"])
    await client.post(
        "/api/wallet/confirm",
        json={"mnemonic": mnemonic, "store_seed": True, "passphrase": "segredo"},
    )

    revealed = await client.post("/api/wallet/reveal", json={"passphrase": "segredo"})
    assert revealed.status_code == 200
    assert " ".join(revealed.json()["mnemonic"]) == mnemonic

    wrong = await client.post("/api/wallet/reveal", json={"passphrase": "errada"})
    assert wrong.status_code == 400
    assert wrong.json()["error"] == "DecryptionError"


async def test_reveal_without_stored_seed(client: httpx.AsyncClient) -> None:
    await client.post("/api/wallet/import/address", json={"address": BIP84_ADDRESS})
    response = await client.post("/api/wallet/reveal", json={"passphrase": "x"})
    assert response.status_code == 404


async def test_import_address_valid_and_invalid(client: httpx.AsyncClient) -> None:
    valid = await client.post("/api/wallet/import/address", json={"address": BIP84_ADDRESS})
    assert valid.status_code == 200
    assert valid.json()["fingerprint"] is None

    invalid = await client.post("/api/wallet/import/address", json={"address": "nope"})
    assert invalid.status_code == 422
    assert invalid.json()["error"] == "InvalidAddressError"


async def test_settings_get_and_update(client: httpx.AsyncClient) -> None:
    defaults = await client.get("/api/settings")
    assert defaults.json()["threads"] == 2
    assert defaults.json()["pool_url"].startswith("stratum+tcp://")

    updated = await client.put("/api/settings", json={"threads": 5, "worker": "rig"})
    assert updated.status_code == 200
    assert updated.json()["threads"] == 5
    assert updated.json()["worker"] == "rig"

    clamped = await client.put("/api/settings", json={"threads": 999})
    assert clamped.json()["threads"] == 8

    invalid = await client.put("/api/settings", json={"worker": "a b"})
    assert invalid.status_code == 422


async def test_miner_start_requires_wallet(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/miner/start", json={})
    assert response.status_code == 404
    assert response.json()["error"] == "WalletNotConfiguredError"


async def test_miner_lifecycle(client: httpx.AsyncClient) -> None:
    await configure_wallet(client)

    started = await client.post("/api/miner/start", json={"threads": 3})
    assert started.status_code == 200
    assert started.json()["state"] == "running"
    assert started.json()["threads"] == 3
    assert started.json()["hashrate_human"] == "1.50 MH/s"

    conflict = await client.post("/api/miner/start", json={})
    assert conflict.status_code == 409

    status = await client.get("/api/miner/status")
    assert status.json()["state"] == "running"

    history = await client.get("/api/miner/history")
    assert [event["kind"] for event in history.json()] == ["start"]

    stopped = await client.post("/api/miner/stop")
    assert stopped.json()["state"] == "stopped"

    again = await client.post("/api/miner/stop")
    assert again.status_code == 409


async def test_miner_start_failure_maps_to_400(
    client: httpx.AsyncClient,
    fake_process: FakeMinerProcess,
) -> None:
    await configure_wallet(client)
    fake_process._fail_start = MinerError("binário ausente")
    response = await client.post("/api/miner/start", json={})
    assert response.status_code == 400
    assert response.json()["error"] == "MinerError"


async def test_miner_logs_sse(
    client: httpx.AsyncClient,
    fake_process: FakeMinerProcess,
) -> None:
    fake_process.push(LogEntry(timestamp=1.0, stream="stdout", message="linha antiga"))
    fake_process._stream = [LogEntry(timestamp=2.0, stream="stdout", message="linha nova")]

    response = await client.get("/api/miner/logs")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "linha antiga" in response.text
    assert "linha nova" in response.text


async def test_miner_logs_stops_when_client_disconnects(
    container: Container,
    fake_process: FakeMinerProcess,
) -> None:
    fake_process._stream = [LogEntry(timestamp=1.0, stream="stdout", message="nova")]

    class DisconnectedRequest:
        async def is_disconnected(self) -> bool:
            return True

    disconnected = DisconnectedRequest()
    response = await miner_logs(disconnected, container)  # type: ignore[arg-type]
    chunks = [chunk async for chunk in response.body_iterator]
    assert chunks == []


async def test_pool_stats(client: httpx.AsyncClient) -> None:
    missing = await client.get("/api/pool/stats")
    assert missing.status_code == 404

    await configure_wallet(client)
    stats = await client.get("/api/pool/stats")
    assert stats.status_code == 200
    body = stats.json()
    assert body["found"] is True
    assert body["workers"] == 1
    assert body["hashrates"]["hashrate1m"] == 2_000_000.0


async def test_lifespan_noop_when_stopped(container: Container) -> None:
    app = create_app(container=container)
    async with app.router.lifespan_context(app):
        pass
    assert container.pool_client.closed is True  # type: ignore[attr-defined]


async def test_lifespan_stops_running_miner(container: Container) -> None:
    fake = container.process
    assert isinstance(fake, FakeMinerProcess)
    fake._status = MinerStatus(state=MinerState.RUNNING, started_at=1.0)
    app = create_app(container=container)
    async with app.router.lifespan_context(app):
        pass
    assert container.process.status().state is MinerState.STOPPED


async def test_lifespan_ignores_not_running_error(container: Container) -> None:
    fake = container.process
    assert isinstance(fake, FakeMinerProcess)
    fake._status = MinerStatus(state=MinerState.RUNNING, started_at=1.0)
    fake.stop_error = MinerNotRunningError("já parado")
    app = create_app(container=container)
    async with app.router.lifespan_context(app):
        pass


async def test_default_domain_error_status(client: httpx.AsyncClient) -> None:
    from app.domain.errors import DomainError
    from app.main import _status_for

    assert _status_for(DomainError("generico")) == 400
