from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
import base64

def encrypt_message(password: str, message: str) -> str:
    """
    Encrypts a message using AES‑256 (CBC) with a key derived from a password.
    Returns a base64 string containing: [salt||iv||ciphertext].
    """
    # Random salt for PBKDF2 (key derivation) and random IV for CBC mode
    salt = get_random_bytes(16)
    iv = get_random_bytes(16)

    # Derive a 256-bit key from the password using PBKDF2 (100k iterations)
    key = PBKDF2(password, salt, dkLen=32, count=100000)

    # PKCS#7-like padding to a multiple of AES block size (16 bytes)
    pad = lambda s: s + (16 - len(s) % 16) * chr(16 - len(s) % 16)
    padded_message = pad(message).encode()

    # Encrypt padded plaintext with AES-CBC
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(padded_message)

    # Package salt + iv + ciphertext and base64-encode for storage/transport
    encrypted_blob = base64.b64encode(salt + iv + ciphertext).decode()
    return encrypted_blob

def decrypt_message(password: str, encrypted_blob: str) -> str:
    """
    Decrypts a base64-encoded blob of the form [salt||iv||ciphertext]
    produced by encrypt_message using the same password.
    """
    # Decode and split the blob into salt (16B), iv (16B), and ciphertext (rest)
    raw = base64.b64decode(encrypted_blob)
    salt, iv, ciphertext = raw[:16], raw[16:32], raw[32:]

    # Re-derive the same key from password and salt
    key = PBKDF2(password, salt, dkLen=32, count=100000)

    # Decrypt and remove PKCS#7 padding
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_plaintext = cipher.decrypt(ciphertext)
    unpad = lambda s: s[:-s[-1]]
    return unpad(padded_plaintext).decode()
