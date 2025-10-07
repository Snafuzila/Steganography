"""
Common bit/byte/text conversion helpers used by encoders.
"""

from __future__ import annotations
from typing import Iterable, List

# ----- Core conversions -----

def ensure_bytes(data: str | bytes, encoding: str = "utf-8") -> bytes:
    return data if isinstance(data, bytes) else data.encode(encoding)

def bytes_to_bits(data: bytes | str) -> List[int]:
    b = ensure_bytes(data)
    out: List[int] = []
    for byte in b:
        for i in range(7, -1, -1):
            out.append((byte >> i) & 1)
    return out

def bits_to_bytes(bits: Iterable[int]) -> bytes:
    buf = bytearray()
    acc = 0
    count = 0
    for bit in bits:
        acc = (acc << 1) | (1 if bit else 0)
        count += 1
        if count == 8:
            buf.append(acc)
            acc = 0
            count = 0
    if count:  # pad remaining with zeros (caller can avoid by trimming to multiple of 8)
        buf.append(acc << (8 - count))
    return bytes(buf)

# Text <-> bits helpers (bit list)
def text_to_bits(text: str, encoding: str = "utf-8") -> List[int]:
    return bytes_to_bits(ensure_bytes(text, encoding))

def bits_to_text(bits: Iterable[int], encoding: str = "utf-8") -> str:
    return bits_to_bytes(bits).decode(encoding, errors="replace")

# ----- Binary-string (“0101…”) helpers -----

def text_to_binstr(text: str, encoding: str = "utf-8") -> str:
    return "".join(f"{byte:08b}" for byte in ensure_bytes(text, encoding))

def binstr_to_text(binary: str, encoding: str = "utf-8") -> str:
    # Trim to a multiple of 8 (ignore trailing partials)
    n = len(binary) - (len(binary) % 8)
    binary = binary[:n]
    if not binary:
        return ""
    b = bytes(int(binary[i:i+8], 2) for i in range(0, len(binary), 8))
    return b.decode(encoding, errors="replace")

# Integers to fixed-width binary strings
def int_to_nbit_binstr(n: int, width: int = 32) -> str:
    if n < 0:
        raise ValueError("Only non-negative integers are supported")
    return format(n, f"0{width}b")