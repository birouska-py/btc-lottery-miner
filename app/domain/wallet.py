"""Carteira — value objects e entidade (BIP-39 / BIP-84).

A camada de domínio valida *forma* (quantidade de palavras, charset bech32,
formato do hash) mas **não** faz criptografia nem derivação de chaves — isso é
responsabilidade da infraestrutura, atrás das portas de aplicação.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.errors import (
    InvalidAddressError,
    InvalidFingerprintError,
    InvalidMnemonicError,
)

#: Quantidades de palavras aceitas pelo BIP-39.
VALID_WORD_COUNTS: frozenset[int] = frozenset({12, 15, 18, 21, 24})

#: Caminho de derivação padrão BIP-84 (Native SegWit).
DEFAULT_PURPOSE = 84
MAINNET_COIN_TYPE = 0

_WORD_RE = re.compile(r"^[a-z]+$")
# bech32 P2WPKH: HRP "bc" + separador "1" + versão de witness "q" + 38 caracteres.
_ADDRESS_RE = re.compile(r"^bc1q[qpzry9x8gf2tvdw0s3jn54khce6mua7l]{38}$")
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class Mnemonic:
    """Frase-semente BIP-39 normalizada (minúsculas, espaços simples).

    A validação de *checksum* (dicionário BIP-39) é feita pela infraestrutura; aqui
    validamos apenas a forma para manter o domínio livre de dependências externas.
    """

    phrase: str

    def __post_init__(self) -> None:
        normalized = " ".join(self.phrase.split()).lower()
        words = normalized.split(" ")
        if len(words) not in VALID_WORD_COUNTS:
            raise InvalidMnemonicError(
                f"a seed deve ter uma das quantidades {sorted(VALID_WORD_COUNTS)} de palavras"
            )
        if any(not _WORD_RE.match(word) for word in words):
            raise InvalidMnemonicError("a seed contém palavras inválidas")
        object.__setattr__(self, "phrase", normalized)

    @property
    def words(self) -> tuple[str, ...]:
        """Palavras da seed, na ordem."""
        return tuple(self.phrase.split(" "))

    @property
    def word_count(self) -> int:
        """Quantidade de palavras."""
        return len(self.words)

    def __str__(self) -> str:
        return self.phrase


@dataclass(frozen=True, slots=True)
class WalletAddress:
    """Endereço público Native SegWit (``bc1q...``)."""

    value: str

    def __post_init__(self) -> None:
        candidate = self.value.strip()
        if not _ADDRESS_RE.match(candidate):
            raise InvalidAddressError("endereço inválido: esperado bech32 P2WPKH (bc1q...)")
        object.__setattr__(self, "value", candidate)

    @property
    def short(self) -> str:
        """Versão abreviada para exibição."""
        return f"{self.value[:8]}…{self.value[-6:]}"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Fingerprint:
    """Hash SHA-256 (hex) usado para validar uma seed sem revelá-la."""

    value: str

    def __post_init__(self) -> None:
        candidate = self.value.strip().lower()
        if not _FINGERPRINT_RE.match(candidate):
            raise InvalidFingerprintError("impressão digital inválida: esperado sha256 em hex")
        object.__setattr__(self, "value", candidate)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DerivationPath:
    """Caminho de derivação BIP-84 (``m/84'/0'/0'/0/0``)."""

    account: int = 0
    change: int = 0
    index: int = 0
    coin_type: int = MAINNET_COIN_TYPE
    purpose: int = DEFAULT_PURPOSE

    def __post_init__(self) -> None:
        if min(self.account, self.change, self.index, self.coin_type, self.purpose) < 0:
            raise InvalidAddressError("caminho de derivação não pode conter valores negativos")
        if self.change not in (0, 1):
            raise InvalidAddressError("'change' deve ser 0 (externo) ou 1 (troco)")

    def __str__(self) -> str:
        return (
            f"m/{self.purpose}'/{self.coin_type}'/{self.account}'/{self.change}/{self.index}"
        )


@dataclass(frozen=True, slots=True)
class Wallet:
    """Carteira configurada — apenas dados públicos são persistidos em claro."""

    address: WalletAddress
    created_at: float
    fingerprint: Fingerprint | None = None
    seed_stored: bool = False

    @property
    def network(self) -> str:
        """Rede da carteira."""
        return "mainnet"
