import os
import subprocess
import tempfile
import numpy as np
import scipy.io.wavfile as wav

# SET THE MESSAGE TO ENCODE HERE:
SECRET_MESSAGE = "hello"

"""
The idea is to embed a message in the audio of a video file by modifying the audio samples.
There 
The message is converted to bits, and these bits are encoded into the audio samples
by comparing samples in a frame and modifying them based on the bit value.
The audio samples are modified in such a way that the changes are imperceptible to the human ear.
The size of each frame is by default 0.1 seconds, and the compare distance is set to half of the frame size.
The header and footer bits are added to the message to mark the start and end of the message, the defaults are
"1010101010101010" for the header and "0101010101010101" for the footer.
There should be 48000 samples per second in the audio, so a frame size of 4800 samples corresponds to 0.1 seconds. 
This can be adjusted with the --frame_duration argument.
"""

""" Convert bytes to a list of bits. Return an array of bits (0s and 1s) that represents the message """
def bytes_to_bits(byteseq):
    if isinstance(byteseq, str):
        byteseq = byteseq.encode()
    bits = []
    for b in byteseq:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    return bits

def encode_bits_to_audio(data, bits, frame_size, compare_distance):
    """
    Modify audio data in-place to encode bits using sample comparison.
    Works for mono and stereo (all channels).
    """
    channels = 1 if data.ndim == 1 else data.shape[1]
    data_mod = data.copy()
    #print(f"there are", len(bits), "bits to encode in the audio data with frame size", frame_size, "and compare distance", compare_distance, "samples.")
    #print(f"there are", channels, "channels in the audio")
    for i, bit in enumerate(bits):
        frame_start = i * frame_size
        frame_end = frame_start + frame_size
        #print(f"Frame start {frame_start}, frame end {frame_end-1} for bit index {i} with value {bit}")
        if frame_end > data_mod.shape[0]: # Check if we have enough audio data
            print(f"Not enough audio data to encode all bits. Stopping at bit index {i}.")
            break
        for ch in range(channels):
            frame = data_mod[frame_start:frame_end] if channels == 1 else data_mod[frame_start:frame_end, ch]
            idx1 = 0
            idx2 = compare_distance
            if bit == 1:
                frame[idx2] = frame[idx1]
                #print(f"Encoding bit {bit} at index {i}, channel {ch}: setting frame[{idx2}] = frame[{idx1}] with value {frame[idx1]}")
            else:
                if frame[idx2] == frame[idx1]:
                    if frame[idx2] < np.iinfo(data_mod.dtype).max:
                        frame[idx2] = frame[idx1] + 1
                    else:
                        frame[idx2] = frame[idx1] - 1
                    """
                    print(f"Encoding bit {bit} at index {i}, channel {ch}: changing frame[{idx2}] to {frame[idx2]}")
                else:
                    print(
                        f"Encoding bit {bit} at index {i}, channel {ch}: frame[{idx2}] and frame[{idx1}] already different: values are {frame[idx2]} and {frame[idx1]}")
                    """
            if channels == 1: # Mono audio
                data_mod[frame_start:frame_end] = frame
            else:
                data_mod[frame_start:frame_end, ch] = frame
    return data_mod

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Embed a message in the audio of a video file.")
    parser.add_argument("input_video", help=".avi or .mkv input video file")
    parser.add_argument("output_video", help="Output video file (same format as input)")
    parser.add_argument("--frame_duration", type=float, default=0.1, help="Frame duration in seconds")
    parser.add_argument("--compare_fraction", type=float, default=0.5, help="Compare distance as fraction of frame (0.5=halfway)")
    parser.add_argument("--header", type=str, default="1010101010101010", help="Header bits")
    parser.add_argument("--footer", type=str, default="0101010101010101", help="Footer bits")
    parser.add_argument("--threshold", type=int, default=0, help="Equality threshold")
    args = parser.parse_args()

    header_bits = [int(b) for b in args.header] # Convert header bits to integers
    footer_bits = [int(b) for b in args.footer] # Convert footer bits to integers
    secret_bits = bytes_to_bits(SECRET_MESSAGE) # Convert the secret message to bits
    all_bits = header_bits + secret_bits + footer_bits # Combine header, message, and footer bits
    """
    print(f"Header bits: {header_bits}")
    print(f"Secret message bits: {secret_bits}")
    print(f"Footer bits: {footer_bits}")
    """

    with tempfile.TemporaryDirectory() as tmpdir: # Create a temporary directory for intermediate files
        audio_wav = os.path.join(tmpdir, "audio.wav") # Temporary audio file
        stego_wav = os.path.join(tmpdir, "stego.wav") # Temporary stego audio file
        print("Extracting audio...")
        cmd = [
            "ffmpeg", "-y", "-i", args.input_video, "-vn",
            "-acodec", "pcm_s16le", # <-- Use lossless PCM audio
            "-ar", "48000", audio_wav
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print("Embedding message...")
        sr, data = wav.read(audio_wav)
        """
        if data.ndim == 1: # Mono audio
            print("First 100 samples (mono):", data[:100]) # Print first 100 samples
        else: # Stereo audio
            print("First 100 samples (stereo):") # Print first 100 samples for each channel
            print("left ", data[:100, 0])
            print("right ", data[:100, 1])
        """
        frame_size = int(sr * args.frame_duration)
        compare_distance = int(frame_size * args.compare_fraction)
        data_encoded = encode_bits_to_audio(data, all_bits, frame_size, compare_distance)
        wav.write(stego_wav, sr, data_encoded)

        print("Muxing audio and video...")
        cmd = [
            "ffmpeg", "-y", "-i", args.input_video, "-i", stego_wav,
            "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
            "-c:a", "pcm_s16le",  # <-- Use lossless PCM audio
            "-movflags", "+faststart", args.output_video
        ]
        subprocess.run(cmd, check=True)
        print(f"Done. Output: {args.output_video}")

if __name__ == "__main__":
    main()