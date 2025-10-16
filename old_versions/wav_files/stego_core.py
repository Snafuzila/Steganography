"""
stego_core.py
--------------

Core functionality for hiding and retrieving messages in 16‑bit mono WAV
audio files using the Least Significant Bit (LSB) technique.  This
module exposes two primary functions, :func:`encode_message` and
:func:`decode_message`, which orchestrate reading the input audio,
encrypting/decrypting the payload, embedding/extracting bits and
writing the resulting stego audio.

The implementation is deliberately modular.  Helper functions convert
between bytes and bit arrays, perform the bitwise embedding, and
extract bits using a generator.  Cryptographic operations are
delegated to :mod:`crypto_utils`, which wraps the OpenSSL command
line tool.  Only 1–3 LSBs of each 16‑bit sample are modified to
minimize audible distortion.
"""

from __future__ import annotations

import os
import wave
from getpass import getpass
from typing import Iterable, Iterator, List
from .crypto_utils import encrypt_message, decrypt_message



def bytes_to_bits(data: bytes) -> List[int]:
    """Convert a byte sequence into a list of bits (MSB first).

    Args:
        data: Arbitrary binary data.

    Returns:
        A list of integers (0 or 1) representing each bit of the input
        sequence, starting with the most significant bit of the first
        byte.
    """
    bits: List[int] = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def bits_to_bytes(bits: Iterable[int]) -> bytes:
    """Reassemble an iterable of bits into bytes.

    The number of bits provided must be a multiple of 8; any excess
    bits are ignored.

    Args:
        bits: An iterable yielding 0/1 values.

    Returns:
        A bytes object reconstructed from the input bits.
    """
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
    # Ignore any partial byte at the end
    return bytes(out)


def bits_to_int(bits: Iterable[int]) -> int:
    """Interpret a sequence of bits as a big‑endian integer."""
    value = 0
    for bit in bits:
        value = (value << 1) | (1 if bit else 0)
    return value


def embed_bits_into_audio(
    frames: bytearray, bits: List[int], n_lsb: int
) -> None:
    """Embed a list of bits into the least significant bits of audio samples.

    This routine operates on a ``bytearray`` representing little‑endian
    16‑bit mono PCM samples.  It modifies the first byte of each
    16‑bit sample (the lower byte) by replacing its ``n_lsb`` least
    significant bits with data from ``bits``.  If the number of bits
    provided is not a multiple of ``n_lsb`` then the final group is
    padded with zeros.

    Args:
        frames: Audio frame data (modified in place).
        bits: Sequence of bits (0/1) to embed.
        n_lsb: Number of least significant bits to replace per sample
            (must be between 1 and 3).

    Raises:
        ValueError: If the provided bitstream is too large to fit in
            the audio data.
    """
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
        byte_idx = sample_idx * 2  # lower byte of the 16‑bit sample
        current_byte = frames[byte_idx]
        # Clear the n_lsb least significant bits
        current_byte &= ~mask
        # Collect up to n_lsb bits for this sample
        slice_end = bit_index + n_lsb
        bit_slice = bits[bit_index:slice_end]
        if len(bit_slice) < n_lsb:
            # Pad with zeros to fill the remaining bits
            bit_slice += [0] * (n_lsb - len(bit_slice))
        # Convert bit_slice to an integer (MSB first)
        value = 0
        for b in bit_slice:
            value = (value << 1) | (1 if b else 0)
        # Combine with current byte
        frames[byte_idx] = current_byte | (value & mask)
        bit_index += len(bit_slice)


def bits_from_audio(frames: bytes, n_lsb: int) -> Iterator[int]:
    """Yield bits embedded in the audio's least significant bits.

    Iterates over the lower byte of each 16‑bit sample and yields
    ``n_lsb`` bits from that byte, starting with the most significant
    of those bits.  Bits are yielded in the order they were embedded
    by :func:`embed_bits_into_audio`.

    Args:
        frames: A bytes object containing little‑endian 16‑bit PCM
            samples.
        n_lsb: Number of bits to extract per sample.

    Yields:
        Individual bits (0/1) as integers.
    """
    if n_lsb < 1 or n_lsb > 3:
        raise ValueError("n_lsb must be between 1 and 3 inclusive")
    mask = (1 << n_lsb) - 1
    num_samples = len(frames) // 2
    for sample_idx in range(num_samples):
        byte_idx = sample_idx * 2
        value = frames[byte_idx] & mask
        # Yield bits from most significant to least significant
        for j in range(n_lsb - 1, -1, -1):
            yield (value >> j) & 1


def encode_message(
    audio_path: str,
    message_text: str,
    output_path: str,
    n_lsb: int = 1,
    password: str | None = None,  # ✅ חדש
) -> None:

    """Hide a plaintext message inside a WAV file.

    This function reads a mono 16‑bit WAV file, encrypts the provided
    message with a user‑supplied password, prefixes the encrypted
    payload with its length (in bytes) and embeds the resulting bit
    stream into the least significant bits of the audio samples.  The
    modified audio is written to ``output_path``.  Only the lower
    byte of each sample is modified, preserving most of the original
    signal quality【51454510526638†L650-L706】.

    Args:
        audio_path: Path to the input WAV file (must be 16‑bit mono).
        message_text: The plaintext message or the path to a text
            file containing the message.  If the path exists on disk
            it will be read; otherwise the value is treated as the
            message itself.
        output_path: Path where the stego WAV file will be written.
        n_lsb: Number of least significant bits to use (1–3).  Using
            more bits increases capacity at the cost of slightly more
            distortion.

    Raises:
        ValueError: If the input audio is not mono 16‑bit PCM or the
            message is too large for the chosen ``n_lsb``.
    """
    if n_lsb < 1 or n_lsb > 3:
        raise ValueError("n_lsb must be between 1 and 3 inclusive")
    # Read the message text; if the provided path exists, load it from
    # file.  Otherwise treat it as the literal message.
    if os.path.exists(message_text):
        with open(message_text, "r", encoding="utf-8") as f:
            plaintext = f.read()
    else:
        plaintext = message_text
    # Prompt the user for a password; use getpass to avoid echoing.
    if password is None:
        password = getpass("Enter password for encryption: ")
    # Encrypt the message.  The result is a Base64 string (bytes).
    enc_data = encrypt_message(plaintext, password)
    # Prepend the length of the encrypted payload as a 32‑bit unsigned
    # integer.  This will allow the decoder to know when to stop
    # reading bits.  Big‑endian order is chosen for consistency.
    length_bytes = len(enc_data).to_bytes(4, byteorder="big", signed=False)
    full_payload = length_bytes + enc_data
    # Convert payload into bits
    payload_bits = bytes_to_bits(full_payload)
    # Open the input WAV and verify format
    with wave.open(audio_path, mode="rb") as wav_in:
        params = wav_in.getparams()
        n_channels = params.nchannels
        sample_width = params.sampwidth
        if n_channels != 1 or sample_width != 2:
            raise ValueError(
                f"Unsupported audio format: {n_channels} channels, {sample_width*8}-bit samples. "
                "Only 16‑bit mono WAV files are supported."
            )
        frames = bytearray(wav_in.readframes(wav_in.getnframes()))
    # Embed the bits into the frame data
    embed_bits_into_audio(frames, payload_bits, n_lsb)
    # Write the modified frames to the output file with the same
    # parameters as the original audio【51454510526638†L650-L706】.
    with wave.open(output_path, mode="wb") as wav_out:
        wav_out.setparams(params)
        wav_out.writeframes(frames)


def decode_message(
    stego_audio_path: str,
    n_lsb: int = 1,
    save_to_file: bool = True,
    password: str = None,  # הוספנו סיסמה כפרמטר אופציונלי
) -> str:
    """Extract and decrypt a hidden message from a stego WAV file."""
    if n_lsb < 1 or n_lsb > 3:
        raise ValueError("n_lsb must be between 1 and 3 inclusive")

    # קריאת הקובץ
    with wave.open(stego_audio_path, mode="rb") as wav_in:
        params = wav_in.getparams()
        n_channels = params.nchannels
        sample_width = params.sampwidth
        if n_channels != 1 or sample_width != 2:
            raise ValueError(
                f"Unsupported audio format: {n_channels} channels, {sample_width*8}-bit samples. "
                "Only 16‑bit mono WAV files are supported."
            )
        frames = wav_in.readframes(wav_in.getnframes())

    # שליפה של האורך (32 ביט)
    bit_gen = bits_from_audio(frames, n_lsb)
    length_bits = []
    try:
        for _ in range(32):
            length_bits.append(next(bit_gen))
    except StopIteration:
        raise ValueError("Audio file does not contain enough data to extract length header")
    enc_length = bits_to_int(length_bits)

    # שליפה של תוכן ההודעה
    total_payload_bits = enc_length * 8
    payload_bits: List[int] = []
    try:
        for _ in range(total_payload_bits):
            payload_bits.append(next(bit_gen))
    except StopIteration:
        raise ValueError(
            "Audio file ended unexpectedly while reading the encrypted message. "
            "Ensure that the correct n_lsb value is used."
        )
    enc_bytes = bits_to_bytes(payload_bits)

    # בקשת סיסמה אם לא סופקה
    if password is None:
        password = getpass("Enter password to decrypt: ")

    # פענוח
    plaintext = decrypt_message(enc_bytes, password)

    # שמירה לקובץ אם צריך
    if save_to_file:
        base, _ = os.path.splitext(os.path.basename(stego_audio_path))
        out_file = os.path.join(os.path.dirname(stego_audio_path), f"{base}_decoded.txt")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(plaintext)


    """Extract and decrypt a hidden message from a stego WAV file.

    This function reads the modified audio produced by
    :func:`encode_message`, extracts the length of the encrypted
    payload (stored in the first 32 bits), retrieves the encrypted
    bytes, prompts the user for the password and decrypts the
    Base64‑encoded string back into the original plaintext.  The
    recovered message is returned and optionally written to a text file.

    Args:
        stego_audio_path: Path to the WAV file containing a hidden
            message.
        n_lsb: Number of least significant bits used during encoding.
        save_to_file: If ``True``, the recovered message will be
            written to a text file with the same base name as the
            audio file (``<audio>_decoded.txt``).

    Returns:
        The decrypted plaintext message.

    Raises:
        ValueError: If the audio format is unsupported or the
            bitstream is malformed.
    """
    if n_lsb < 1 or n_lsb > 3:
        raise ValueError("n_lsb must be between 1 and 3 inclusive")
    # Read the audio file
    with wave.open(stego_audio_path, mode="rb") as wav_in:
        params = wav_in.getparams()
        n_channels = params.nchannels
        sample_width = params.sampwidth
        if n_channels != 1 or sample_width != 2:
            raise ValueError(
                f"Unsupported audio format: {n_channels} channels, {sample_width*8}-bit samples. "
                "Only 16‑bit mono WAV files are supported."
            )
        frames = wav_in.readframes(wav_in.getnframes())
    # Create a generator to pull bits sequentially
    bit_gen = bits_from_audio(frames, n_lsb)
    # Extract first 32 bits to get the length
    length_bits = []
    try:
        for _ in range(32):
            length_bits.append(next(bit_gen))
    except StopIteration:
        raise ValueError("Audio file does not contain enough data to extract length header")
    enc_length = bits_to_int(length_bits)
    # Calculate how many bits to read for the encrypted payload
    total_payload_bits = enc_length * 8
    payload_bits: List[int] = []
    try:
        for _ in range(total_payload_bits):
            payload_bits.append(next(bit_gen))
    except StopIteration:
        raise ValueError(
            "Audio file ended unexpectedly while reading the encrypted message. "
            "Ensure that the correct n_lsb value is used."
        )
    # Convert bits to bytes
    enc_bytes = bits_to_bytes(payload_bits)
    # Prompt user for password used during encryption
    password = getpass("Enter password to decrypt: ")
    # Decrypt the message
    plaintext = decrypt_message(enc_bytes, password)
    # Optionally write to a file
    if save_to_file:
        base, _ = os.path.splitext(os.path.basename(stego_audio_path))
        out_file = os.path.join(os.path.dirname(stego_audio_path), f"{base}_decoded.txt")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(plaintext)
    return plaintext
