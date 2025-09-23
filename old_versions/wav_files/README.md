# Audio Steganography with AES‑256 Encryption

This repository implements a complete end‑to‑end project for hiding
arbitrary text inside uncompressed audio.  It was written as a
hands‑on demonstration for a university course on information
security.  The goal is to showcase how secret messages can be hidden
in plain sight, while still enjoying the confidentiality of modern
cryptography.

## How it works

**Least Significant Bit substitution.**  Digital audio stored in a
WAV file consists of a sequence of samples.  In a mono, 16‑bit WAV
file each sample is represented by two bytes.  To hide a message we
modify only the lower byte of each sample (one out of every two
bytes); this byte carries the least significant bits of the sample
value and small changes there are inaudible【51454510526638†L650-L706】.  Our
implementation replaces one to three of those least significant bits
with bits from the secret message.  Using more bits increases
capacity but also slightly degrades the signal.

Before embedding, the message is transformed into a bitstream.  We
first encrypt the plaintext using a password (see below), then prefix
the encrypted payload with its length as a 32‑bit big‑endian integer.
The full byte sequence is converted to bits and written into the
audio sample bytes.  On extraction the first 32 bits are read to
recover the length and the subsequent bits are reassembled into the
encrypted payload.  This length prefix allows the decoder to know
exactly when the message ends, avoiding the stray characters that
appear if you simply read until the end of the file【51454510526638†L650-L706】.

**AES‑256 encryption.**  Hiding information without encryption is
dangerous because anyone who discovers the hidden bits can read your
message.  To prevent this, the plaintext is encrypted using
password‑based AES‑256 before it is embedded.  Best practices for
password‑based encryption require a random salt and a strong key
derivation function.  In the reference implementation from Lane
Wagner’s AES‑256 tutorial, a random salt is generated and the
password is stretched into a 256‑bit key using the Scrypt KDF
【132564739309937†L74-L92】.  Salts ensure that the same password yields a
different key every time, thwarting precomputed rainbow table
attacks【132564739309937†L96-L106】.  While the tutorial uses the
PyCryptodome library, our project achieves the same result by
invoking the OpenSSL command line tool with the `-pbkdf2` option.
OpenSSL automatically derives the key from the password, prepends the
salt to the ciphertext and applies AES‑256‑CBC encryption.  The
ciphertext is then Base64‑encoded so that it can be stored as ASCII
text【132564739309937†L74-L92】.  During decoding, the encrypted data is fed
back into OpenSSL along with the same password; the tool reads the
salt, derives the key and verifies the message integrity.

## Project layout

```
stego_project/
├── crypto_utils.py  # wrappers around OpenSSL for AES‑256 encryption/decryption
├── stego_core.py    # bitwise embedding/extraction and high‑level encode/decode functions
├── main.py          # command‑line interface
└── README.md        # this file
```

### crypto_utils.py

Provides two functions, `encrypt_message` and `decrypt_message`, that
invoke the OpenSSL `enc` command with the `-aes-256-cbc`, `-salt` and
`-pbkdf2` flags.  The former takes a plaintext string and returns a
Base64 ciphertext.  The latter takes the Base64 bytes and a password
and returns the original plaintext.  Errors from OpenSSL are
propagated as Python exceptions.

### stego_core.py

Defines helper functions to convert between bytes and bits, embed
bits into audio frames and extract them.  The two high‑level
functions are:

- **encode_message(audio_path, message_text, output_path, n_lsb=1)**:
  Reads `audio_path`, prompts for a password, encrypts the message
  (either a literal string or the contents of a text file), prepends
  its length and embeds the resulting bitstream into the least
  significant bits of the audio samples.  Only mono 16‑bit WAV files
  are supported.
- **decode_message(stego_audio_path, n_lsb=1, save_to_file=True)**:
  Extracts the bitstream from a stego WAV, recovers the encrypted
  payload length and data, prompts for the password and decrypts the
  message.  By default the recovered plaintext is also saved to
  `<stego_audio_basename>_decoded.txt`.

### main.py

Implements a simple command‑line interface using `argparse`.  It
supports two subcommands: `encode` for embedding messages and
`decode` for extraction.  Use `--help` on either subcommand to see the
available options.

## Usage

Ensure that you have Python 3 and OpenSSL installed on your system.

1. Place a mono 16‑bit WAV file in the working directory and note its
   filename (e.g. `input.wav`).
2. Install any dependencies (none besides OpenSSL).  This project
   avoids the need for extra Python packages by calling OpenSSL
   directly.
3. Run the encoder.  For example, to hide the Hebrew phrase "סוד
   סודי ביותר" using 2 LSBs and save the result as `output.wav`:

   ```bash
   python main.py encode -i input.wav -o output.wav -m "סוד סודי ביותר" -n 2
   ```

   You will be prompted to enter a password; use the same password
   later to decode.

4. Decode the message:

   ```bash
   python main.py decode -i output.wav -n 2
   ```

   Enter the password when prompted.  The recovered message will be
   printed to the console and, unless you specify `--no-save`, will
   also be written to `output_decoded.txt`.

## Notes and limitations

* **Audio format:** The implementation supports only 16‑bit mono WAV
  files.  Attempts to encode or decode other formats will raise an
  error.  This constraint simplifies the bit indexing logic and is
  sufficient for demonstration purposes.
* **Capacity:** The number of bits available for embedding is
  `n_samples * n_lsb`, where `n_samples` is the number of audio
  samples.  A typical five‑second, 44.1 kHz file provides around
  220 000 samples and thus roughly 220 000 bits (27.5 kB) of capacity
  when using a single LSB.  If the message is too long a
  `ValueError` is raised.
* **Security:** While OpenSSL's AES‑256 implementation with PBKDF2 is
  considered secure, the overall scheme is still a simple LSB
  replacement technique.  As noted in research, replacing the least
  significant bits of audio samples introduces detectable statistical
  changes【51454510526638†L650-L706】.  For high‑stakes applications you should
  consider more sophisticated steganographic methods, such as LSB
  matching or spread‑spectrum techniques.

## Acknowledgements

The overall approach for reading and modifying WAV samples draws on
Daniel Lerch Hostalot’s tutorial on LSB steganography in images and
audio, which explains that WAV files store 16‑bit samples and that
only the lower byte should be altered【51454510526638†L650-L706】.  The idea of
using a salt and a password‑derived key for encryption comes from
Lane Wagner’s article on AES‑256 encryption, which emphasises
generating a random salt and deriving the key via Scrypt【132564739309937†L74-L92】【132564739309937†L96-L106】.