import logging
from clvm_tools import binutils
from src.types.sized_bytes import bytes48
from src.types.program import Program
from src.wallet.BLSPrivateKey import BLSPrivateKey
from src.wallet.util.wallet_types import WalletType
from src.wallet.wallet import Wallet
from src.wallet.wallet_info import WalletInfo
from src.util.byte_types import hexstr_to_bytes
from src.wallet.ap_wallet.authoriser_info import AuthoriserInfo
from src.wallet.ap_wallet import ap_puzzles
from blspy import PublicKey
from typing import Any


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
        info_as_string = bytes(self.authoriser_info).hex()
        self.wallet_info = await wallet_state_manager.user_store.create_wallet(
            "Authoriser Wallet", WalletType.AUTHORISER, info_as_string
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
        self.authoriser_info = AuthoriserInfo.from_bytes(
            hexstr_to_bytes(self.wallet_info.data)
        )
        self.base_puzzle_program = None
        self.base_inner_puzzle_hash = None
        return self

    async def add_ap_info(self, name, my_pubkey=None, b_pubkey=None):
        if b_pubkey is None:
            return False
        if my_pubkey is None:
            my_pubkey = await self.get_new_pubkey()
        new_extra_data = (name, bytes(my_pubkey), bytes(b_pubkey))
        current_data = self.authoriser_info.authorisations
        current_data.append(new_extra_data)
        await self.save_info(AuthoriserInfo(current_data))
        return True

    def get_ap_info(self):
        contacts = {}
        for auth in self.authoriser_info.authorisations:
            puzzle = ap_puzzles.ap_make_puzzle(bytes(auth[1]), bytes(auth[2])).get_tree_hash()
            contacts[auth[0]] = {"my_pubkey": auth[1], "their_pubkey": auth[2], "puzhash": puzzle}
        return contacts

    async def get_new_pubkey(self) -> bytes48:
        return (
            await self.wallet_state_manager.get_unused_derivation_record(
                self.wallet_info.id
            )
        ).pubkey

    async def sign(self, value: bytes, pubkey: bytes):
        publickey = PublicKey.from_bytes(bytes(pubkey))
        index = await self.wallet_state_manager.puzzle_store.index_for_pubkey(publickey)
        private = self.wallet_state_manager.private_key.private_child(
            index
        ).get_private_key()
        pk = BLSPrivateKey(private)

        sig = pk.sign(value)
        assert sig.validate([sig.PkMessagePair(publickey, value)])
        return sig

    def puzzle_for_pk(self, pubkey: bytes) -> Program:
        return binutils.assemble(f"(q (AUTHORISER {self.wallet_info.wallet_id} 0x{pubkey}))")

    async def save_info(self, auth_info: AuthoriserInfo):
        self.authoriser_info = auth_info
        current_info = self.wallet_info
        data_str = bytes(auth_info).hex()
        wallet_info = WalletInfo(
            current_info.id, current_info.name, current_info.type, data_str
        )
        self.wallet_info = wallet_info
        await self.wallet_state_manager.user_store.update_wallet(wallet_info)
