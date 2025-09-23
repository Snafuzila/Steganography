from crypto_utils import encrypt_message, decrypt_message

# Convert text to a binary string of '0' and '1' characters (8 bits per character).
def text_to_binary(text):
    return ''.join(format(ord(c), '08b') for c in text)

# Convert a binary string back to text (cut to multiples of 8 bits).
def binary_to_text(binary):
    return ''.join(chr(int(binary[i:i+8], 2)) for i in range(0, len(binary), 8))

# Map bits to whitespace characters: '0' -> space, '1' -> tab.
def binary_to_whitespace(binary):
    return ''.join(' ' if b == '0' else '\t' for b in binary)

# Map whitespace characters back to bits: space -> '0', tab -> '1'.
def whitespace_to_binary(ws):
    return ''.join('0' if c == ' ' else '1' for c in ws if c in [' ', '\t'])

def embed_encrypted_message(input_file, output_file, secret, password):
    """
    Encrypt the secret message, convert it to binary, and embed it
    into the host file by appending space/tab characters at the end of each line.
    """
    encrypted = encrypt_message(secret, password)
    binary = text_to_binary(encrypted)
    whitespace = binary_to_whitespace(binary)

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if len(whitespace) > len(lines):
        print(f"Error: Not enough lines in host file ({len(lines)} lines for {len(whitespace)} bits).")
        return

    # Append one space/tab marker per line for as many bits as needed
    for i in range(len(whitespace)):
        lines[i] = lines[i].rstrip('\n') + whitespace[i] + '\n'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"Message successfully embedded into {output_file}")

def extract_encrypted_message(stego_file):
    """
    Read trailing whitespace markers (space/tab) from the stego file,
    reconstruct the binary string, and convert it back to the ciphertext.
    """
    with open(stego_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    bits = ''
    for line in lines:
        # Look for whitespace before newline that encodes bits
        if line.endswith(' \n') or line.endswith('\t\n'):
            last_char = line[-2]
            if last_char in [' ', '\t']:
                bits += '0' if last_char == ' ' else '1'

    # Ensure we only take complete bytes
    bits = bits[:len(bits) - (len(bits) % 8)]
    binary_string = binary_to_text(bits)

    # Since ciphertext is base64-like, stop at first invalid character
    valid_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_='
    result = ''
    for c in binary_string:
        if c in valid_chars:
            result += c
        else:
            break

    return result

# === CLI ===
if __name__ == "__main__":
    print("Choose:")
    print("1. Encrypt & embed message")
    print("2. Extract & decrypt message")
    choice = input("> ").strip()

    if choice == '1':
        print("Choose file type:")
        print("1. TXT")
        print("2. HTML")
        print("3. CSS")
        file_choice = input("> ").strip()

        # Default names based on type
        if file_choice == '1':
            default_in = "host.txt"
            default_out = "stego_output.txt"
        elif file_choice == '2':
            default_in = "host.html"
            default_out = "stego_output.html"
        elif file_choice == '3':
            default_in = "host.css"
            default_out = "stego_output.css"
        else:
            print("Error: Invalid file type.")
            exit()

        # Let user override default names
        user_in = input(f"Enter host file name [{default_in}]: ").strip() or default_in
        user_out = input(f"Enter stego output file name [{default_out}]: ").strip() or default_out

        secret = input("Enter message to hide: ")
        password = input("Enter password: ")
        embed_encrypted_message(user_in, user_out, secret, password)

    elif choice == '2':
        print("Choose file type to extract from:")
        print("1. TXT")
        print("2. HTML")
        print("3. CSS")
        file_choice = input("> ").strip()

        if file_choice == '1':
            default_in = "stego_output.txt"
        elif file_choice == '2':
            default_in = "stego_output.html"
        elif file_choice == '3':
            default_in = "stego_output.css"
        else:
            print("Error: Invalid file type.")
            exit()

        # Let user override default input file
        user_in = input(f"Enter stego file name [{default_in}]: ").strip() or default_in

        password = input("Enter password to reveal hidden message: ")
        encrypted_data = extract_encrypted_message(user_in)
        decrypted = decrypt_message(encrypted_data, password)

        if decrypted:
            print("\nSuccess! Hidden message:")
            print(decrypted)
        else:
            print("\nError: Wrong password or corrupted data.")

    else:
        print("Error: Invalid choice.")
