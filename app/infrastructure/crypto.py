"""Criptografia em repouso.

Deriva uma chave simétrica de 256 bits a partir de um segredo (senha do usuário ou
a própria seed BIP-39) usando **Argon2id** (com *fallback* PBKDF2-HMAC-SHA256) e
cifra os dados com **AES-256-GCM** (confidencialidade + integridade autenticada).

Formato do token (base64 url-safe):

    [ versão (1B) ][ salt (16B) ][ nonce (12B) ][ ciphertext+tag (*) ]
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.domain.errors import CryptoError, DecryptionError

TOKEN_VERSION = 1
SALT_LENGTH = 16
NONCE_LENGTH = 12
KEY_LENGTH = 32


@runtime_checkable
class KeyDeriver(Protocol):
    """Deriva uma chave simétrica a partir de segredo + salt."""

    def derive(self, secret: str, salt: bytes) -> bytes: ...


@dataclass(frozen=True, slots=True)
class Argon2Params:
    """Parâmetros do Argon2id (padrão alinhado ao mínimo recomendado pelo OWASP)."""

    time_cost: int = 2
    memory_cost: int = 19_456  # KiB (~19 MiB)
    parallelism: int = 1
    hash_len: int = KEY_LENGTH


class Argon2KeyDeriver:
    """Derivação de chave com Argon2id (memory-hard)."""

    def __init__(self, params: Argon2Params | None = None) -> None:
        self._params = params or Argon2Params()

    def derive(self, secret: str, salt: bytes) -> bytes:
        """Deriva ``KEY_LENGTH`` bytes a partir de ``secret`` e ``salt``."""
        return hash_secret_raw(
            secret=secret.encode("utf-8"),
            salt=salt,
            time_cost=self._params.time_cost,
            memory_cost=self._params.memory_cost,
            parallelism=self._params.parallelism,
            hash_len=self._params.hash_len,
            type=Type.ID,
        )


class Pbkdf2KeyDeriver:
    """Derivação de chave com PBKDF2-HMAC-SHA256 (alternativa portável)."""

    def __init__(self, iterations: int = 600_000) -> None:
        self._iterations = iterations

    def derive(self, secret: str, salt: bytes) -> bytes:
        """Deriva ``KEY_LENGTH`` bytes a partir de ``secret`` e ``salt``."""
        return PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_LENGTH,
            salt=salt,
            iterations=self._iterations,
        ).derive(secret.encode("utf-8"))


class PassphraseCipher:
    """Cifra autenticada de valores (AES-256-GCM) protegida por um segredo."""

    def __init__(self, deriver: KeyDeriver | None = None) -> None:
        self._deriver = deriver or Argon2KeyDeriver()

    def encrypt(self, secret: str, plaintext: str) -> str:
        """Cifra ``plaintext`` e devolve um token autocontido (salt + nonce + ct)."""
        if not secret:
            raise CryptoError("o segredo de cifragem não pode ser vazio")
        salt = os.urandom(SALT_LENGTH)
        nonce = os.urandom(NONCE_LENGTH)
        key = self._deriver.derive(secret, salt)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.urlsafe_b64encode(
            bytes([TOKEN_VERSION]) + salt + nonce + ciphertext
        ).decode("ascii")

    def decrypt(self, secret: str, token: str) -> str:
        """Descriptografa um token; levanta :class:`DecryptionError` se inválido."""
        if not secret:
            raise DecryptionError("segredo de cifragem vazio")
        try:
            raw = base64.urlsafe_b64decode(token.encode("ascii"))
        except ValueError as exc:
            raise DecryptionError("token de cifragem inválido") from exc

        minimum = 1 + SALT_LENGTH + NONCE_LENGTH + 16
        if len(raw) < minimum or raw[0] != TOKEN_VERSION:
            raise DecryptionError("token de cifragem inválido")

        salt = raw[1 : 1 + SALT_LENGTH]
        nonce = raw[1 + SALT_LENGTH : 1 + SALT_LENGTH + NONCE_LENGTH]
        ciphertext = raw[1 + SALT_LENGTH + NONCE_LENGTH :]
        key = self._deriver.derive(secret, salt)
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")
        except (InvalidTag, ValueError) as exc:
            raise DecryptionError("senha incorreta ou dado corrompido") from exc
