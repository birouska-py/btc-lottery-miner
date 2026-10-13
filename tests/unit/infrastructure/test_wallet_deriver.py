"""Testes da derivação BIP-39/BIP-84."""

from __future__ import annotations

import pytest

from app.domain.errors import InvalidMnemonicError
from app.domain.wallet import DerivationPath, Mnemonic
from app.infrastructure.wallet_deriver import Bip84Deriver
from tests.conftest import BIP84_ADDRESS, BIP84_MNEMONIC


def test_generate_default_and_custom_word_count() -> None:
    deriver = Bip84Deriver()
    assert deriver.generate().word_count == 12
    assert deriver.generate(24).word_count == 24


def test_generate_rejects_invalid_word_count() -> None:
    with pytest.raises(InvalidMnemonicError):
        Bip84Deriver().generate(13)


def test_validate_accepts_known_vector() -> None:
    Bip84Deriver().validate(Mnemonic(BIP84_MNEMONIC))


def test_validate_rejects_bad_checksum() -> None:
    with pytest.raises(InvalidMnemonicError):
        Bip84Deriver().validate(Mnemonic(" ".join(["abandon"] * 12)))


def test_derive_address_matches_bip84_vector() -> None:
    deriver = Bip84Deriver()
    address = deriver.derive_address(Mnemonic(BIP84_MNEMONIC), DerivationPath())
    assert str(address) == BIP84_ADDRESS


def test_derive_internal_change_chain() -> None:
    deriver = Bip84Deriver()
    address = deriver.derive_address(Mnemonic(BIP84_MNEMONIC), DerivationPath(change=1, index=3))
    assert str(address).startswith("bc1q")
    assert str(address) != BIP84_ADDRESS


def test_fingerprint_is_deterministic_and_64_hex() -> None:
    deriver = Bip84Deriver()
    first = deriver.fingerprint(Mnemonic(BIP84_MNEMONIC))
    assert first == deriver.fingerprint(Mnemonic(BIP84_MNEMONIC))
    assert len(str(first)) == 64
