from dataclasses import dataclass
from typing import Optional
from src.types.sized_bytes import bytes48
from src.util.streamable import streamable, Streamable


@dataclass(frozen=True)
@streamable
class AuthoriserInfo(Streamable):
    name: Optional[str]
    my_pubkey: Optional[bytes48]
    their_pubkey: Optional[bytes48]
