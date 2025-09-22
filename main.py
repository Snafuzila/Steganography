# main.py
from encrypt import encrypt_message #AES256
from decrypt import decrypt_message
from PIL import Image
from lsb_img import lsb_img_hide_text_with_length, lsb_img_extract_text_from_image


'''

def main():
    input_image_path = 'input.png'
    output_image_path = 'output.png'
    secret_message = 'Hello World for testing!'

    # Step 1: Open the image
    try:
        original_image = Image.open(input_image_path)
    except FileNotFoundError:
        print(f"❌ Image not found: {input_image_path}")
        return

    # Step 2: Hide the message
    print("📥 Hiding message...")
    encoded_image = lsb_img_hide_text_with_length(original_image, secret_message)

    # Step 3: Save the image with hidden message
    encoded_image.save(output_image_path)
    print(f"✅ Message hidden and saved to {output_image_path}")

    # Step 4: Re-open the image to simulate later extraction
    print("🔍 Extracting message...")
    image_with_message = Image.open(output_image_path)
    extracted_message = lsb_img_extract_text_from_image(image_with_message)

    # Step 5: Output the result
    print("📤 Extracted Message:", extracted_message)

if __name__ == '__main__':
    main()
'''
'''
if __name__ == "__main__":
    password = input("Enter password: ")
    msg = input("Enter message to encrypt: ")

    encrypted = encrypt_message(password, msg)
    print(f"\nEncrypted: {encrypted}")

    decrypted = decrypt_message(password, encrypted)
    print(f"Decrypted: {decrypted}")
'''
