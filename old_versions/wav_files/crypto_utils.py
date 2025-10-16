"""
crypto_utils.py
----------------

This module contains utility functions for encrypting and decrypting
messages with the AES‑256 cipher.  Instead of relying on external
Python cryptography libraries (which are not available in this
environment), we make use of the ubiquitous OpenSSL command line tool
to perform the heavy lifting.  OpenSSL ships with most UNIX
distributions and provides robust, battle‑tested implementations of
modern cryptographic primitives.  We leverage the `enc` subcommand to
perform password‑based encryption and decryption with PBKDF2 key
derivation and AES‑256 in CBC mode.  The resulting ciphertext is
encoded as Base64 to make it easy to embed inside audio samples.

Functions in this module accept and return Python types only; they
invoke OpenSSL through the standard library's :mod:`subprocess`
interface and raise exceptions on failure.
"""

from __future__ import annotations

import subprocess
from typing import Union


def encrypt_message(message: str, password: str) -> bytes:
    """Encrypt a UTF‑8 string using AES‑256 and return a Base64 string.

    The encryption is performed via the ``openssl`` command line tool.
    We select the AES‑256‑CBC algorithm with PBKDF2 key derivation and
    a random salt.  The resulting ciphertext includes a standard
    header (``Salted__``) followed by the salt and the encrypted
    payload.  We pass the ``-base64`` and ``-A`` flags to OpenSSL so
    that the output is a single‑line Base64 string without embedded
    newlines.  See OpenSSL's manual page for details.

    Args:
        message: The plaintext message to encrypt.  It is encoded to
            bytes using UTF‑8 before encryption.
        password: A user‑supplied passphrase used to derive the
            encryption key.  Using a strong, unique password is
            critical; the PBKDF2 function will apply a work factor to
            slow down brute force attacks.

    Returns:
        A ``bytes`` object containing the Base64‑encoded ciphertext.

    Raises:
        RuntimeError: If the OpenSSL command returns a non‑zero exit
            status.  The error text from OpenSSL will be included in
            the exception message.
    """
    if not isinstance(message, str):
        raise TypeError("message must be a string")
    if not isinstance(password, str):
        raise TypeError("password must be a string")

    # Invoke openssl to perform AES‑256‑CBC encryption with PBKDF2.
    # The -salt option instructs openssl to generate a random salt and
    # prefix it to the output.  The -pbkdf2 flag enables PBKDF2 as the
    # key derivation function rather than the older, weaker EVP_BytesToKey.
    # The -A flag prevents OpenSSL from inserting line breaks in the
    # Base64 output, making it easier to embed inside our bitstream.
    process = subprocess.run(
        [
            "openssl",
            "enc",
            "-aes-256-cbc",
            "-salt",
            "-pbkdf2",
            "-pass",
            f"pass:{password}",
            "-base64",
            "-A",
        ],
        input=message.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenSSL encryption failed: {stderr}")
    # Strip any trailing whitespace to avoid embedding unnecessary
    # characters.  The output is bytes; return as is.
    return process.stdout.strip()


def decrypt_message(enc_data: bytes, password: str) -> str:
    """Decrypt a Base64 string produced by :func:`encrypt_message`.

    This function reverses the process performed by
    :func:`encrypt_message`.  It passes the Base64 ciphertext to
    OpenSSL, which automatically parses the ``Salted__`` header,
    extracts the salt, derives the decryption key using PBKDF2 and the
    provided password, and decrypts the remaining bytes.  The
    plaintext is returned as a UTF‑8 string.

    Args:
        enc_data: The Base64‑encoded ciphertext (as bytes) returned
            from :func:`encrypt_message`.
        password: The passphrase used during encryption.

    Returns:
        The decrypted message as a Python string.

    Raises:
        RuntimeError: If the OpenSSL command returns a non‑zero exit
            status (for example, when the password is incorrect).
    """
    if not isinstance(enc_data, (bytes, bytearray)):
        raise TypeError("enc_data must be bytes")
    if not isinstance(password, str):
        raise TypeError("password must be a string")

    # Feed the Base64 ciphertext into OpenSSL's standard input.  We use
    # the -d flag to indicate decryption and pass the same algorithm
    # parameters used during encryption.  OpenSSL will verify the
    # message integrity and fail if the password is incorrect.
    process = subprocess.run(
        [
            "openssl",
            "enc",
            "-d",
            "-aes-256-cbc",
            "-salt",
            "-pbkdf2",
            "-pass",
            f"pass:{password}",
            "-base64",
            "-A",
        ],
        input=enc_data,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenSSL decryption failed: {stderr}")
    # Decode the plaintext using UTF‑8.  Any decoding errors will
    # propagate to the caller.
    return process.stdout.decode("utf-8")
