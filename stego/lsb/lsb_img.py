from PIL import Image  # Pillow library to handle images
from stego import encrypt as encrypt_module
from stego.utils.bit_utils import (
    text_to_binstr,
    binstr_to_text,
    int_to_nbit_binstr,
)

def lsb_img_hide_text_with_length(image: Image.Image, message: str) -> Image.Image:
    # img = Image.open(image_path)  # we uncomment this line if we want to change the input to path, then the line open the input image

    # Make sure image is in RGB mode (not RGBA, grayscale, etc.)
    if image.mode != 'RGB':
        image = image.convert('RGB')

    binary_message = text_to_binstr(message)  # unified helper

    # Calculate message length in bits and create a 32-bit binary header
    message_length = len(binary_message)
    length_header = int_to_nbit_binstr(message_length, 32)

    full_binary = length_header + binary_message

    # Convert image pixels to a list of (R, G, B) tuples
    pixels = list(image.getdata())

    new_pixels = []
    data_index = 0  # Index of the bit we are embedding
    total_bits = len(full_binary)  # Total number of bits to embed

    for pixel in pixels:
        if data_index >= total_bits:
            # No more bits to embed, just copy the pixel
            new_pixels.append(pixel)
            continue

        # Unpack RGB values. we converted to RGB mode, so there shouldn't be alpha channel.
        r, g, b = pixel  

        # For each color channel, replace the least significant bit
        if data_index < total_bits:
            r = (r & ~1) | int(full_binary[data_index])
            # Clear LSB and set it. (r & ~1) clear the last bit. then there is '|' or
            # operator if message bit is one it puts 1 there, we get from full_binary a char and so we also convert to int.  
            data_index += 1
        if data_index < total_bits:
            g = (g & ~1) | int(full_binary[data_index])
            data_index += 1
        if data_index < total_bits:
            b = (b & ~1) | int(full_binary[data_index])
            data_index += 1

        new_pixels.append((r, g, b))

    # Safety check: if we ran out of space before encoding all bits
    if data_index < total_bits:
        raise ValueError("Message is too long for this image.")

    # Create a new image with the same size and mode
    new_img = Image.new(image.mode, image.size)
    new_img.putdata(new_pixels)  # Update the pixels with the modified ones

    return new_img  # Return the new image (not saved to file yet)


# Function to extract the hidden message from the image
def lsb_img_extract_text_from_image(image: Image.Image) -> str:
    # Make sure the image is in RGB mode
    if image.mode != 'RGB':
        image = image.convert('RGB')

    pixels = list(image.getdata())
    bit_stream = ''

    # Extract LSBs from all RGB channels
    for pixel in pixels:
        for value in pixel:  # r, g, b values
            bit_stream += str(value & 1)

    # First 32 bits represent the length of the message in bits
    length_bits = bit_stream[:32]
    message_length = int(length_bits, 2)

    # Extract the actual message bits using the length
    message_bits = bit_stream[32:32+message_length]

    # Convert the bits into text
    hidden_message = binstr_to_text(message_bits)  # unified helper
    return hidden_message

def encode_file(image_path: str, output_path: str, message: str, password: str) -> None:
    """
    Encrypts message and writes a new stego image to output_path.
    """
    ciphertext = encrypt_module.encrypt_message(password, message)
    img = Image.open(image_path)
    new_img = lsb_img_hide_text_with_length(img, ciphertext)
    new_img.save(output_path)

def decode_file(image_path: str, password: str) -> str:
    """
    Extracts and decrypts message from the image at image_path.
    """
    img = Image.open(image_path)
    encrypted_blob = lsb_img_extract_text_from_image(img)
    return encrypt_module.decrypt_message(password, encrypted_blob)