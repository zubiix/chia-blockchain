from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.types.sized_bytes import bytes32, bytes64
from src.util.streamable import streamable, Streamable


@dataclass(frozen=True)
@streamable
class APInfo(Streamable):
    authoriser_pubkey: Optional[bytes64]
    contacts: Optional[List[Tuple[str, bytes32]]]  # list of (name, address, signature)
    authorised_signature: Optional[bytes64]
