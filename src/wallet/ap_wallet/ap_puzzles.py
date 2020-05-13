from chiasim.hashable import Program, ProgramHash
from clvm_tools import binutils
from utilities.puzzle_utilities import pubkey_format
from chiasim.validation.Conditions import ConditionOpcode


# this is for wallet A to generate the permitted puzzlehashes and sign them ahead of time
# returns a list of tuples of (puzhash, signature)
# not sure about how best to communicate/store who/what the puzzlehashes are, or if this is even important
def ap_generate_signatures(puzhashes, oldpuzzlehash, a_wallet, a_pubkey_used):
    puzhash_signature_list = []
    for p in puzhashes:
        signature = a_wallet.sign(p, a_pubkey_used)
        puzhash_signature_list.append((p, signature))
    return puzhash_signature_list


# we use it to merge the outputs of two programs that create lists
def merge_two_lists(list1=None, list2=None):
    if (list1 is None) or (list2 is None):
        return None
    ret = f"((c (q ((c (f (a)) (a)))) (c (q ((c (i ((c (i (f (r (a))) (q (q ())) (q (q 1))) (a))) (q (f (c (f (r (r (a)))) (q ())))) (q ((c (f (a)) (c (f (a)) (c (r (f (r (a)))) (c (c (f (f (r (a)))) (f (r (r (a))))) (q ())))))))) (a)))) (c {list1} (c {list2} (q ()))))))"
    return ret


# this creates our authorised payee puzzle
def ap_make_puzzle(a_pubkey_serialized, b_pubkey_serialized):
    a_pubkey = pubkey_format(a_pubkey_serialized)
    b_pubkey = pubkey_format(b_pubkey_serialized)

    # Mode one is for spending to one of the approved destinations
    # Solution contains (option 1 flag, new puzzle, new solution, my_primary_input, wallet_puzzle_hash)

    # Below is the result of compiling ap_wallet.clvm

    # It is slightly more optimal to add aggsig solution by hand
    puz = f"((c (q (c (c (q 50) (c (q {b_pubkey}) (c ((c (r (f (a))) (c (f (a)) (c (c (f (r (a))) (c (f (r (r (a)))) (c (f (r (r (r (a))))) (c (f (r (r (r (r (a)))))) (c (f (r (r (r (r (r (a))))))) (c (f (r (r (r (r (r (r (a)))))))) (c (f (r (r (r (r (r (r (r (a))))))))) (q ())))))))) (q ()))))) (q ())))) ((c (i (f (r (a))) (q ((c (f (f (a))) (c (f (a)) (c ((c (f (r (r (a)))) (f (r (r (r (a))))))) (c (q ()) (c (f (r (r (r (r (a)))))) (c (f (r (r (r (r (r (a))))))) (q (())))))))))) (q (c (c (q 53) (c (sha256 (f (r (r (r (r (r (r (a)))))))) (f (r (r (a)))) (f (r (r (r (r (r (r (r (a)))))))))) (q ()))) (c (c (q 51) (c ((c (r (f (a))) (c (f (a)) (c (c (q 7) (c (c (q 5) (c (c (q 1) (c (sha256 (f (r (r (r (a))))) (f (r (r (r (r (a)))))) (f (r (r (r (r (r (a)))))))) (q ()))) (q ((q ()))))) (q ()))) (q ()))))) (q (())))) (c (c (q 51) (c (f (r (r (a)))) (c (+ (f (r (r (r (r (r (a))))))) (f (r (r (r (r (r (r (r (a)))))))))) (q ())))) (q ())))))) (a))))) (c (q (((c (i (l (f (r (a)))) (q ((c (i (= (f (f (f (r (a))))) (q 51)) (q ((c (f (f (a))) (c (f (a)) (c (r (f (r (a)))) (c (c (f (f (r (a)))) (c (c (q 50) (c (q {a_pubkey}) (c (f (r (f (f (r (a)))))) (q ())))) (f (r (r (a)))))) (c (f (r (r (r (a))))) (c (f (r (r (r (r (a)))))) (c (+ (f (r (r (f (f (r (a))))))) (f (r (r (r (r (r (a)))))))) (q ())))))))))) (q ((c (f (f (a))) (c (f (a)) (c (r (f (r (a)))) (c (c (f (f (r (a)))) (f (r (r (a))))) (c (f (r (r (r (a))))) (c (f (r (r (r (r (a)))))) (c (f (r (r (r (r (r (a))))))) (q ()))))))))))) (a)))) (q (c (c (q 53) (c (sha256 (f (r (r (r (a))))) (f (r (r (r (r (a)))))) (f (r (r (r (r (r (a)))))))) (q ()))) (f (r (r (a))))))) (a))) (c (i (l (f (r (a)))) (q (sha256 (q 2) ((c (r (f (a))) (c (f (a)) (c (f (f (r (a)))) (q ()))))) ((c (r (f (a))) (c (f (a)) (c (r (f (r (a)))) (q ()))))))) (q (sha256 (q 1) (f (r (a)))))) (a)))) (a))))"

    return Program(binutils.assemble(puz))


def ap_make_aggregation_puzzle(wallet_puzzle):
    # If Wallet A wants to send further funds to Wallet B then they can lock them up using this code
    # Solution will be (my_id wallet_coin_primary_input wallet_coin_amount)
    me_is_my_id = f'(c (q 0x{ConditionOpcode.ASSERT_MY_COIN_ID.hex()}) (c (f (a)) (q ())))'
    # lock_puzzle is the hash of '(r (c (q "merge in ID") (q ())))'
    lock_puzzle = '(sha256tree (c (q 7) (c (c (q 5) (c (c (q 1) (c (f (a)) (q ()))) (c (q (q ())) (q ())))) (q ()))))'
    parent_coin_id = f"(sha256 (f (r (a))) (q 0x{wallet_puzzle.hex()}) (f (r (r (a)))))"
    input_of_lock = f'(c (q 0x{ConditionOpcode.ASSERT_COIN_CONSUMED.hex()}) (c (sha256 {parent_coin_id} {lock_puzzle} (q 0)) (q ())))'
    puz = f"(c {me_is_my_id} (c {input_of_lock} (q ())))"
    return Program(binutils.assemble(puz))


# returns the ProgramHash of a new puzzle
def ap_get_new_puzzlehash(a_pubkey_serialized, b_pubkey_serialized):
    return ProgramHash(ap_make_puzzle(a_pubkey_serialized, b_pubkey_serialized))


def ap_get_aggregation_puzzlehash(wallet_puzzle):
    return ProgramHash(ap_make_aggregation_puzzle(wallet_puzzle))


# this allows wallet A to approve of new puzzlehashes/spends from wallet B that weren't in the original list
def ap_sign_output_newpuzzlehash(newpuzzlehash, a_wallet, a_pubkey_used):
    signature = a_wallet.sign(newpuzzlehash, a_pubkey_used)
    return signature


# creates the solution that will allow wallet B to spend the coin
# Wallet B is allowed to make multiple spends but must spend the coin in its entirety
def ap_make_solution_mode_1(self, outputs=[], my_primary_input, my_puzzle_hash):
    sol = "(1 (a) ("
    for puzhash, amount in outputs:
        sol += f"(0x{ConditionOpcode.CREATE_COIN.hex()} 0x{puzhash.hex()} {amount})"
    sol += f") 0x{my_primary_input.hex()} 0x{my_puzzle_hash.hex()} () ())"
    return Program(binutils.assemble(sol))


def ac_make_aggregation_solution(self, myid, wallet_coin_primary_input, wallet_coin_amount):
    sol = f"(0x{myid.hex()} 0x{wallet_coin_primary_input.hex()} {wallet_coin_amount})"
    return Program(binutils.assemble(sol))


def ap_make_solution_mode_2(self, wallet_puzzle_hash, consolidating_primary_input, consolidating_coin_puzzle_hash, outgoing_amount, my_primary_input, incoming_amount):
    sol = f"(() 0x{wallet_puzzle_hash.hex()} 0x{consolidating_primary_input.hex()} 0x{consolidating_coin_puzzle_hash.hex()} {outgoing_amount} 0x{my_primary_input.hex()} {incoming_amount})"
    return Program(binutils.assemble(sol))


"""
Copyright 2020 Chia Network Inc
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
   http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
