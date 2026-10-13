"""Testes do serviço de mineração."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.application.mining_service import MiningService
from app.application.models import AppSettings
from app.application.settings_service import SettingsService
from app.application.wallet_service import WalletService
from app.domain.errors import MinerNotRunningError, WalletNotConfiguredError
from app.domain.mining import LogEntry, MinerState
from app.domain.wallet import Mnemonic
from app.infrastructure.crypto import PassphraseCipher, Pbkdf2KeyDeriver
from app.infrastructure.wallet_deriver import Bip84Deriver
from tests.conftest import BIP84_ADDRESS, BIP84_MNEMONIC
from tests.fakes import (
    FakeMinerProcess,
    MemoryHistoryRepository,
    MemorySecretRepository,
    MemorySettingsRepository,
    MemoryWalletRepository,
)

DEFAULTS = AppSettings(
    threads=2,
    worker="solo",
    pool_url="stratum+tcp://solo.ckpool.org:3333",
    algorithm="sha256d",
)


@dataclass
class Wiring:
    """Dependências montadas para os testes."""

    mining: MiningService
    wallets: WalletService
    history: MemoryHistoryRepository
    process: FakeMinerProcess


def make_service() -> Wiring:
    wallets = WalletService(
        deriver=Bip84Deriver(),
        wallets=MemoryWalletRepository(),
        secrets=MemorySecretRepository(),
        cipher=PassphraseCipher(Pbkdf2KeyDeriver(iterations=200)),
        clock=lambda: 1.0,
    )
    settings = SettingsService(MemorySettingsRepository(), DEFAULTS, max_threads=8)
    history = MemoryHistoryRepository()
    process = FakeMinerProcess()
    mining = MiningService(process, wallets, settings, history, clock=lambda: 55.0)
    return Wiring(mining=mining, wallets=wallets, history=history, process=process)


async def test_start_requires_wallet() -> None:
    with pytest.raises(WalletNotConfiguredError):
        await make_service().mining.start()


async def test_start_builds_config_and_records_history() -> None:
    wiring = make_service()
    await wiring.wallets.confirm(Mnemonic(BIP84_MNEMONIC))

    status = await wiring.mining.start()
    assert status.state is MinerState.RUNNING
    assert wiring.process.started_configs[0].address == BIP84_ADDRESS
    assert wiring.process.started_configs[0].threads == 2
    assert [event.kind for event in wiring.history.events] == ["start"]
    assert wiring.history.events[0].created_at == 55.0


async def test_start_with_threads_updates_preferences() -> None:
    wiring = make_service()
    await wiring.wallets.confirm(Mnemonic(BIP84_MNEMONIC))

    await wiring.mining.start(threads=6)
    assert wiring.process.started_configs[0].threads == 6


async def test_stop_records_history() -> None:
    wiring = make_service()
    await wiring.wallets.confirm(Mnemonic(BIP84_MNEMONIC))
    await wiring.mining.start()

    status = await wiring.mining.stop()
    assert status.state is MinerState.STOPPED
    assert [event.kind for event in wiring.history.events] == ["start", "stop"]


async def test_stop_when_not_running_propagates() -> None:
    with pytest.raises(MinerNotRunningError):
        await make_service().mining.stop()


async def test_status_history_buffer_and_subscribe_delegate() -> None:
    wiring = make_service()
    await wiring.wallets.confirm(Mnemonic(BIP84_MNEMONIC))
    await wiring.mining.start()
    wiring.process.push(LogEntry(timestamp=1.0, stream="stdout", message="oi"))

    assert (await wiring.mining.status()).state is MinerState.RUNNING
    assert len(await wiring.mining.history(limit=10)) == 1
    assert wiring.mining.buffer()[-1].message == "oi"

    stream = wiring.mining.subscribe()
    await stream.aclose()
