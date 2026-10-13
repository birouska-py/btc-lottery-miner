"""Objetos de transferência da camada de aplicação."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.wallet import Fingerprint, Mnemonic, WalletAddress


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Preferências do usuário persistidas no banco."""

    threads: int
    worker: str
    pool_url: str
    algorithm: str = "sha256d"
    force_ipv4: bool = False


@dataclass(frozen=True, slots=True)
class PoolPreset:
    """Pool pré-configurada oferecida na interface."""

    name: str
    url: str


@dataclass(frozen=True, slots=True)
class GeneratedWallet:
    """Resultado da geração de uma carteira — a seed só é exibida uma vez."""

    mnemonic: Mnemonic
    address: WalletAddress
    fingerprint: Fingerprint
    path: str
