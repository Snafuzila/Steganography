from encrypt import encrypt_message
from decrypt import decrypt_message

if __name__ == "__main__":
    password = input("Enter password: ")
    msg = input("Enter message to encrypt: ")

    encrypted = encrypt_message(password, msg)
    print(f"\nEncrypted: {encrypted}")

    decrypted = decrypt_message(password, encrypted)
    print(f"Decrypted: {decrypted}")
