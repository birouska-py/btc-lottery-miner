"""Derivação de carteiras BIP-39 / BIP-84 (Native SegWit) — 100% offline."""

from __future__ import annotations

import hashlib

from bip_utils import (
    Bip39MnemonicGenerator,
    Bip39MnemonicValidator,
    Bip39SeedGenerator,
    Bip39WordsNum,
    Bip44Changes,
    Bip84,
    Bip84Coins,
)

from app.domain.errors import InvalidMnemonicError
from app.domain.wallet import DerivationPath, Fingerprint, Mnemonic, WalletAddress

_WORDS_TO_ENUM: dict[int, Bip39WordsNum] = {
    12: Bip39WordsNum.WORDS_NUM_12,
    15: Bip39WordsNum.WORDS_NUM_15,
    18: Bip39WordsNum.WORDS_NUM_18,
    21: Bip39WordsNum.WORDS_NUM_21,
    24: Bip39WordsNum.WORDS_NUM_24,
}


class Bip84Deriver:
    """Implementa as operações de carteira usando as bibliotecas ``mnemonic``/``bip_utils``."""

    def generate(self, words: int = 12) -> Mnemonic:
        """Gera uma nova seed BIP-39 com a quantidade de palavras pedida."""
        words_num = _WORDS_TO_ENUM.get(words)
        if words_num is None:
            raise InvalidMnemonicError(f"quantidade de palavras inválida: {words}")
        return Mnemonic(str(Bip39MnemonicGenerator().FromWordsNumber(words_num)))

    def validate(self, mnemonic: Mnemonic) -> None:
        """Valida o *checksum* da seed; levanta :class:`InvalidMnemonicError` se inválida."""
        if not Bip39MnemonicValidator().IsValid(str(mnemonic)):
            raise InvalidMnemonicError("checksum da seed BIP-39 inválido")

    def derive_address(
        self,
        mnemonic: Mnemonic,
        path: DerivationPath,
        passphrase: str = "",
    ) -> WalletAddress:
        """Deriva o endereço P2WPKH (``bc1q...``) no caminho BIP-84 informado."""
        seed = Bip39SeedGenerator(str(mnemonic)).Generate(passphrase)
        bip84 = Bip84.FromSeed(seed, Bip84Coins.BITCOIN)
        change = Bip44Changes.CHAIN_EXT if path.change == 0 else Bip44Changes.CHAIN_INT
        node = (
            bip84.Purpose()
            .Coin()
            .Account(path.account)
            .Change(change)
            .AddressIndex(path.index)
        )
        return WalletAddress(node.PublicKey().ToAddress())

    def fingerprint(self, mnemonic: Mnemonic) -> Fingerprint:
        """Hash de validação da seed (permite conferir sem revelar a frase)."""
        digest = hashlib.sha256(str(mnemonic).encode("utf-8")).hexdigest()
        return Fingerprint(digest)
