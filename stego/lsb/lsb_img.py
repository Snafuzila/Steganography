#lsb_img.py
from PIL import Image  # Pillow library to handle images
from stego import encrypt as encrypt_module

# Converts a string message into a binary string
def text_to_binary(text):
    return ''.join(format(ord(char), '08b') for char in text)
    # Example: "A" → '01000001'

# Converts an integer to a 32-bit binary string ~ this is to hold the size of the string, 32bits = 530mb , 16 = 8kb. 32 bit is popular in many tools
def int_to_32bit_binary(n):
    return format(n, '032b')
    # Example: 150 → '00000000000000000000000010010110'

# Main function to hide the message in an image
# def hide_text_with_length(image_path, message): # we comment the next line if we want to get path and not image object
def lsb_img_hide_text_with_length(image: Image.Image, message: str) -> Image.Image:
    # img = Image.open(image_path)  # we uncomment this line if we want to change the input to path, then the line open the input image

    # Make sure image is in RGB mode (not RGBA, grayscale, etc.)
    if image.mode != 'RGB':
        image = image.convert('RGB')

    # Convert the message to a binary string
    binary_message = text_to_binary(message)

    # Calculate message length in bits and create a 32-bit binary header
    message_length = len(binary_message)
    length_header = int_to_32bit_binary(message_length)

    # Combine length + actual message: total bits to hide
    full_binary = length_header + binary_message

    # Convert image pixels to a list of (R, G, B) tuples
    pixels = list(image.getdata())

    # Will store the modified pixels
    new_pixels = []

    data_index = 0                      # Index of the bit we are embedding
    total_bits = len(full_binary)      # Total number of bits to embed

    # Loop through each pixel and modify its LSBs
    for pixel in pixels:
        if data_index >= total_bits:
            # No more bits to embed, just copy the pixel
            new_pixels.append(pixel)
            continue

        r, g, b = pixel  # Unpack RGB values. we converted to RGB mode, so there shouldnt be alpha channel.

        # For each color channel, replace the least significant bit
        if data_index < total_bits:
            r = (r & ~1) | int(full_binary[data_index])  # Clear LSB and set it. (r & ~1) clear the last bit. then there is '|' or operator if message bit is one it 
            #                                                         puts 1 there, we get from full_binary a char andso we also convert to int.  
            data_index += 1
        if data_index < total_bits:
            g = (g & ~1) | int(full_binary[data_index])
            data_index += 1
        if data_index < total_bits:
            b = (b & ~1) | int(full_binary[data_index])
            data_index += 1

        # Save the modified pixel
        new_pixels.append((r, g, b))

    # Safety check: if we ran out of space before encoding all bits
    if data_index < total_bits:
        raise ValueError("Message is too long for this image.")

    # Create a new image with the same size and mode
    new_img = Image.new(image.mode, image.size)
    new_img.putdata(new_pixels)  # Update the pixels with the modified ones

    return new_img  # Return the new image (not saved to file yet)



# Converts a binary string into a text string
def binary_to_text(binary_string):
    chars = [binary_string[i:i+8] for i in range(0, len(binary_string), 8)]
    return ''.join(chr(int(char, 2)) for char in chars)

# Function to extract the hidden message from the image
def lsb_img_extract_text_from_image(image: Image.Image) -> str:
    # Make sure the image is in RGB mode
    if image.mode != 'RGB':
        image = image.convert('RGB')

    pixels = list(image.getdata())
    bit_stream = ''

    # Step 1: Extract LSBs from all RGB channels
    for pixel in pixels:
        for value in pixel:  # r, g, b values
            bit_stream += str(value & 1)

    # Step 2: First 32 bits represent the length of the message in bits
    length_bits = bit_stream[:32]
    message_length = int(length_bits, 2)

    # Step 3: Extract the actual message bits using the length
    message_bits = bit_stream[32:32+message_length]

    # Step 4: Convert the bits into text
    hidden_message = binary_to_text(message_bits)
    return hidden_message

def encode_file(image_path: str, output_path: str, message: str, password: str) -> None:
    """
    Encrypts message and writes a new stego image to output_path.
    """
    from PIL import Image
    ciphertext = encrypt_module.encrypt_message(password, message)
    img = Image.open(image_path)
    new_img = lsb_img_hide_text_with_length(img, ciphertext)
    new_img.save(output_path)

def decode_file(image_path: str, password: str) -> str:
    """
    Extracts and decrypts message from the image at image_path.
    """
    from PIL import Image
    img = Image.open(image_path)
    encrypted_blob = lsb_img_extract_text_from_image(img)
    return encrypt_module.decrypt_message(password, encrypted_blob)