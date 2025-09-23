"""
main.py
-------

Command‑line interface for the audio steganography project.  This
script allows users to hide a message inside a 16‑bit mono WAV file or
to extract a hidden message from a stego WAV.  It wraps the
high‑level functions defined in :mod:`stego_core` and provides a
friendly interface with helpful error messages.

Usage examples:

```
# Embed a literal message using 2 LSBs
python main.py encode -i input.wav -o output.wav -m "סוד סודי ביותר" -n 2

# Embed a message from a text file using the default 1 LSB
python main.py encode -i input.wav -o output.wav -f secret.txt

# Decode a message
python main.py decode -i output.wav -n 2
```

The program will prompt for a password during both encoding and
decoding.  Decoded messages are optionally saved alongside the audio
file with a ``_decoded.txt`` suffix.
"""

from __future__ import annotations

import argparse
import sys

from .stego_core import encode_message, decode_message


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Hide or reveal a secret message in a WAV audio file using LSB steganography and AES‑256 encryption."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Encoder
    enc_parser = subparsers.add_parser("encode", help="embed a message into an audio file")
    enc_parser.add_argument(
        "-i",
        "--input",
        dest="input_path",
        required=True,
        help="path to the cover audio (16‑bit mono WAV)"
    )
    enc_parser.add_argument(
        "-o",
        "--output",
        dest="output_path",
        required=True,
        help="path for the stego audio"
    )
    group = enc_parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-m",
        "--message",
        dest="message",
        help="plain text message to embed"
    )
    group.add_argument(
        "-f",
        "--file",
        dest="message_file",
        help="path to a text file containing the message"
    )
    enc_parser.add_argument(
        "-n",
        "--n_lsb",
        dest="n_lsb",
        type=int,
        default=1,
        choices=[1, 2, 3],
        help="number of least significant bits to use (1–3)"
    )

    # Decoder
    dec_parser = subparsers.add_parser("decode", help="extract a message from a stego audio file")
    dec_parser.add_argument(
        "-i",
        "--input",
        dest="input_path",
        required=True,
        help="path to the stego audio file"
    )
    dec_parser.add_argument(
        "-n",
        "--n_lsb",
        dest="n_lsb",
        type=int,
        default=1,
        choices=[1, 2, 3],
        help="number of least significant bits used during encoding"
    )
    dec_parser.add_argument(
        "-s",
        "--no-save",
        dest="save_to_file",
        action="store_false",
        help="do not save the recovered message to a text file"
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    if args.command == "encode":
        message_source = args.message_file if args.message_file is not None else args.message
        encode_message(
            audio_path=args.input_path,
            message_text=message_source,
            output_path=args.output_path,
            n_lsb=args.n_lsb,
        )
        print(f"Message successfully embedded into {args.output_path}")
    elif args.command == "decode":
        plaintext = decode_message(
            stego_audio_path=args.input_path,
            n_lsb=args.n_lsb,
            save_to_file=args.save_to_file,
        )
        print("Recovered message:\n" + plaintext)
        if args.save_to_file:
            print("The message has also been saved to a text file.")
    else:
        raise RuntimeError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()