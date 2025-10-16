# main_stego.py abcd

# Main script for steganography project integrating image, audio, video, and text hiding methods.
# Uses encryption from encrypt.py for all methods.
# Inputs from 'examples' directory, outputs to 'outputs' directory.
# Automatically detects file type for decoding, or allows selection/detection for encoding.

import os
from PIL import Image
import subprocess
import tempfile
import numpy as np
import scipy.io.wavfile as wav  # Note: renamed if needed, but not conflicting here

# Import functions from provided files
from encrypt_functions.lsb.lsb_img import lsb_img_hide_text_with_length, lsb_img_extract_text_from_image
from encrypt_functions.lsb.lsb_wav import encode_message, decode_message
from encrypt_functions.whitespace.mainWhiteS import embed_message, extract_message
from encrypt_functions.Sample_Comparison.video_audio_encoder import encode_message_in_video
from encrypt_functions.Sample_Comparison.video_audio_decoder import decode_audio_stego
from encrypt_functions.encrypt import encrypt_message, decrypt_message

# Directories
BASE_DIR = os.path.dirname(__file__)
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
if not os.path.exists(OUTPUTS_DIR):
    os.makedirs(OUTPUTS_DIR)

if __name__ == "__main__":
    print("Steganography Tool with AES Encryption")
    print("1. Encode (hide message)")
    print("2. Decode (extract and decrypt message)")
    choice = input("Choose: ").strip()

    if choice == '1':
        # Encode
        print("\nChoose file type:")
        print("1. Image")
        print("2. Audio")
        print("3. Video")
        print("4. Text")
        print("5. Detect")
        type_choice = input("> ").strip()
        type_map = {'1': 'image', '2': 'audio', '3': 'video', '4': 'text', '5': 'detect'}
        file_type = type_map.get(type_choice, 'detect')

        input_file = input("Enter input file name (with extension, inside 'examples'): ").strip()
        input_path = os.path.join(EXAMPLES_DIR, input_file)
        if not os.path.exists(input_path):
            print("File not found.")
            exit()

        if file_type == 'detect':
            ext = os.path.splitext(input_file)[1].lower()
            if ext in ['.png', '.jpg', '.jpeg', '.bmp']:
                file_type = 'image'
            elif ext == '.wav':
                file_type = 'audio'
            elif ext in ['.mkv', '.avi', '.mp4']:
                file_type = 'video'
            elif ext in ['.txt']:
                file_type = 'text'
            else:
                print("Unknown file type.")
                exit()

        print(f"\nDetected/Selected: {file_type.capitalize()}")

        # Show algorithm
        if file_type == 'image':
            print("Algorithm: Least Significant Bit (LSB) substitution in RGB channels with 32-bit length header.")
        elif file_type == 'audio':
            print("Algorithm: Least Significant Bit (LSB) substitution in audio samples (1 bit per sample) with 32-bit length header.")
        elif file_type == 'video':
            print("Algorithm: Custom frame-based sample equality/difference in video's audio track, with binary header/footer markers.")
        elif file_type == 'text':
            print("Algorithm: Whitespace steganography (spaces for 0, tabs for 1) at the end of text lines.")

        message = input("\nEnter message to hide: ")
        password = input("Enter password for AES encryption: ")
        encrypted_blob = encrypt_message(password, message)
        print("Message encrypted using AES.")

        output_file = input("Enter output file name (with extension, inside 'outputs'; default: stego_<input>): ").strip() or f"stego_{input_file}"
        output_path = os.path.join(OUTPUTS_DIR, output_file)

        if file_type == 'image':
            img = Image.open(input_path)
            stego_img = lsb_img_hide_text_with_length(img, encrypted_blob)
            stego_img.save(output_path)
        elif file_type == 'audio':
            encode_message(input_path, encrypted_blob, output_path)
        elif file_type == 'video':
            encode_message_in_video(input_path, output_video=output_path, message=encrypted_blob)
        elif file_type == 'text':
            embed_message(input_path, output_path, encrypted_blob)

        print(f"Stego file saved to {output_path}")

    elif choice == '2':
        # Decode
        input_file = input("\nEnter stego file path (with extension): ").strip()
        if not os.path.exists(input_file):
            print("File not found.")
            exit()

        ext = os.path.splitext(input_file)[1].lower()
        if ext in ['.png', '.bmp']:
            file_type = 'image'
        elif ext == '.wav':
            file_type = 'audio'
        elif ext in ['.mkv', '.avi', '.mov']:
            file_type = 'video'
        elif ext in ['.txt', '.html', '.css']:
            file_type = 'text'
        else:
            print("Unknown file type.")
            exit()

        print(f"\nDetected: {file_type.capitalize()}")

        extracted_blob = None
        if file_type == 'image':
            img = Image.open(input_file)
            extracted_blob = lsb_img_extract_text_from_image(img)
        elif file_type == 'audio':
            extracted_blob = decode_message(input_file, save_to_file=False)
        elif file_type == 'video':
            with tempfile.TemporaryDirectory() as tmpdir:
                audio_wav = os.path.join(tmpdir, "audio.wav")
                cmd = [
                    "ffmpeg", "-y", "-i", input_file, "-vn",
                    "-acodec", "pcm_s16le", "-ar", "48000", audio_wav
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                extracted_blob = decode_audio_stego(audio_wav)
        elif file_type == 'text':
            extracted_blob = extract_message(input_file)

        if extracted_blob:
            print("Extracted encrypted data.")
            password = input("Enter password for AES decryption: ")
            try:
                decrypted = decrypt_message(password, extracted_blob)
                print("\nDecrypted message:")
                print(decrypted)
            except Exception as e:
                print("Decryption failed. Wrong password or corrupted data?")
                print(e)
        else:
            print("No hidden message found or extraction failed.")

    else:
        print("Invalid choice.")