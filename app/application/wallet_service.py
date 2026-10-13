"""Serviço de carteira — geração, importação, validação e seed cifrada."""

from __future__ import annotations

import time

from app.application.models import GeneratedWallet
from app.application.ports import (
    Clock,
    MnemonicDeriver,
    SecretCipher,
    SecretRepository,
    WalletRepository,
)
from app.domain.errors import ValidationError, WalletNotConfiguredError
from app.domain.wallet import DerivationPath, Mnemonic, Wallet, WalletAddress

#: Nome do segredo (seed) no repositório de segredos cifrados.
SEED_SECRET_NAME = "seed"


class WalletService:
    """Casos de uso de carteira.

    A seed **nunca** é persistida em claro. Quando o usuário opta por guardá-la,
    ela é cifrada (AES-GCM) com uma senha escolhida por ele; caso contrário,
    apenas o endereço público e a impressão digital são gravados.
    """

    def __init__(
        self,
        deriver: MnemonicDeriver,
        wallets: WalletRepository,
        secrets: SecretRepository,
        cipher: SecretCipher,
        clock: Clock = time.time,
    ) -> None:
        self._deriver = deriver
        self._wallets = wallets
        self._secrets = secrets
        self._cipher = cipher
        self._clock = clock

    async def get_wallet(self) -> Wallet | None:
        """Carteira configurada, ou ``None``."""
        return await self._wallets.get()

    async def require_wallet(self) -> Wallet:
        """Carteira configurada ou :class:`WalletNotConfiguredError`."""
        wallet = await self._wallets.get()
        if wallet is None:
            raise WalletNotConfiguredError("configure ou importe uma carteira antes de continuar")
        return wallet

    async def generate(self, words: int = 12) -> GeneratedWallet:
        """Gera uma nova seed BIP-39 (sem persistir nada)."""
        mnemonic = self._deriver.generate(words)
        return self._describe(mnemonic)

    async def confirm(
        self,
        mnemonic: Mnemonic,
        store_seed: bool = False,
        passphrase: str | None = None,
    ) -> Wallet:
        """Persiste a carteira derivada de ``mnemonic`` após confirmação do usuário."""
        self._deriver.validate(mnemonic)
        generated = self._describe(mnemonic)
        wallet = Wallet(
            address=generated.address,
            created_at=self._clock(),
            fingerprint=generated.fingerprint,
            seed_stored=store_seed,
        )
        await self._wallets.save(wallet)
        if store_seed:
            await self._store_seed(mnemonic, passphrase)
        else:
            await self._secrets.delete(SEED_SECRET_NAME)
        return wallet

    async def import_seed(
        self,
        mnemonic: Mnemonic,
        store_seed: bool = False,
        passphrase: str | None = None,
    ) -> Wallet:
        """Importa uma seed existente (equivalente a ``confirm``, com validação)."""
        return await self.confirm(mnemonic, store_seed=store_seed, passphrase=passphrase)

    async def import_address(self, address: str) -> Wallet:
        """Importa apenas um endereço público (sem seed)."""
        wallet = Wallet(address=WalletAddress(address), created_at=self._clock())
        await self._wallets.save(wallet)
        await self._secrets.delete(SEED_SECRET_NAME)
        return wallet

    async def reveal_seed(self, passphrase: str) -> Mnemonic:
        """Descriptografa a seed previamente armazenada."""
        token = await self._secrets.get(SEED_SECRET_NAME)
        if token is None:
            raise WalletNotConfiguredError("nenhuma seed foi armazenada nesta instalação")
        return Mnemonic(self._cipher.decrypt(passphrase, token))

    async def verify(self, mnemonic: Mnemonic) -> bool:
        """Confere se a seed informada corresponde à impressão digital gravada."""
        self._deriver.validate(mnemonic)
        wallet = await self.require_wallet()
        if wallet.fingerprint is None:
            return False
        return self._deriver.fingerprint(mnemonic) == wallet.fingerprint

    async def clear(self) -> None:
        """Remove a carteira e a seed armazenada."""
        await self._secrets.delete(SEED_SECRET_NAME)
        await self._wallets.clear()

    def _describe(self, mnemonic: Mnemonic) -> GeneratedWallet:
        path = DerivationPath()
        return GeneratedWallet(
            mnemonic=mnemonic,
            address=self._deriver.derive_address(mnemonic, path),
            fingerprint=self._deriver.fingerprint(mnemonic),
            path=str(path),
        )

    async def _store_seed(self, mnemonic: Mnemonic, passphrase: str | None) -> None:
        if not passphrase:
            raise ValidationError("informe uma senha para armazenar a seed com segurança")
        token = self._cipher.encrypt(passphrase, str(mnemonic))
        await self._secrets.set(SEED_SECRET_NAME, token)
