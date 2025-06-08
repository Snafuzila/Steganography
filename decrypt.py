import base64
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2

def decrypt_message(password: str, encrypted_blob: str) -> str:
    """
    Decrypts a base64-encoded AES-256 encrypted message using the original password.
    """
    raw = base64.b64decode(encrypted_blob)
    salt, iv, ciphertext = raw[:16], raw[16:32], raw[32:]
    key = PBKDF2(password, salt, dkLen=32, count=100000)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_plaintext = cipher.decrypt(ciphertext)

    # הסרת ריפוד
    unpad = lambda s: s[:-s[-1]]
    return unpad(padded_plaintext).decode()
