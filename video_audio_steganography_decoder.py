import os
import sys
import tempfile
import subprocess
import numpy as np
import scipy.io.wavfile as wav

"""
This script decodes a message hidden in the audio of a video file using steganography techniques.
It extracts the audio, analyzes the samples, and retrieves the hidden message based on specified header and footer bits.
It should be run after encoding a message into the audio of a video file using the corresponding encoder script.
The message is expected to be encoded in a specific format, with a header and footer to mark the start and end of the message.
The message would be printed to the console after decoding.
"""

def bits_to_bytes(bits):
    chars = []
    for b in range(0, len(bits), 8):
        byte_bits = bits[b:b+8]
        if len(byte_bits) < 8:
            break
        value = 0
        for bit in byte_bits:
            value = (value << 1) | bit
        chars.append(value)
    return bytearray(chars)

def find_header_footer(bitstream, header_bits, footer_bits):
    header_len = len(header_bits)
    footer_len = len(footer_bits)
    for i in range(len(bitstream) - header_len - footer_len):
        if bitstream[i:i+header_len] == header_bits:
            for j in range(i+header_len, len(bitstream) - footer_len + 1):
                if bitstream[j:j+footer_len] == footer_bits:
                    return i+header_len, j
    return None, None

def decode_audio_stego(
    wav_in,
    frame_duration=0.1,
    compare_fraction=0.5,
    header_bits=[1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0],
    footer_bits=[0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1],
    threshold=0
):
    sr, data = wav.read(wav_in)
    if data.ndim > 1:
        data_mono = data[:, 0]
    else:
        data_mono = data
    frame_size = int(sr * frame_duration)
    compare_distance = int(frame_size * compare_fraction)
    n_frames = len(data_mono) // frame_size
    bits = []
    for i in range(n_frames):
        frame_start = i * frame_size
        frame = data_mono[frame_start:frame_start+frame_size]
        if len(frame) < compare_distance + 1:
            continue
        idx1 = 0
        idx2 = compare_distance
        if abs(frame[idx2] - frame[idx1]) <= threshold:
            bits.append(1)
        else:
            bits.append(0)
    h_start, h_end = find_header_footer(bits, header_bits, footer_bits)
    if h_start is None or h_end is None:
        print("Header or footer not found.")
        return None
    payload_bits = bits[h_start:h_end]
    message_bytes = bits_to_bytes(payload_bits)
    try:
        message = message_bytes.decode()
    except UnicodeDecodeError:
        message = message_bytes
    print(f"Decoded message: {message}")
    return message

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Decode a message from the audio of a video file.")
    parser.add_argument("input_video", help=".avi or .mkv input video file")
    parser.add_argument("--frame_duration", type=float, default=0.1, help="Frame duration in seconds")
    parser.add_argument("--compare_fraction", type=float, default=0.5, help="Compare distance as fraction of frame")
    parser.add_argument("--header", type=str, default="1010101010101010", help="Header bits")
    parser.add_argument("--footer", type=str, default="0101010101010101", help="Footer bits")
    parser.add_argument("--threshold", type=int, default=0, help="Equality threshold")
    args = parser.parse_args()

    header_bits = [int(b) for b in args.header]
    footer_bits = [int(b) for b in args.footer]

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_wav = os.path.join(tmpdir, "audio.wav")
        print("Extracting audio...")
        cmd = [
            "ffmpeg", "-y", "-i", args.input_video, "-vn",
            "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2", audio_wav
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        decode_audio_stego(
            wav_in=audio_wav,
            frame_duration=args.frame_duration,
            compare_fraction=args.compare_fraction,
            header_bits=header_bits,
            footer_bits=footer_bits,
            threshold=args.threshold
        )

if __name__ == "__main__":
    main()