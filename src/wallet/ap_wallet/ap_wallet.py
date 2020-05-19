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
from src.wallet.ap_wallet import ap_puzzles
from blspy import PublicKey


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
        wallet_state_manager: Any,
        wallet: Wallet,
        authoriser_pubkey: PublicKey,
        name: str = None,
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
        self.ap_info = APInfo(bytes(authoriser_pubkey), None, [], None)
        info_as_string = bytes(self.ap_info).hex()
        self.wallet_info = await wallet_state_manager.user_store.create_wallet(
            "AP Wallet", WalletType.COLOURED_COIN, info_as_string
        )
        if self.wallet_info is None:
            raise
        await self.wallet_state_manager.add_new_wallet(self, self.wallet_info.id)
        devrec = await self.wallet_state_manager.get_unused_derivation_record(
            self.wallet_info.id
        )
        pubkey = devrec.pubkey
        self.ap_info = APInfo(bytes(authoriser_pubkey), bytes(pubkey), [], None)
        return self

    async def set_sender_values(self, a_pubkey_used, sig=None):
        if sig is not None:
            ap_info = APInfo(
                a_pubkey_used, self.ap_info.my_pubkey, self.ap_info.contacts, sig
            )
        else:
            ap_info = APInfo(
                a_pubkey_used, self.ap_info.my_pubkey, self.ap_info.contacts, self.ap_info.authorised_signature
            )
        puzzlehash = self.puzzle_for_pk(self.ap_info.my_pubkey).get_tree_hash()
        index = await self.wallet_state_manager.puzzle_store.index_for_pubkey(
            self.ap_info.my_pubkey
        )
        derivation_paths = [
            DerivationRecord(
                uint32(index),
                puzzlehash,
                self.ap_info.my_pubkey,
                self.wallet_info.type,
                uint32(self.wallet_info.id),
            )
        ]

        await self.wallet_state_manager.puzzle_store.add_derivation_paths(
            derivation_paths
        )
        await self.save_info(ap_info)
        return

    async def coin_added(
        self, coin: Coin, height: int, header_hash: bytes32, removals: List[Coin]
    ):

        return

    async def get_confirmed_balance(self) -> uint64:
        record_list: Set[
            WalletCoinRecord
        ] = await self.wallet_state_manager.wallet_store.get_unspent_coins_for_wallet(
            self.wallet_info.id
        )

        amount: uint64 = uint64(0)
        for record in record_list:
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

    async def add_contact(self, name, puzzle, new_signature):
        current_contacts = self.ap_info.contacts
        current_contacts.append((name, puzzle))
        old_signature = self.ap_info.authorised_signature
        new_signature = new_signature.aggregate([old_signature, new_signature])
        new_ap_info = APInfo(
            self.ap_info.authoriser_pubkey, current_contacts, new_signature
        )
        self.save_info(new_ap_info)
        return

    def get_contacts(self):
        return self.ap_info.contacts

    def puzzle_for_pk(self, pubkey) -> Program:
        ap_puzzle: Program = ap_puzzles.ap_make_puzzle(
            self.ap_info.authoriser_pubkey, pubkey
        )
        return ap_puzzle

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

    # this is for sending a recieved ap coin, not creating a new ap coin
    def ap_generate_unsigned_transaction(self, puzzlehash_amount_list):
        # we only have/need one coin in this wallet at any time - this code can be improved
        spends = []
        coin = self.temp_coin
        puzzle_hash = coin.puzzle_hash

        pubkey, secretkey = self.get_keys(puzzle_hash, self.a_pubkey)
        puzzle = ap_puzzles.ap_make_puzzle(self.a_pubkey, bytes(pubkey))
        solution = self.ap_make_solution_mode_1(
            puzzlehash_amount_list, coin.parent_coin_info, puzzle_hash
        )
        spends.append((puzzle, CoinSolution(coin, solution)))
        return spends

    # this allows wallet A to approve of new puzzlehashes/spends from wallet B that weren't in the original list
    def ap_sign_output_newpuzzlehash(self, puzzlehash, newpuzzlehash, b_pubkey_used):
        pubkey, secretkey = self.get_keys(puzzlehash, None, b_pubkey_used)
        signature = secretkey.sign(newpuzzlehash)
        return signature

    # this is for sending a locked coin
    # Wallet B must sign the whole transaction, and the appropriate puzhash signature from A must be included
    def ap_sign_transaction(self, spends: (Program, [CoinSolution]), signatures_from_a):
        sigs = []
        for puzzle, solution in spends:
            pubkey, secretkey = self.get_keys(solution.coin.puzzle_hash, self.a_pubkey)
            signature = secretkey.sign(Program(solution.solution).get_tree_hash().hex() + CoinSolution.coin.name())
            sigs.append(signature)
        for s in signatures_from_a:
            sigs.append(s)
        aggsig = BLSSignature.aggregate(sigs)
        solution_list = [
            CoinSolution(
                coin_solution.coin, clvm.to_sexp_f([puzzle, coin_solution.solution])
            )
            for (puzzle, coin_solution) in spends
        ]
        spend_bundle = SpendBundle(solution_list, aggsig)
        return spend_bundle

    # this is for sending a recieved ap coin, not sending a new ap coin
    def ap_generate_signed_transaction(self, amount, puzzlehash):

        # calculate amount of transaction and change
        coins = self.select_coins(amount)
        if coins is None or coins == set():
            return None
        change = sum([coin.amount for coin in coins]) - amount

        # We could take this out and just let the transaction fail, but its probably better to have the sanity check
        found = False
        for name_address in self.ap_info.contacts:
            if puzzlehash == name_address[1]:
                found = True
                break
        if found is False:
            return None

        puzzlehash_amount_list = [(puzzlehash, amount), (self.AP_puzzlehash, change)]
        transaction = self.ap_generate_unsigned_transaction(puzzlehash_amount_list)
        self.temp_coin = Coin(self.temp_coin, self.temp_coin.puzzle_hash, change)
        return self.ap_sign_transaction(transaction, self.ap_info.authorised_signature)

    async def save_info(self, ap_info: APInfo):
        self.cc_info = ap_info
        current_info = self.wallet_info
        data_str = bytes(ap_info).hex()
        wallet_info = WalletInfo(
            current_info.id, current_info.name, current_info.type, data_str
        )
        self.wallet_info = wallet_info
        await self.wallet_state_manager.user_store.update_wallet(wallet_info)
