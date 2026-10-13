"""Testes do domínio de mineração."""

from __future__ import annotations

import math

import pytest

from app.domain.errors import ValidationError
from app.domain.mining import (
    HashRate,
    LogEntry,
    MinerState,
    MinerStatus,
    MiningConfig,
    ShareStats,
    validate_pool_url,
    validate_worker,
)
from tests.conftest import BIP84_ADDRESS


def test_hashrate_parse_variants() -> None:
    assert HashRate.parse("1.5 kH/s") == HashRate(1500.0)
    assert HashRate.parse("2 MH/s") == HashRate(2_000_000.0)
    assert HashRate.parse("no hashrate here") is None
    assert HashRate.parse("accepted: 1/2 (50.0%), 3.5 Gh/s") == HashRate(3_500_000_000.0)
    cpuminer_line = "[2026-10-13 00:25:25] thread 0: 2097152 hashes, 8393 khash/s"
    assert HashRate.parse(cpuminer_line) == HashRate(8_393_000.0)


def test_hashrate_rejects_negative_and_infinite() -> None:
    with pytest.raises(ValidationError):
        HashRate(-1.0)
    with pytest.raises(ValidationError):
        HashRate(math.inf)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, "0.00 H/s"),
        (1500.0, "1.50 kH/s"),
        (2_500_000.0, "2.50 MH/s"),
        (3_000_000_000.0, "3.00 GH/s"),
        (4_000_000_000_000.0, "4.00 TH/s"),
        (1e15, "1.00 PH/s"),
        (1e18, "1000.00 PH/s"),
    ],
)
def test_hashrate_str(value: float, expected: str) -> None:
    assert str(HashRate(value)) == expected


def test_mining_config_valid_and_command() -> None:
    config = MiningConfig(address=BIP84_ADDRESS, worker="solo", threads=4, pool_url="stratum+tcp://solo.ckpool.org:3333")
    assert config.username == f"{BIP84_ADDRESS}.solo"
    assert config.as_command("cpuminer") == [
        "cpuminer",
        "-a",
        "sha256d",
        "-o",
        "stratum+tcp://solo.ckpool.org:3333",
        "-u",
        f"{BIP84_ADDRESS}.solo",
        "-p",
        "x",
        "-t",
        "4",
    ]


def test_mining_config_rejects_bad_worker() -> None:
    with pytest.raises(ValidationError):
        MiningConfig(address=BIP84_ADDRESS, worker="a b", threads=1, pool_url="stratum+tcp://x:1")


def test_mining_config_rejects_bad_threads() -> None:
    with pytest.raises(ValidationError):
        MiningConfig(address=BIP84_ADDRESS, worker="solo", threads=0, pool_url="stratum+tcp://x:1")


def test_mining_config_rejects_bad_pool_url() -> None:
    with pytest.raises(ValidationError):
        MiningConfig(address=BIP84_ADDRESS, worker="solo", threads=1, pool_url="http://x")


def test_mining_config_rejects_empty_algorithm() -> None:
    with pytest.raises(ValidationError):
        MiningConfig(
            address=BIP84_ADDRESS,
            worker="solo",
            threads=1,
            pool_url="stratum+tcp://x:1",
            algorithm="",
        )


def test_mining_config_rejects_bad_address() -> None:
    with pytest.raises(ValidationError):
        MiningConfig(address="nope", worker="solo", threads=1, pool_url="stratum+tcp://x:1")


def test_validate_helpers() -> None:
    validate_worker("solo-1")
    validate_pool_url("stratum+ssl://pool:3333")
    with pytest.raises(ValidationError):
        validate_worker("!!")
    with pytest.raises(ValidationError):
        validate_pool_url("ftp://pool")


def test_share_stats_and_log_entry_defaults() -> None:
    stats = ShareStats()
    assert stats.accepted == 0 and stats.rejected == 0 and stats.stale == 0
    entry = LogEntry(timestamp=1.0, stream="stdout", message="oi")
    assert entry.message == "oi"


def test_miner_status_uptime() -> None:
    running = MinerStatus(state=MinerState.RUNNING, started_at=100.0)
    assert running.uptime(130.0) == 30.0
    stopped = MinerStatus(state=MinerState.STOPPED, started_at=100.0)
    assert stopped.uptime(130.0) == 0.0
    assert MinerStatus(state=MinerState.RUNNING).uptime(130.0) == 0.0
