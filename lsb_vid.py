import cv2
import numpy as np
import os

def text_to_binary(text):
    return ''.join(format(ord(char), '08b') for char in text)

def int_to_32bit_binary(n):
    return format(n, '032b')

def binary_to_text(binary_string):
    chars = [binary_string[i:i+8] for i in range(0, len(binary_string), 8)]
    return ''.join(chr(int(char, 2)) for char in chars)

def get_codec(output_path):
    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".avi":
        return cv2.VideoWriter_fourcc(*'XVID')
    elif ext == ".mp4":
        return cv2.VideoWriter_fourcc(*'MJPG')  # safer for LSB than H.264/X264
    else:
        raise ValueError("Unsupported format. Use .avi or .mp4")

def lsb_video_hide_text_with_length(input_video_path, output_video_path, message):
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        raise ValueError("Could not open input video")

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    codec = get_codec(output_video_path)

    out = cv2.VideoWriter(output_video_path, codec, fps, (frame_width, frame_height))

    binary_message = int_to_32bit_binary(len(message) * 8) + text_to_binary(message)
    data_index = 0
    total_bits = len(binary_message)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        modified_frame = frame.copy()
        rows, cols, _ = frame.shape
        for row in range(rows):
            for col in range(cols):
                if data_index >= total_bits:
                    break
                pixel = frame[row, col]
                for channel in range(3):  # BGR
                    if data_index >= total_bits:
                        break
                    pixel[channel] = (pixel[channel] & ~1) | int(binary_message[data_index])
                    data_index += 1
                modified_frame[row, col] = pixel
            if data_index >= total_bits:
                break

        out.write(modified_frame)

    cap.release()
    out.release()

    if data_index < total_bits:
        raise ValueError("Message is too long to fit in this video.")

def lsb_video_extract_text_from_video(input_video_path):
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        raise ValueError("Could not open input video")

    bit_stream = ''
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        rows, cols, _ = frame.shape
        for row in range(rows):
            for col in range(cols):
                pixel = frame[row, col]
                for channel in range(3):
                    bit_stream += str(pixel[channel] & 1)

    cap.release()

    length_bits = bit_stream[:32]
    message_length = int(length_bits, 2)
    message_bits = bit_stream[32:32 + message_length]

    return binary_to_text(message_bits)
