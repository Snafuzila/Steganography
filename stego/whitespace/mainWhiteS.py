import os
from stego.utils.bit_utils import text_to_binstr, binstr_to_text
from stego.utils import encrypt as encrypt_module

# Whitespace steganography (spaces and tabs).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")

# === Conversion helpers ===

def binary_to_whitespace(binary: str) -> str:
    return ''.join(' ' if b == '0' else '\t' for b in binary)

def whitespace_to_binary(ws: str) -> str:
    return ''.join('0' if c == ' ' else '1' for c in ws if c in [' ', '\t'])


# === Embedding ===

def embed_message(input_file: str, output_file: str, secret: str) -> bool:
    """
    Embed the plaintext secret into the host file by appending
    one space/tab character at the end of each line.
    Returns True on success, False if capacity is insufficient.
    """
    binary = text_to_binstr(secret)
    whitespace = binary_to_whitespace(binary)

    with open(input_file, 'r', encoding='utf-8', newline='') as f:
        lines = f.readlines()

    if len(whitespace) > len(lines):
        print(f"Error: Not enough lines in host file ({len(lines)} lines for {len(whitespace)} bits).")
        return False

    for i in range(len(whitespace)):
        lines[i] = lines[i].rstrip('\r\n') + whitespace[i] + os.linesep

    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        f.writelines(lines)

    print(f"Message successfully embedded into {output_file}")
    return True

# === Extraction ===

def extract_message(stego_file: str) -> str:
    """
    Extract the hidden message from the stego file by reading
    trailing spaces/tabs at the end of each line.
    """
    with open(stego_file, 'r', encoding='utf-8', newline='') as f:
        lines = f.readlines()

    bits = ''
    for line in lines:
        stripped = line.rstrip('\r\n')
        if not stripped:
            continue
        last_char = stripped[-1]
        if last_char in [' ', '\t']:
            bits += '0' if last_char == ' ' else '1'

    bits = bits[:len(bits) - (len(bits) % 8)]
    return binstr_to_text(bits)

# === High-level helpers (encryption + stego) ===

def encode_file(input_file: str, output_file: str, message: str, password: str) -> bool:
    """
    Encrypts 'message' with 'password' and embeds it into the input file.
    Returns True on success, False if capacity is insufficient.
    """
    ciphertext = encrypt_module.encrypt_message(password, message)
    return embed_message(input_file, output_file, ciphertext)

def decode_file(stego_file: str, password: str) -> str:
    """
    Extracts and decrypts the hidden message from stego_file.
    Returns a plaintext string (empty string if nothing found).
    """
    encrypted = extract_message(stego_file)
    return encrypt_module.decrypt_message(password, encrypted)
