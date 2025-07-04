from PIL import Image

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