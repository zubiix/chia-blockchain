import time
import logging
import clvm
from typing import Dict, Optional, List, Any, Set
from src.types.BLSSignature import BLSSignature
from src.types.coin import Coin
from src.types.coin_solution import CoinSolution
from src.types.program import Program
from src.types.spend_bundle import SpendBundle
from src.types.sized_bytes import bytes32
from src.util.ints import uint64, uint32
from src.wallet.BLSPrivateKey import BLSPrivateKey
from src.wallet.ap_wallet.ap_info import APInfo
from src.wallet.transaction_record import TransactionRecord
from src.wallet.util.wallet_types import WalletType
from src.wallet.wallet import Wallet
from src.wallet.wallet_coin_record import WalletCoinRecord
from src.wallet.wallet_info import WalletInfo
from src.wallet.derivation_record import DerivationRecord
from src.util.byte_types import hexstr_to_bytes
from src.wallet.ap_wallet import ap_puzzles
from src.wallet.ap_wallet import AuthoriserInfo
from blspy import PublicKey
from src.util.hash import std_hash


class AuthoriserWallet:
    wallet_state_manager: Any
    log: logging.Logger
    wallet_info: WalletInfo
    authoriser_info: AuthoriserInfo
    standard_wallet: Wallet

    @staticmethod
    async def create_wallet_for_ap(
        wallet_state_manager: Any,
        wallet: Wallet,
        authoriser_pubkey: PublicKey,
        name: str = None,
    ):

        self = AuthoriserWallet()
        self.base_puzzle_program = None
        self.base_inner_puzzle_hash = None
        self.standard_wallet = wallet
        if name:
            self.log = logging.getLogger(name)
        else:
            self.log = logging.getLogger(__name__)

        self.wallet_state_manager = wallet_state_manager
        self.authoriser_info = AuthoriserInfo(None)
        info_as_string = bytes(self.auth_info).hex()
        self.wallet_info = await wallet_state_manager.user_store.create_wallet(
            "Authoriser Wallet", WalletType.AUTHORIZER, info_as_string
        )
        if self.wallet_info is None:
            raise
        await self.wallet_state_manager.add_new_wallet(self, self.wallet_info.id)
        return self

    @staticmethod
    async def create(
        wallet_state_manager: Any,
        wallet: Wallet,
        wallet_info: WalletInfo,
        name: str = None,
    ):
        self = AuthoriserWallet()

        if name:
            self.log = logging.getLogger(name)
        else:
            self.log = logging.getLogger(__name__)

        self.wallet_state_manager = wallet_state_manager
        self.wallet_info = wallet_info
        self.standard_wallet = wallet
        self.cc_info = APInfo.from_bytes(hexstr_to_bytes(self.wallet_info.data))
        self.base_puzzle_program = None
        self.base_inner_puzzle_hash = None
        return self
