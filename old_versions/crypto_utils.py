# crypto_utils.py
# Simplified version: works as a pass-through (no AES, no password).
# Keeping function signatures the same for future compatibility.

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
