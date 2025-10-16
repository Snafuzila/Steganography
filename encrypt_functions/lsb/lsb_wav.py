"""
stego_core.py
--------------

Core functionality for hiding and retrieving messages in 16-bit mono WAV
audio files using the Least Significant Bit (LSB) technique.  This
module exposes two primary functions, :func:`encode_message` and
:func:`decode_message`, which orchestrate reading the input audio,
embedding/extracting bits and writing the resulting stego audio.

IMPORTANT:
This module no longer performs any AES encryption/decryption.
It embeds and extracts **plain UTF-8 text** only.
If encryption is required, perform it **outside** this module
(e.g., in your MAIN/GUI layer) and pass the already-processed
payload (e.g., base64 string) as the message_text parameter.
"""

from __future__ import annotations

import os
import wave
from typing import Iterable, Iterator, List


def bytes_to_bits(data: bytes) -> List[int]:
    """Convert a byte sequence into a list of bits (MSB first)."""
    bits: List[int] = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def bits_to_bytes(bits: Iterable[int]) -> bytes:
    """Reassemble an iterable of bits into bytes (ignores trailing partials)."""
    out = bytearray()
    accumulator = 0
    count = 0
    for bit in bits:
        accumulator = (accumulator << 1) | (1 if bit else 0)
        count += 1
        if count == 8:
            out.append(accumulator)
            accumulator = 0
            count = 0
    return bytes(out)


def bits_to_int(bits: Iterable[int]) -> int:
    """Interpret a sequence of bits as a big-endian integer."""
    value = 0
    for bit in bits:
        value = (value << 1) | (1 if bit else 0)
    return value


def embed_bits_into_audio(frames: bytearray, bits: List[int], n_lsb: int) -> None:
    """Embed a list of bits into the least significant bits of audio samples."""
    if n_lsb < 1 or n_lsb > 3:
        raise ValueError("n_lsb must be between 1 and 3 inclusive")
    num_samples = len(frames) // 2
    capacity = num_samples * n_lsb
    if len(bits) > capacity:
        raise ValueError(
            f"Message requires {len(bits)} bits but audio can store only {capacity} bits using {n_lsb} LSBs"
        )
    mask = (1 << n_lsb) - 1
    bit_index = 0
    total_bits = len(bits)
    for sample_idx in range(num_samples):
        if bit_index >= total_bits:
            break
        byte_idx = sample_idx * 2  # lower byte of the 16-bit sample
        current_byte = frames[byte_idx]
        current_byte &= ~mask  # clear the n_lsb bits
        # pack up to n_lsb bits
        slice_end = bit_index + n_lsb
        bit_slice = bits[bit_index:slice_end]
        if len(bit_slice) < n_lsb:
            bit_slice += [0] * (n_lsb - len(bit_slice))
        value = 0
        for b in bit_slice:
            value = (value << 1) | (1 if b else 0)
        frames[byte_idx] = current_byte | (value & mask)
        bit_index += len(bit_slice)


def bits_from_audio(frames: bytes, n_lsb: int) -> Iterator[int]:
    """Yield bits embedded in the audio's least significant bits."""
    if n_lsb < 1 or n_lsb > 3:
        raise ValueError("n_lsb must be between 1 and 3 inclusive")
    mask = (1 << n_lsb) - 1
    num_samples = len(frames) // 2
    for sample_idx in range(num_samples):
        byte_idx = sample_idx * 2
        value = frames[byte_idx] & mask
        for j in range(n_lsb - 1, -1, -1):  # MSB→LSB of the selected bits
            yield (value >> j) & 1


def encode_message(
    audio_path: str,
    message_text: str,
    output_path: str,
    n_lsb: int = 1,
    password: str | None = None,  # kept for backward-compatibility; unused
) -> None:
    """
    Hide a **plaintext** UTF-8 message inside a WAV file (no AES here).

    If you need encryption, encrypt in your outer layer and pass the
    resulting string (e.g., base64) as `message_text`.
    """
    if n_lsb < 1 or n_lsb > 3:
        raise ValueError("n_lsb must be between 1 and 3 inclusive")

    # Read message: if `message_text` is a path, read file; else treat as literal.
    if os.path.exists(message_text):
        with open(message_text, "r", encoding="utf-8") as f:
            plaintext = f.read()
    else:
        plaintext = message_text

    # Convert to bytes and prefix 4-byte length (big-endian)
    msg_bytes = plaintext.encode("utf-8")
    length_bytes = len(msg_bytes).to_bytes(4, byteorder="big", signed=False)
    full_payload = length_bytes + msg_bytes
    payload_bits = bytes_to_bits(full_payload)

    # Open input WAV and verify it is 16-bit mono
    with wave.open(audio_path, mode="rb") as wav_in:
        params = wav_in.getparams()
        n_channels = params.nchannels
        sample_width = params.sampwidth
        if n_channels != 1 or sample_width != 2:
            raise ValueError(
                f"Unsupported audio format: {n_channels} channels, {sample_width*8}-bit samples. "
                "Only 16-bit mono WAV files are supported."
            )
        frames = bytearray(wav_in.readframes(wav_in.getnframes()))

    # Embed and write out
    embed_bits_into_audio(frames, payload_bits, n_lsb)
    with wave.open(output_path, mode="wb") as wav_out:
        wav_out.setparams(params)
        wav_out.writeframes(frames)


def decode_message(
    stego_audio_path: str,
    n_lsb: int = 1,
    save_to_file: bool = True,
    password: str | None = None,  # kept for backward-compatibility; unused
) -> str:
    """Extract a **plaintext** UTF-8 message from a stego WAV file (no AES here)."""
    if n_lsb < 1 or n_lsb > 3:
        raise ValueError("n_lsb must be between 1 and 3 inclusive")

    # Read frames and verify format
    with wave.open(stego_audio_path, mode="rb") as wav_in:
        params = wav_in.getparams()
        n_channels = params.nchannels
        sample_width = params.sampwidth
        if n_channels != 1 or sample_width != 2:
            raise ValueError(
                f"Unsupported audio format: {n_channels} channels, {sample_width*8}-bit samples. "
                "Only 16-bit mono WAV files are supported."
            )
        frames = wav_in.readframes(wav_in.getnframes())

    # Recreate the embedded bitstream
    bit_gen = bits_from_audio(frames, n_lsb)

    # First 32 bits = payload length in bytes
    length_bits = []
    try:
        for _ in range(32):
            length_bits.append(next(bit_gen))
    except StopIteration:
        raise ValueError("Audio file does not contain enough data to extract length header")
    msg_len = bits_to_int(length_bits)

    # Next msg_len * 8 bits = payload bytes (UTF-8 text)
    total_payload_bits = msg_len * 8
    payload_bits: List[int] = []
    try:
        for _ in range(total_payload_bits):
            payload_bits.append(next(bit_gen))
    except StopIteration:
        raise ValueError(
            "Audio file ended unexpectedly while reading the message. "
            "Ensure that the correct n_lsb value is used."
        )
    msg_bytes = bits_to_bytes(payload_bits)
    plaintext = msg_bytes.decode("utf-8", errors="strict")

    if save_to_file:
        base, _ = os.path.splitext(os.path.basename(stego_audio_path))
        out_file = os.path.join(os.path.dirname(stego_audio_path), f"{base}_decoded.txt")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(plaintext)

    return plaintext
