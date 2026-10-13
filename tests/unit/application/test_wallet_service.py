"""Testes do serviço de carteira."""

from __future__ import annotations

import pytest

from app.application.wallet_service import WalletService
from app.domain.errors import (
    DecryptionError,
    InvalidAddressError,
    InvalidMnemonicError,
    ValidationError,
    WalletNotConfiguredError,
)
from app.domain.wallet import Mnemonic
from app.infrastructure.crypto import PassphraseCipher, Pbkdf2KeyDeriver
from app.infrastructure.wallet_deriver import Bip84Deriver
from tests.conftest import BIP84_ADDRESS, BIP84_MNEMONIC
from tests.fakes import MemorySecretRepository, MemoryWalletRepository


def make_service() -> WalletService:
    return WalletService(
        deriver=Bip84Deriver(),
        wallets=MemoryWalletRepository(),
        secrets=MemorySecretRepository(),
        cipher=PassphraseCipher(Pbkdf2KeyDeriver(iterations=200)),
        clock=lambda: 100.0,
    )


async def test_generate_does_not_persist() -> None:
    service = make_service()
    generated = await service.generate(12)
    assert generated.mnemonic.word_count == 12
    assert str(generated.address).startswith("bc1q")
    assert generated.path == "m/84'/0'/0'/0/0"
    assert await service.get_wallet() is None


async def test_require_wallet_raises_when_absent() -> None:
    with pytest.raises(WalletNotConfiguredError):
        await make_service().require_wallet()


async def test_confirm_persists_public_data() -> None:
    service = make_service()
    wallet = await service.confirm(Mnemonic(BIP84_MNEMONIC))
    assert str(wallet.address) == BIP84_ADDRESS
    assert wallet.fingerprint is not None
    assert wallet.seed_stored is False
    assert await service.get_wallet() == wallet


async def test_store_seed_requires_passphrase() -> None:
    service = make_service()
    with pytest.raises(ValidationError):
        await service.confirm(Mnemonic(BIP84_MNEMONIC), store_seed=True)


async def test_store_and_reveal_seed() -> None:
    service = make_service()
    wallet = await service.confirm(Mnemonic(BIP84_MNEMONIC), store_seed=True, passphrase="s3nh4")
    assert wallet.seed_stored is True

    revealed = await service.reveal_seed("s3nh4")
    assert str(revealed) == BIP84_MNEMONIC

    with pytest.raises(DecryptionError):
        await service.reveal_seed("errada")


async def test_reveal_without_stored_seed() -> None:
    with pytest.raises(WalletNotConfiguredError):
        await make_service().reveal_seed("qualquer")


async def test_import_address_only() -> None:
    service = make_service()
    wallet = await service.import_address(f"  {BIP84_ADDRESS} ")
    assert str(wallet.address) == BIP84_ADDRESS
    assert wallet.fingerprint is None
    assert wallet.seed_stored is False

    with pytest.raises(InvalidAddressError):
        await service.import_address("nope")


async def test_import_seed_validates_checksum() -> None:
    service = make_service()
    wallet = await service.import_seed(Mnemonic(BIP84_MNEMONIC))
    assert str(wallet.address) == BIP84_ADDRESS

    with pytest.raises(InvalidMnemonicError):
        await service.import_seed(Mnemonic(" ".join(["abandon"] * 12)))


async def test_verify_matches_and_mismatches() -> None:
    service = make_service()
    await service.confirm(Mnemonic(BIP84_MNEMONIC))
    assert await service.verify(Mnemonic(BIP84_MNEMONIC)) is True
    assert await service.verify(Bip84Deriver().generate()) is False


async def test_verify_without_fingerprint_returns_false() -> None:
    service = make_service()
    await service.import_address(BIP84_ADDRESS)
    assert await service.verify(Mnemonic(BIP84_MNEMONIC)) is False


async def test_clear_removes_wallet_and_seed() -> None:
    service = make_service()
    await service.confirm(Mnemonic(BIP84_MNEMONIC), store_seed=True, passphrase="p")
    await service.clear()
    assert await service.get_wallet() is None
    with pytest.raises(WalletNotConfiguredError):
        await service.reveal_seed("p")


async def test_confirm_without_store_removes_previous_seed() -> None:
    service = make_service()
    await service.confirm(Mnemonic(BIP84_MNEMONIC), store_seed=True, passphrase="p")
    await service.confirm(Mnemonic(BIP84_MNEMONIC))
    with pytest.raises(WalletNotConfiguredError):
        await service.reveal_seed("p")
