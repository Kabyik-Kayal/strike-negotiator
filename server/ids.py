from secrets import token_bytes
from time import time


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_base32(value: int, length: int) -> str:
    chars: list[str] = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def new_ulid() -> str:
    timestamp_ms = int(time() * 1000)
    random_value = int.from_bytes(token_bytes(10), "big")
    return f"{_encode_base32(timestamp_ms, 10)}{_encode_base32(random_value, 16)}"

