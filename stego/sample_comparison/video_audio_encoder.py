import os
import subprocess
import tempfile
import numpy as np
import scipy.io.wavfile as wav
import math
import argparse
from dataclasses import dataclass, field
from typing import Optional, List
from stego.utils.bit_utils import bytes_to_bits
from stego.utils import encrypt as encrypt_module

# Internal defaults (not intended to be imported by the app)
_DEFAULT_FRAME_DURATION = 0.1
_DEFAULT_COMPARE_FRACTION = 0.5
_DEFAULT_HEADER = "1010101010101010"
_DEFAULT_FOOTER = "0101010101010101"
# Safe ranges/guards for the sample-comparison algo
SAFE_CF_MIN = 0.05   # avoid degenerate 0 or near-0
SAFE_CF_MAX = 0.95   # avoid compare idx at or past frame end
MIN_FRAME_SIZE_DEFAULT = 150  # encoder will never go below this

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

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
SECRET_MESSAGE = "Message to test"

# Try to find a frame size that can accommodate the required bits, halving if needed.
def find_suitable_frame_size(total_samples: int, sr: int, frame_duration: float, required_bits: int, min_frame_size: int = MIN_FRAME_SIZE_DEFAULT) -> tuple[bool, int, float, int]:
    """
    Returns: (ok, chosen_frame_size, chosen_frame_duration_seconds, max_bits)
    Halving logic: start with frame_duration and keep halving until finding a 
    frame size that can fit the required bits, or reach min_frame_size, 150 by default.
    """
    frame_size = max(1, int(sr * frame_duration))
    while frame_size >= min_frame_size:
        max_bits = math.ceil(total_samples / frame_size)
        if max_bits >= required_bits:
            return True, frame_size, frame_size / sr, max_bits
        frame_size //= 2
    return False, -1, -1.0, 0

def select_frame_size_with_fallback(
    total_samples: int,
    sr: int,
    required_bits: int,
    requested_frame_duration: float,
    *,
    default_frame_duration: float = _DEFAULT_FRAME_DURATION,
    min_frame_size: int = MIN_FRAME_SIZE_DEFAULT,
) -> tuple[bool, int, float, int, bool]:
    """
    Strategy:
      - First try the user-requested frame_duration.
      - If it can't fit the payload, start from the default_frame_duration (0.1s)
        and keep halving (0.05, 0.025, ...) until it fits or we hit min_frame_size.
    Returns: (ok, frame_size, frame_duration_sec, max_bits, used_fallback)
    """
    # 1) Try the requested frame_duration as-is
    ok, fs, fd, max_bits = find_suitable_frame_size(
        total_samples, sr, requested_frame_duration, required_bits, min_frame_size
    )
    if ok:
        return True, fs, fd, max_bits, False

    # 2) Fallback: start at default and halve
    ok2, fs2, fd2, max_bits2 = find_suitable_frame_size(
        total_samples, sr, default_frame_duration, required_bits, min_frame_size
    )
    return ok2, fs2, fd2, max_bits2, True

# Encode bits into audio data by modifying samples
def encode_bits_to_audio(data, bits, frame_size, compare_distance):
    channels = 1 if data.ndim == 1 else data.shape[1] # Mono or Stereo
    data_mod = data.copy() # Avoid modifying original data
    total_samples = data_mod.shape[0] # Number of samples (per channel)
    for i, bit in enumerate(bits):
        frame_start = i * frame_size
        frame_end = frame_start + frame_size
        if frame_start >= total_samples:
            print(f"Not enough audio data to encode all bits. Stopping at bit index {i}.")
            break
        frame_end = min(frame_end, total_samples)
        for ch in range(channels):
            # Extract the current frame for the channel
            frame = data_mod[frame_start:frame_end] if channels == 1 else data_mod[frame_start:frame_end, ch]
            actual_compare_distance = min(compare_distance, len(frame) - 1) # Ensure within frame
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

@dataclass
class VideoEncodeOptions:
    frame_duration: Optional[float] = None
    compare_fraction: Optional[float] = None
    header_bits: Optional[str] = None
    footer_bits: Optional[str] = None

@dataclass
class EncodeResult:
    output_path: str
    frame_size: int
    frame_duration: float
    compare_fraction: float
    header: str
    footer: str
    # Display helpers: "DEFAULT" if unchanged, otherwise the actual value (as string)
    header_display: str
    footer_display: str
    compare_fraction_display: str
    # Extra info
    total_bits: int
    max_bits: int
    sample_rate: int
    total_samples: int
    warnings: List[str] = field(default_factory=list)

def encode_message_in_video_details(
    input_video: str,
    output_video: Optional[str] = None,
    message: Optional[str] = None,
    *,
    frame_duration: float = _DEFAULT_FRAME_DURATION,
    compare_fraction: float = _DEFAULT_COMPARE_FRACTION,
    header: str = _DEFAULT_HEADER,
    footer: str = _DEFAULT_FOOTER,
) -> EncodeResult:
    """
    Encode a message into the audio track and return rich details about the encoding.
    Does the same work as encode_message_in_video, but returns an EncodeResult instead of a path.
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

        # Extracting audio, using 48kHz, PCM 16-bit WAV to ensure compatibility
        cmd = [
            "ffmpeg", "-y", "-i", input_video, "-vn",
            "-acodec", "pcm_s16le", "-ar", "48000", audio_wav
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Read audio
        sr, data = wav.read(audio_wav)
        total_samples = data.shape[0]

        # Prepare warnings collected at this level
        local_warnings: List[str] = []

        # Clamp compare_fraction to safe range
        cf_used = _clamp(compare_fraction, SAFE_CF_MIN, SAFE_CF_MAX)
        if abs(cf_used - compare_fraction) > 1e-12:
            local_warnings.append(f"compare_fraction clamped to {cf_used} (was {compare_fraction}).")

        # Capacity check and frame selection (new fallback strategy)
        min_frame_size = MIN_FRAME_SIZE_DEFAULT
        need_bits = len(all_bits)
        ok, frame_size, frame_duration_real, max_bits, used_fallback = select_frame_size_with_fallback(
            total_samples=total_samples,
            sr=sr,
            required_bits=need_bits,
            requested_frame_duration=frame_duration,
            default_frame_duration=_DEFAULT_FRAME_DURATION,
            min_frame_size=min_frame_size,
        )

        if not ok:  # Not enough capacity even with smallest allowed frame size
            raise ValueError(
                (
                    "Message is too large for the given video audio. "
                    f"Needed {need_bits} bits more "
                    f"even at frame_size={min_frame_size} (~{min_frame_size/sr:.8f}s)."
                )
            )

        # If we had to adjust from the requested duration (or we fell back), warn
        requested_fs = max(1, int(sr * frame_duration))
        if used_fallback or frame_size != requested_fs:
            local_warnings.append(
                f"Frame duration adjusted from {frame_duration:.8f}s to "
                f"{frame_duration_real:.8f}s (frame_size={frame_size}) to fit payload."
            )

        # Compute compare distance safely within [1, frame_size-1]
        compare_distance = int(frame_size * cf_used)
        safe_cd = min(max(compare_distance, 1), frame_size - 1)
        if safe_cd != compare_distance:
            local_warnings.append(
                f"compare_distance adjusted to {safe_cd} (from {compare_distance}) for frame_size {frame_size}."
            )
        compare_distance = safe_cd

        # Embed
        data_encoded = encode_bits_to_audio(data, all_bits, frame_size, compare_distance)
        wav.write(stego_wav, sr, data_encoded)

        # Mux back
        cmd = [
            "ffmpeg", "-y", "-i", input_video, "-i", stego_wav,
            "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
            "-c:a", "pcm_s16le", "-movflags", "+faststart", output_video
        ]
        subprocess.run(cmd, check=True)

    # Build display markers so the app doesn't need to know defaults
    header_display = "DEFAULT" if header == _DEFAULT_HEADER else header
    footer_display = "DEFAULT" if footer == _DEFAULT_FOOTER else footer
    is_default_cf = abs(compare_fraction - _DEFAULT_COMPARE_FRACTION) <= 1e-12
    compare_fraction_display = "DEFAULT" if is_default_cf else f"{compare_fraction}"

    return EncodeResult(
        output_path=output_video,
        frame_size=frame_size,
        frame_duration=frame_duration_real,
        compare_fraction=cf_used,
        header=header,
        footer=footer,
        header_display=header_display,
        footer_display=footer_display,
        compare_fraction_display=compare_fraction_display,
        total_bits=need_bits,
        max_bits=max_bits,
        sample_rate=sr,
        total_samples=total_samples,
        warnings=local_warnings,  # send back any auto-adjust messages
    )

def encode_video_message(
    input_video: str,
    output_video: Optional[str],
    plaintext_message: str,
    password: str,
    options: Optional[VideoEncodeOptions] = None,
) -> EncodeResult:
    """
    High-level API: encrypts plaintext_message with password,
    validates/normalizes options, and returns structured result.
    """
    # Defaults
    fd = _DEFAULT_FRAME_DURATION
    cf = _DEFAULT_COMPARE_FRACTION
    header = _DEFAULT_HEADER
    footer = _DEFAULT_FOOTER
    warnings: List[str] = []

    # Normalize options if provided
    if options:
        if options.frame_duration is not None:
            try:
                fd = float(options.frame_duration)
            except Exception:
                warnings.append("Invalid frame_duration; using default.")
        if options.compare_fraction is not None:
            try:
                cf = float(options.compare_fraction)
                cf_clamped = _clamp(cf, SAFE_CF_MIN, SAFE_CF_MAX)
                if abs(cf_clamped - cf) > 1e-12:
                    warnings.append(f"compare_fraction clamped to {cf_clamped} (was {cf}).")
                cf = cf_clamped
                # assign after clamping
                cf = cf_clamped
            except Exception:
                warnings.append("Invalid compare_fraction; using default.")
        if options.header_bits:
            hb = options.header_bits.strip()
            if len(hb) >= 16 and len(hb) % 8 == 0 and all(c in "01" for c in hb):
                header = hb
            else:
                warnings.append("Invalid header; using default.")
        if options.footer_bits:
            fb = options.footer_bits.strip()
            if len(fb) >= 16 and len(fb) % 8 == 0 and all(c in "01" for c in fb):
                footer = fb
            else:
                warnings.append("Invalid footer; using default.")

    # Encrypt the plaintext here (keeps app simple and consistent with other encoders)
    ciphertext = encrypt_module.encrypt_message(password, plaintext_message)

    # Call the detailed encoder with the encrypted payload
    res = encode_message_in_video_details(
        input_video=input_video,
        output_video=output_video,
        message=ciphertext,
        frame_duration=fd,
        compare_fraction=cf,
        header=header,
        footer=footer,
    )
    # Attach normalization warnings
    res.warnings.extend(warnings)
    return res

def encode_message_in_video(
    input_video: str,
    output_video: Optional[str] = None,
    message: Optional[str] = None,
    *,
    frame_duration: float = _DEFAULT_FRAME_DURATION,
    compare_fraction: float = _DEFAULT_COMPARE_FRACTION,
    header: str = _DEFAULT_HEADER,
    footer: str = _DEFAULT_FOOTER,
) -> str:
    """
    Backward-compatible wrapper that returns only the output path.
    """
    res = encode_message_in_video_details(
        input_video=input_video,
        output_video=output_video,
        message=message,
        frame_duration=frame_duration,
        compare_fraction=compare_fraction,
        header=header,
        footer=footer,
    )
    print(f"Using frame size: {res.frame_size} samples ({res.frame_duration:.8f} seconds per frame).")
    print("Make sure to use this frame size or duration when decoding!")
    print(f"Done. Output: {res.output_path}")
    return res.output_path

def main():
    parser = argparse.ArgumentParser(description="Embed a message in the audio of a video file.")
    parser.add_argument("input_video", help=".avi or .mkv input video file")
    parser.add_argument("output_video", nargs="?", help="Optional output path")
    parser.add_argument("--frame_duration", type=float, default=_DEFAULT_FRAME_DURATION)
    parser.add_argument("--compare_fraction", type=float, default=_DEFAULT_COMPARE_FRACTION)
    parser.add_argument("--header", type=str, default=_DEFAULT_HEADER)
    parser.add_argument("--footer", type=str, default=_DEFAULT_FOOTER)
    parser.add_argument("--message", type=str, default=None)
    args = parser.parse_args()
    res = encode_message_in_video_details(
        input_video=args.input_video,
        output_video=args.output_video,
        message=args.message,
        frame_duration=args.frame_duration,
        compare_fraction=args.compare_fraction,
        header=args.header,
        footer=args.footer,
    )
    print(f"Using frame size: {res.frame_size} samples ({res.frame_duration:.8f} seconds per frame).")
    print("Make sure to use this frame size or duration when decoding!")
    print(f"Done. Output: {res.output_path}")


if __name__ == "__main__":
    main()