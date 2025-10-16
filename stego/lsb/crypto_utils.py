# crypto_utils.py
# Simple XOR-based encryption for WAV steganography

def encrypt_message(message: str, password: str = None) -> bytes:
    """
    Simple XOR encryption with password.
    Returns encrypted bytes.
    """
    if not password:
        return message.encode("utf-8")
    
    message_bytes = message.encode("utf-8")
    password_bytes = password.encode("utf-8")
    
    # XOR each byte with password bytes (cycling through password)
    encrypted = bytearray()
    for i, byte in enumerate(message_bytes):
        encrypted.append(byte ^ password_bytes[i % len(password_bytes)])
    
    return bytes(encrypted)

def decrypt_message(token: bytes, password: str = None) -> str:
    """
    Simple XOR decryption with password.
    Returns decrypted string or garbled text if password is wrong.
    """
    if token is None:
        return None
    
    if not password:
        # No password provided, try to decode as UTF-8
        try:
            return token.decode("utf-8", errors="replace")
        except:
            return str(token)
    
    password_bytes = password.encode("utf-8")
    
    # XOR each byte with password bytes (cycling through password)
    decrypted = bytearray()
    for i, byte in enumerate(token):
        decrypted.append(byte ^ password_bytes[i % len(password_bytes)])
    
    # Try to decode as UTF-8, but allow replacement chars for wrong passwords
    try:
        return decrypted.decode("utf-8", errors="replace")
    except:
        return str(decrypted)
