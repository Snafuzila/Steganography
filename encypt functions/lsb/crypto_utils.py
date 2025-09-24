# crypto_utils.py
# Simplified version: works as a pass-through (no AES, no password).
# Keeping function signatures the same for future compatibility.

<<<<<<< HEAD
def encrypt_message(message: str, password: str = None) -> str:
    """
    Stub function: returns the message as-is (no encryption).
    The 'password' parameter is kept only for API compatibility.
    """
    return message

def decrypt_message(token: str, password: str = None) -> str:
    """
    Stub function: returns the token as-is (no decryption).
    If the token is None, return None to preserve expected behavior.
    """
    if token is None:
        return None
    return token
=======
def encrypt_message(message: str, password: str = None) -> bytes:
    """
    Stub: return message as UTF-8 bytes (no real encryption).
    This keeps the downstream API (which expects bytes) satisfied.
    """
    return message.encode("utf-8")

def decrypt_message(token: bytes, password: str = None) -> str:
    """
    Stub: interpret token as UTF-8 bytes and return a string.
    If token is None, return None.
    """
    if token is None:
        return None
    if isinstance(token, bytes):
        return token.decode("utf-8", errors="replace")
    return str(token)
>>>>>>> master
