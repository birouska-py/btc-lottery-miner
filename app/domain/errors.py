"""Erros de domínio.

Todos os erros esperados da aplicação herdam de :class:`DomainError`, o que permite
tratá-los de forma uniforme na borda HTTP sem vazar detalhes de infraestrutura.
"""

from __future__ import annotations


class DomainError(Exception):
    """Erro base de domínio."""


class ValidationError(DomainError):
    """Entrada inválida segundo as regras de domínio."""


class InvalidMnemonicError(ValidationError):
    """A frase-semente (BIP-39) é inválida."""


class InvalidAddressError(ValidationError):
    """O endereço Bitcoin (bech32 P2WPKH) é inválido."""


class InvalidFingerprintError(ValidationError):
    """A impressão digital (hash de validação) é inválida."""


class WalletNotConfiguredError(DomainError):
    """Nenhuma carteira foi configurada ainda."""


class WalletAlreadyConfiguredError(DomainError):
    """Já existe uma carteira configurada."""


class MinerError(DomainError):
    """Erro genérico no minerador."""


class MinerAlreadyRunningError(MinerError):
    """O minerador já está em execução."""


class MinerNotRunningError(MinerError):
    """O minerador não está em execução."""


class PoolError(DomainError):
    """Erro ao consultar a pool."""


class PoolNotFoundError(PoolError):
    """Endereço ainda não visto pela pool (sem shares)."""


class CryptoError(DomainError):
    """Erro na camada criptográfica."""


class DecryptionError(CryptoError):
    """Falha ao descriptografar — chave incorreta ou dado corrompido."""
