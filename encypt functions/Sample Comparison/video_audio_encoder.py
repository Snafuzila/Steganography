import os
import subprocess
import tempfile
import numpy as np
import scipy.io.wavfile as wav
import math
import argparse

"""
This script embeds a secret message into the audio track of a video file using steganography techniques.
It extracts the audio from the video, modifies the audio samples to encode the message, and then reintegrates the
modified audio back into the video.

Usage:
- CLI with an explicit message:
    python video_audio_encoder.py input.mkv output.mkv --message "abcde" (with the quotes)

- CLI using the default SECRET_MESSAGE (no need to type it every time):
    python video_audio_encoder.py input.mkv output.mkv

- CLI with automatic output name (append _output and de-duplicate with (1), (2), ...):
    python video_audio_encoder.py input.mkv
    # Produces input_output.mkv, or input_output(1).mkv if the first exists, etc.

- Programmatic use from Python (output path optional):
    from video_audio_encoder import encode_message_in_video
    encode_message_in_video("input.mkv")  # auto-generates output path and uses SECRET_MESSAGE
    encode_message_in_video("input.mkv", "custom_output.mkv", message="hello")
"""

# DEFAULT MESSAGE: used when --message is omitted or when message=None in function calls.
SECRET_MESSAGE = "A longer secret message that is hidden in the audio track of a video file using steganography techniques."

def bytes_to_bits(byteseq):
    if isinstance(byteseq, str):
        byteseq = byteseq.encode()
    bits = []
    for b in byteseq:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    return bits


def encode_bits_to_audio(data, bits, frame_size, compare_distance):
    channels = 1 if data.ndim == 1 else data.shape[1]
    data_mod = data.copy()
    total_samples = data_mod.shape[0]
    for i, bit in enumerate(bits):
        frame_start = i * frame_size
        frame_end = frame_start + frame_size
        if frame_start >= total_samples:
            print(f"Not enough audio data to encode all bits. Stopping at bit index {i}.")
            break
        frame_end = min(frame_end, total_samples)
        for ch in range(channels):
            frame = data_mod[frame_start:frame_end] if channels == 1 else data_mod[frame_start:frame_end, ch]
            actual_compare_distance = min(compare_distance, len(frame) - 1)
            idx1 = 0
            idx2 = actual_compare_distance
            if len(frame) < 2:
                continue  # Not enough samples to encode this bit
            if bit == 1:
                frame[idx2] = frame[idx1]
            else:
                if frame[idx2] == frame[idx1]:
                    if frame[idx2] < np.iinfo(data_mod.dtype).max:
                        frame[idx2] = frame[idx1] + 1
                    else:
                        frame[idx2] = frame[idx1] - 1
            if channels == 1:
                data_mod[frame_start:frame_end] = frame
            else:
                data_mod[frame_start:frame_end, ch] = frame
    return data_mod


def _generate_default_output_path(input_video_path: str, suffix: str = "_output") -> str:
    """
    Given an input video path, generate an output path in the same directory by appending
    `suffix` before the file extension. If that path already exists, append (1), (2), etc.
    Example:
      input: /path/video.mkv -> /path/video_output.mkv (or /path/video_output(1).mkv if needed)
    """
    directory, filename = os.path.split(input_video_path)
    base, ext = os.path.splitext(filename)
    # Keep the same extension as input. If there's no extension, keep it extension-less.
    initial_name = f"{base}{suffix}{ext}"
    candidate = os.path.join(directory, initial_name)

    if not os.path.exists(candidate):
        return candidate

    n = 1
    while True:
        candidate_n = os.path.join(directory, f"{base}{suffix}({n}){ext}")
        if not os.path.exists(candidate_n):
            return candidate_n
        n += 1


def encode_message_in_video(
    input_video: str,
    output_video: str | None = None,
    message: str | None = None,
    *,
    frame_duration: float = 0.1,
    compare_fraction: float = 0.5,
    header: str = "1010101010101010",
    footer: str = "0101010101010101",
) -> str:
    """
    Encode a message into the audio track of a video and write to output_video.
    If message is None, uses SECRET_MESSAGE.
    If output_video is None, auto-generates a path based on input video name with '_output',
    avoiding overwrites by appending (1), (2), etc.

    Returns the final output path used.
    """
    # Decide the message
    if message is None:
        message = SECRET_MESSAGE

    # Decide the output path
    if output_video is None:
        output_video = _generate_default_output_path(input_video)

    header_bits = [int(b) for b in header]
    footer_bits = [int(b) for b in footer]
    secret_bits = bytes_to_bits(message)
    all_bits = header_bits + secret_bits + footer_bits

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_wav = os.path.join(tmpdir, "audio.wav")
        stego_wav = os.path.join(tmpdir, "stego.wav")

        print("Extracting audio...")
        cmd = [
            "ffmpeg", "-y", "-i", input_video, "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "48000", audio_wav
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print("Embedding message...")
        sr, data = wav.read(audio_wav)
        total_samples = data.shape[0]

        # Start with initial frame size and halve until message fits or min frame size reached
        initial_frame_size = int(sr * frame_duration)
        frame_size = initial_frame_size
        min_frame_size = 150  # as requested
        found_frame_size = False

        while frame_size >= min_frame_size:
            max_bits = math.ceil(total_samples / frame_size)
            if len(all_bits) <= max_bits:
                found_frame_size = True
                break
            frame_size = frame_size // 2  # halve frame size and try again

        if not found_frame_size:
            print(
                f"Message is too large for the given video, even with minimum frame size "
                f"({min_frame_size} samples, {min_frame_size/sr:.8f} seconds)."
            )
            print("Try a shorter message or a longer video/audio.")
            return output_video

        frame_duration_real = frame_size / sr
        compare_distance = int(frame_size * compare_fraction)
        print(f"Using frame size: {frame_size} samples ({frame_duration_real:.8f} seconds per frame).")
        print(f"Make sure to use this frame size ({frame_size}) or frame duration ({frame_duration_real:.8f} seconds) when decoding!")

        data_encoded = encode_bits_to_audio(data, all_bits, frame_size, compare_distance)
        wav.write(stego_wav, sr, data_encoded)

        print("Muxing audio and video...")
        cmd = [
            "ffmpeg", "-y", "-i", input_video, "-i", stego_wav,
            "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
            "-c:a", "pcm_s16le",
            "-movflags", "+faststart", output_video
        ]
        subprocess.run(cmd, check=True)
        print(f"Done. Output: {output_video}")

    return output_video


def main():
    parser = argparse.ArgumentParser(description="Embed a message in the audio of a video file.")
    parser.add_argument("input_video", help=".avi or .mkv input video file")
    # Make output_video optional; if omitted, we auto-generate a name based on input.
    parser.add_argument(
        "output_video",
        nargs="?",
        help="Output video file (same format as input). If omitted, will use <input>_output.<ext> (or add (1), (2), ... if needed)."
    )
    parser.add_argument("--frame_duration", type=float, default=0.1,
                        help="Frame duration in seconds (initial value; will be halved if needed)")
    parser.add_argument("--compare_fraction", type=float, default=0.5,
                        help="Compare distance as fraction of frame (0.5=halfway)")
    parser.add_argument("--header", type=str, default="1010101010101010", help="Header bits (must be at least 16 chars and divisible by 8)")
    parser.add_argument("--footer", type=str, default="0101010101010101", help="Footer bits (must be at least 16 chars and divisible by 8)")
    parser.add_argument(
        "--message",
        type=str,
        default=None,
        help="The message to encode (omit to use SECRET_MESSAGE)."
    )
    args = parser.parse_args()

    encode_message_in_video(
        input_video=args.input_video,
        output_video=args.output_video,  # None -> auto-generate with _output and deduplicate
        message=args.message,            # None -> use SECRET_MESSAGE
        frame_duration=args.frame_duration,
        compare_fraction=args.compare_fraction,
        header=args.header,
        footer=args.footer,
    )


if __name__ == "__main__":
    main()