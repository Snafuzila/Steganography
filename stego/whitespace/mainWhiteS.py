# mainWhiteS.py
# Whitespace steganography (spaces and tabs).
# All input/output files are taken from and saved into the "examples" folder,
# located at the root of the project (next to encrypt_functions).

import os

# === Base paths ===
# __file__ = current file location (whitespace/mainWhiteS.py)
# dirname() 3 times = go up to "Steganography"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")


# === Conversion helpers ===

def text_to_binary(text: str) -> str:
    """Convert text string to a binary string (0/1), 8 bits per character."""
    return ''.join(format(ord(c), '08b') for c in text)

def binary_to_text(binary: str) -> str:
    """Convert a binary string back to text (must be multiple of 8 bits)."""
    return ''.join(chr(int(binary[i:i+8], 2)) for i in range(0, len(binary), 8))

def binary_to_whitespace(binary: str) -> str:
    """Map binary digits to whitespace: '0' -> space, '1' -> tab."""
    return ''.join(' ' if b == '0' else '\t' for b in binary)

def whitespace_to_binary(ws: str) -> str:
    """Map whitespace characters back to binary: space -> '0', tab -> '1'."""
    return ''.join('0' if c == ' ' else '1' for c in ws if c in [' ', '\t'])


# === Embedding ===

def embed_message(input_file: str, output_file: str, secret: str) -> bool:
    """
    Embed the plaintext secret into the host file by appending
    one space/tab character at the end of each line.
    Returns True on success, False if capacity is insufficient.
    """
    binary = text_to_binary(secret)
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
    return binary_to_text(bits)


# === CLI ===

if __name__ == "__main__":
    print("Choose:")
    print("1. Embed message")
    print("2. Extract message")
    choice = input("> ").strip()

    if choice == '1':
        input_file = input("Enter host file name (with extension, inside 'examples'): ").strip()
        output_file = input("Enter stego output file name (with extension, inside 'examples'): ").strip()

        # Build full paths inside examples/
        input_path = os.path.join(EXAMPLES_DIR, input_file)
        output_path = os.path.join(EXAMPLES_DIR, output_file)

        secret = input("Enter message to hide: ")
        embed_message(input_path, output_path, secret)

    elif choice == '2':
        stego_file = input("Enter stego file name (with extension, inside 'examples'): ").strip()

        # Build full path inside examples/
        stego_path = os.path.join(EXAMPLES_DIR, stego_file)

        message = extract_message(stego_path)

        if message:
            print("\nSuccess! Hidden message:")
            print(message)
        else:
            print("\nError: No hidden data found.")

    else:
        print("Error: Invalid choice.")

# === High-level helpers (encryption + stego) ===
from stego import encrypt as encrypt_module

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
