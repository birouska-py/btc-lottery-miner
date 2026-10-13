"""Testes da criptografia em repouso."""

from __future__ import annotations

import base64
import os

import pytest

from app.domain.errors import CryptoError, DecryptionError
from app.infrastructure.crypto import (
    Argon2KeyDeriver,
    Argon2Params,
    PassphraseCipher,
    Pbkdf2KeyDeriver,
)


@pytest.fixture
def fast_cipher() -> PassphraseCipher:
    return PassphraseCipher(Pbkdf2KeyDeriver(iterations=200))


def test_roundtrip(fast_cipher: PassphraseCipher) -> None:
    token = fast_cipher.encrypt("senha-forte", "abandon abandon about")
    assert token != "abandon abandon about"
    assert fast_cipher.decrypt("senha-forte", token) == "abandon abandon about"


def test_two_encryptions_differ(fast_cipher: PassphraseCipher) -> None:
    assert fast_cipher.encrypt("s", "x") != fast_cipher.encrypt("s", "x")


def test_wrong_passphrase(fast_cipher: PassphraseCipher) -> None:
    token = fast_cipher.encrypt("certa", "segredo")
    with pytest.raises(DecryptionError):
        fast_cipher.decrypt("errada", token)


def test_tampered_token(fast_cipher: PassphraseCipher) -> None:
    token = fast_cipher.encrypt("s", "segredo")
    raw = bytearray(base64.urlsafe_b64decode(token))
    raw[-1] ^= 0x01
    tampered = base64.urlsafe_b64encode(bytes(raw)).decode()
    with pytest.raises(DecryptionError):
        fast_cipher.decrypt("s", tampered)


def test_encrypt_empty_secret(fast_cipher: PassphraseCipher) -> None:
    with pytest.raises(CryptoError):
        fast_cipher.encrypt("", "x")


def test_decrypt_empty_secret(fast_cipher: PassphraseCipher) -> None:
    with pytest.raises(DecryptionError):
        fast_cipher.decrypt("", "qualquer")


def test_decrypt_invalid_base64(fast_cipher: PassphraseCipher) -> None:
    with pytest.raises(DecryptionError):
        fast_cipher.decrypt("s", "***não-é-base64***")


def test_decrypt_short_token(fast_cipher: PassphraseCipher) -> None:
    token = base64.urlsafe_b64encode(b"\x01\x02\x03").decode()
    with pytest.raises(DecryptionError):
        fast_cipher.decrypt("s", token)


def test_decrypt_wrong_version(fast_cipher: PassphraseCipher) -> None:
    raw = bytes([99]) + os.urandom(16) + os.urandom(12) + os.urandom(32)
    token = base64.urlsafe_b64encode(raw).decode()
    with pytest.raises(DecryptionError):
        fast_cipher.decrypt("s", token)


def test_argon2_deriver_is_deterministic() -> None:
    deriver = Argon2KeyDeriver(Argon2Params(time_cost=1, memory_cost=8, parallelism=1))
    first = deriver.derive("senha", b"0123456789abcdef")
    second = deriver.derive("senha", b"0123456789abcdef")
    assert first == second
    assert len(first) == 32
    assert first != deriver.derive("outra", b"0123456789abcdef")


def test_pbkdf2_deriver() -> None:
    deriver = Pbkdf2KeyDeriver(iterations=100)
    assert len(deriver.derive("senha", b"salt")) == 32
    assert deriver.derive("senha", b"salt") != deriver.derive("senha", b"other")
