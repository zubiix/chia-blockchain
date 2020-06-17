from dataclasses import dataclass
from typing import List, Optional, Tuple
from src.types.sized_bytes import bytes48
from src.util.streamable import streamable, Streamable


@dataclass(frozen=True)
@streamable
class AuthoriserInfo(Streamable):
    authorisations: Optional[
        List[Tuple[str, bytes48, bytes48, List[Tuple[bytes, bytes]]]]
    ]  # Optional list of (name, my_pubkey, their pubkey [(message, sig)])
