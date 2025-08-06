import cv2  # OpenCV for video processing
import os

# Converts text into a binary string (8 bits per character)
def text_to_binary(text):
    return ''.join(format(ord(char), '08b') for char in text)

# Converts an integer (message length in bits) to a 32-bit binary string
def int_to_32bit_binary(n):
    return format(n, '032b')

# Converts binary string back to human-readable text
def binary_to_text(binary_string):
    # Break binary into chunks of 8 bits, convert to characters
    chars = [binary_string[i:i+8] for i in range(0, len(binary_string), 8)]
    return ''.join(chr(int(char, 2)) for char in chars)

# Chooses appropriate codec based on output video file extension
def get_codec(output_path):
    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".avi":
        return cv2.VideoWriter_fourcc(*'XVID')
    elif ext == ".mp4":
        return cv2.VideoWriter_fourcc(*'MJPG')  # Less compression than H.264
    else:
        raise ValueError("Unsupported format. Use .avi or .mp4")

# Hides a text message into a video using LSB encoding
def lsb_video_hide_text_with_length(input_video_path, output_video_path, message):
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        raise ValueError("Could not open input video")

    # Extract frame properties from original video
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    codec = get_codec(output_video_path)

    # Prepare the writer to create output video
    out = cv2.VideoWriter(output_video_path, codec, fps, (frame_width, frame_height))

    # Convert the message to binary and prepend its 32-bit length
    binary_message = int_to_32bit_binary(len(message) * 8) + text_to_binary(message)
    data_index = 0
    total_bits = len(binary_message)

    # Process each frame
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break  # No more frames

        # Copy the frame to modify
        modified_frame = frame.copy()
        rows, cols, _ = frame.shape

        # Traverse each pixel in the frame
        for row in range(rows):
            for col in range(cols):
                if data_index >= total_bits:
                    break  # Stop once the full message is embedded

                pixel = frame[row, col]  # Get the pixel (BGR)

                # Modify each color channel (Blue, Green, Red)
                for channel in range(3):
                    if data_index >= total_bits:
                        break

                    # Embed one bit from the message in the LSB of this channel
                    pixel[channel] = (pixel[channel] & ~1) | int(binary_message[data_index])
                    data_index += 1

                modified_frame[row, col] = pixel  # Save modified pixel

            if data_index >= total_bits:
                break

        out.write(modified_frame)  # Save modified frame

    cap.release()
    out.release()

    # If we didn't finish embedding, message was too long
    if data_index < total_bits:
        raise ValueError("Message is too long to fit in this video.")

# Extracts hidden text message from a video using LSB decoding
def lsb_video_extract_text_from_video(input_video_path):
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        raise ValueError("Could not open input video")

    bit_stream = ''  # To store all the extracted bits

    # Read each frame and extract LSBs
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break  # No more frames

        rows, cols, _ = frame.shape

        for row in range(rows):
            for col in range(cols):
                pixel = frame[row, col]
                for channel in range(3):
                    # Extract the LSB of each color channel
                    bit_stream += str(pixel[channel] & 1)

    cap.release()

    # First 32 bits = message length (in bits)
    length_bits = bit_stream[:32]
    message_length = int(length_bits, 2)

    # Extract the next 'message_length' bits
    message_bits = bit_stream[32:32 + message_length]

    # Convert back to readable text
    return binary_to_text(message_bits)