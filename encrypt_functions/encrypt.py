from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
import base64

def encrypt_message(password: str, message: str) -> str:
    """
    Encrypts a message using AES-256 with a password-based key.
    Returns the result as a base64 string (includes salt and IV for decryption).
    """
    # הגדרת פרמטרים
    salt = get_random_bytes(16)  # מלח לאבטחת ה־Key derivation
    iv = get_random_bytes(16)    # וקטור אתחול עבור AES
    key = PBKDF2(password, salt, dkLen=32, count=100000)  # יצירת מפתח בגודל 256 ביט

    # ריפוד ההודעה לפי AES (בלוקים של 16 בתים)
    pad = lambda s: s + (16 - len(s) % 16) * chr(16 - len(s) % 16)
    padded_message = pad(message).encode()

    # הצפנה
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(padded_message)

    # קידוד לפורמט שניתן לשמור או להחביא
    encrypted_blob = base64.b64encode(salt + iv + ciphertext).decode()

    return encrypted_blob

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
