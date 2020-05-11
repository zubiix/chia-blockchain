import logging
import time

import clvm
from typing import Dict, Optional, List, Any, Set
from clvm_tools import binutils
from clvm.EvalError import EvalError
from src.types.BLSSignature import BLSSignature
from src.types.coin import Coin
from src.types.coin_solution import CoinSolution
from src.types.condition_opcodes import ConditionOpcode
from src.types.program import Program
from src.types.spend_bundle import SpendBundle
from src.types.sized_bytes import bytes32
from src.util.byte_types import hexstr_to_bytes
from src.util.condition_tools import (
    conditions_dict_for_solution,
    hash_key_pairs_for_conditions_dict,
)
from src.util.ints import uint64, uint32
from src.wallet.BLSPrivateKey import BLSPrivateKey
from src.wallet.block_record import BlockRecord
from src.wallet.ap_wallet.ap_info import APInfo
from src.wallet.transaction_record import TransactionRecord
from src.wallet.util.json_util import dict_to_json_str
from src.wallet.util.wallet_types import WalletType
from src.wallet.wallet import Wallet
from src.wallet.wallet_coin_record import WalletCoinRecord
from src.wallet.wallet_info import WalletInfo
from src.wallet.derivation_record import DerivationRecord
from src.wallet.cc_wallet import cc_wallet_puzzles
from clvm import run_program


class APWallet:
    wallet_state_manager: Any
    log: logging.Logger
    wallet_info: WalletInfo
    cc_coin_record: WalletCoinRecord
    ap_info: APInfo
    standard_wallet: Wallet
    base_puzzle_program: Optional[bytes]
    base_inner_puzzle_hash: Optional[bytes32]

    @staticmethod
    async def create_wallet_for_ap(
        wallet_state_manager: Any, wallet: Wallet, name: str = None
    ):

        self = APWallet()
        self.base_puzzle_program = None
        self.base_inner_puzzle_hash = None
        self.standard_wallet = wallet
        if name:
            self.log = logging.getLogger(name)
        else:
            self.log = logging.getLogger(__name__)

        self.wallet_state_manager = wallet_state_manager

        self.ap_info = APInfo([], None)
        info_as_string = bytes(self.cc_info).hex()
        self.wallet_info = await wallet_state_manager.user_store.create_wallet(
            "CC Wallet", WalletType.COLOURED_COIN, info_as_string
        )
        if self.wallet_info is None:
            raise

        await self.wallet_state_manager.add_new_wallet(self, self.wallet_info.id)
        return self

    async def get_confirmed_balance(self) -> uint64:
        record_list: Set[
            WalletCoinRecord
        ] = await self.wallet_state_manager.wallet_store.get_unspent_coins_for_wallet(
            self.wallet_info.id
        )

        amount: uint64 = uint64(0)
        for record in record_list:
            parent = await self.get_parent_for_coin(record.coin)
            if parent is not None:
                amount = uint64(amount + record.coin.amount)

        self.log.info(f"Confirmed balance for ap wallet is {amount}")
        return uint64(amount)

    async def get_unconfirmed_balance(self) -> uint64:
        confirmed = await self.get_confirmed_balance()
        unconfirmed_tx: List[
            TransactionRecord
        ] = await self.wallet_state_manager.tx_store.get_unconfirmed_for_wallet(
            self.wallet_info.id
        )
        addition_amount = 0
        removal_amount = 0

        for record in unconfirmed_tx:
            if record.incoming:
                addition_amount += record.amount
            else:
                removal_amount += record.amount

        result = confirmed - removal_amount + addition_amount

        self.log.info(f"Unconfirmed balance for ap wallet is {result}")
        return uint64(result)

    def puzzle_for_pk(self, pubkey) -> Program:
        inner_puzzle_hash = self.standard_wallet.puzzle_for_pk(
            bytes(pubkey)
        ).get_tree_hash()
        if self.base_puzzle_program is None:
            cc_puzzle: Program = cc_wallet_puzzles.cc_make_puzzle(
                inner_puzzle_hash, self.cc_info.my_core
            )
            self.base_puzzle_program = bytes(cc_puzzle)
            self.base_inner_puzzle_hash = inner_puzzle_hash
        else:
            cc_puzzle = self.fast_cc_puzzle(inner_puzzle_hash)
        return cc_puzzle

    async def get_new_puzzle_hash(self):
        return (
            await self.wallet_state_manager.get_unused_derivation_record(
                self.wallet_info.id
            )
        ).puzzle_hash

    async def select_coins(self, amount: uint64) -> Optional[Set[Coin]]:
        """ Returns a set of coins that can be used for generating a new transaction. """
        async with self.wallet_state_manager.lock:
            spendable_am = await self.get_confirmed_balance()

            if amount > spendable_am:
                self.log.warning(
                    f"Can't select amount higher than our spendable balance {amount}, spendable {spendable_am}"
                )
                return None

            self.log.info(f"About to select coins for amount {amount}")
            unspent: List[WalletCoinRecord] = await self.get_cc_spendable_coins()

            sum = 0
            used_coins: Set = set()

            # Use older coins first
            unspent.sort(key=lambda r: r.confirmed_block_index)

            # Try to use coins from the store, if there isn't enough of "unused"
            # coins use change coins that are not confirmed yet
            unconfirmed_removals: Dict[
                bytes32, Coin
            ] = await self.wallet_state_manager.unconfirmed_removals_for_wallet(
                self.wallet_info.id
            )
            for coinrecord in unspent:
                if sum >= amount and len(used_coins) > 0:
                    break
                if coinrecord.coin.name() in unconfirmed_removals:
                    continue
                sum += coinrecord.coin.amount
                used_coins.add(coinrecord.coin)
                self.log.info(
                    f"Selected coin: {coinrecord.coin.name()} at height {coinrecord.confirmed_block_index}!"
                )

            # This happens when we couldn't use one of the coins because it's already used
            # but unconfirmed, and we are waiting for the change. (unconfirmed_additions)
            if sum < amount:
                raise ValueError(
                    "Can't make this transaction at the moment. Waiting for the change from the previous transaction."
                )

            self.log.info(f"Successfully selected coins: {used_coins}")
            return used_coins

    async def ap_spend(
        self, amount: uint64, to_address: bytes32
    ) -> Optional[SpendBundle]:
        spend_bundle = SpendBundle()
        return spend_bundle

    async def save_info(self, cc_info: CCInfo):
        self.cc_info = cc_info
        current_info = self.wallet_info
        data_str = bytes(cc_info).hex()
        wallet_info = WalletInfo(
            current_info.id, current_info.name, current_info.type, data_str
        )
        self.wallet_info = wallet_info
        await self.wallet_state_manager.user_store.update_wallet(wallet_info)
