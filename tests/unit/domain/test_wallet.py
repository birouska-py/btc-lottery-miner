"""Testes do domínio de carteira."""

from __future__ import annotations

import pytest

from app.domain.errors import (
    InvalidAddressError,
    InvalidFingerprintError,
    InvalidMnemonicError,
)
from app.domain.wallet import DerivationPath, Fingerprint, Mnemonic, Wallet, WalletAddress
from tests.conftest import BIP84_ADDRESS, BIP84_MNEMONIC


def test_mnemonic_normalizes_whitespace_and_case() -> None:
    mnemonic = Mnemonic("  Abandon ABANDON abandon abandon abandon abandon "
                        "abandon abandon abandon abandon abandon About ")
    assert mnemonic.phrase == BIP84_MNEMONIC
    assert mnemonic.word_count == 12
    assert mnemonic.words[0] == "abandon"
    assert str(mnemonic) == BIP84_MNEMONIC


@pytest.mark.parametrize("phrase", ["abandon about", "", "abandon " * 13])
def test_mnemonic_rejects_invalid_word_count(phrase: str) -> None:
    with pytest.raises(InvalidMnemonicError):
        Mnemonic(phrase)


def test_mnemonic_rejects_non_alpha_words() -> None:
    phrase = " ".join(["abandon"] * 11 + ["4bout"])
    with pytest.raises(InvalidMnemonicError):
        Mnemonic(phrase)


def test_wallet_address_valid_and_short() -> None:
    address = WalletAddress(f"  {BIP84_ADDRESS}  ")
    assert str(address) == BIP84_ADDRESS
    assert address.short.startswith("bc1qcr8t")
    assert address.short.endswith("306fyu")


@pytest.mark.parametrize(
    "value",
    [
        "",
        "BC1QCR8TE4KR609GCAWUTMRZA0J4XV80JY8Z306FYU",
        "bc1qinvalid",
        "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
    ],
)
def test_wallet_address_rejects_invalid(value: str) -> None:
    with pytest.raises(InvalidAddressError):
        WalletAddress(value)


def test_fingerprint_normalizes_case() -> None:
    fingerprint = Fingerprint("A" * 64)
    assert str(fingerprint) == "a" * 64


def test_fingerprint_rejects_invalid() -> None:
    with pytest.raises(InvalidFingerprintError):
        Fingerprint("xyz")


def test_derivation_path_defaults_and_string() -> None:
    assert str(DerivationPath()) == "m/84'/0'/0'/0/0"
    assert str(DerivationPath(account=1, change=1, index=7)) == "m/84'/0'/1'/1/7"


def test_derivation_path_rejects_negative_and_bad_change() -> None:
    with pytest.raises(InvalidAddressError):
        DerivationPath(account=-1)
    with pytest.raises(InvalidAddressError):
        DerivationPath(change=2)


def test_wallet_entity_network() -> None:
    wallet = Wallet(address=WalletAddress(BIP84_ADDRESS), created_at=1.0)
    assert wallet.network == "mainnet"
    assert wallet.fingerprint is None
    assert wallet.seed_stored is False
