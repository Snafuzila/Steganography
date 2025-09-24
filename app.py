import os
import sys
import importlib.util
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from flask import Flask, render_template, request, send_from_directory, redirect, url_for, flash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


ALLOWED_EXTENSIONS = {"txt", "css", "html", "mov", "mkv", "avi", "png", "bmp", "wav"}


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(TEMPLATES_DIR),
        static_folder=str(STATIC_DIR),
    )
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

    # Ensure directories exist
    for d in (UPLOADS_DIR, OUTPUTS_DIR, TEMPLATES_DIR, STATIC_DIR):
        d.mkdir(parents=True, exist_ok=True)

    def load_module_from_path(module_name: str, file_path: Path):
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module {module_name} from {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def load_module_in_package(package_name: str, module_name: str, module_path: Path, package_dir: Path):
        """Load a module as if it were inside a package so relative imports work.

        Ensures a synthetic package entry exists in sys.modules and then loads
        the target module with a fully-qualified name like 'pkg.mod'.
        """
        # Ensure synthetic package
        if package_name not in sys.modules:
            pkg = importlib.util.module_from_spec(importlib.machinery.ModuleSpec(package_name, loader=None))
            pkg.__path__ = [str(package_dir)]  # type: ignore[attr-defined]
            sys.modules[package_name] = pkg
        fqmn = f"{package_name}.{module_name}"
        spec = importlib.util.spec_from_file_location(fqmn, str(module_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module {fqmn} from {module_path}")
        mod = importlib.util.module_from_spec(spec)
        # Set package attribute so 'from .x import y' resolves
        mod.__package__ = package_name
        sys.modules[fqmn] = mod
        spec.loader.exec_module(mod)
        return mod

    # Simple whitespace stego for txt/html/css (encryption handled separately)
    def _text_to_binary(text: str) -> str:
        return ''.join(format(ord(c), '08b') for c in text)

    def _binary_to_text(binary: str) -> str:
        return ''.join(chr(int(binary[i:i+8], 2)) for i in range(0, len(binary), 8))

    def embed_whitespace(input_file: Path, output_file: Path, payload: str) -> None:
        bits = _text_to_binary(payload)
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if len(bits) > len(lines):
            raise ValueError("Not enough lines in host file to embed message bits")
        out_lines = []
        for i, line in enumerate(lines):
            if i < len(bits):
                marker = ' ' if bits[i] == '0' else '\t'
                out_lines.append(line.rstrip('\n') + marker + '\n')
            else:
                out_lines.append(line)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(out_lines)

    def extract_whitespace(stego_file: Path) -> str:
        with open(stego_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        bits = []
        for line in lines:
            if line.endswith(' \n') or line.endswith('\t\n'):
                last_char = line[-2]
                if last_char == ' ':
                    bits.append('0')
                elif last_char == '\t':
                    bits.append('1')
        bit_str = ''.join(bits)
        bit_str = bit_str[:len(bit_str) - (len(bit_str) % 8)]
        return _binary_to_text(bit_str)

    def is_garbled_text(text: str) -> bool:
        """Check if text appears to be garbled (wrong password result)."""
        if not text:
            return False
        # Count non-printable and replacement characters
        garbled_chars = sum(1 for c in text if ord(c) < 32 or c == '\ufffd')
        # If more than 30% of characters are garbled, likely wrong password
        return garbled_chars / len(text) > 0.3

    @app.context_processor
    def inject_globals():
        return {
            "allowed_types": sorted(list(ALLOWED_EXTENSIONS)),
        }

    def allowed_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/download/<path:filename>")
    def download_output(filename: str):
        # Only allow files within outputs
        return send_from_directory(str(OUTPUTS_DIR), filename, as_attachment=True)

    @app.post("/encode")
    def encode():
        # Inputs
        chosen_type = request.form.get("file_type")
        password = request.form.get("password") or ""
        message = request.form.get("message") or ""
        uploaded = request.files.get("upload_file")

        if not chosen_type or chosen_type not in ALLOWED_EXTENSIONS:
            flash("Please choose a valid file type.", "error")
            return redirect(url_for("index"))

        if not password:
            flash("Password is required.", "error")
            return redirect(url_for("index"))

        if not message:
            flash("Message is required.", "error")
            return redirect(url_for("index"))

        # Determine input path (uploads only)
        input_path: Optional[Path] = None
        temp_dir: Optional[str] = None
        if uploaded and uploaded.filename:
            filename = secure_filename(uploaded.filename)
            if not allowed_file(filename):
                flash("Uploaded file type not allowed.", "error")
                return redirect(url_for("index"))
            temp_dir = tempfile.mkdtemp(prefix="stego_encode_")
            input_path = Path(temp_dir) / filename
            uploaded.save(str(input_path))
        else:
            flash("Please upload a file to encode.", "error")
            return redirect(url_for("index"))

        # Validate extension vs selected type
        ext = input_path.suffix.lower().lstrip(".")
        if chosen_type.lower() != ext:
            flash("Selected file type and uploaded file do not match. Please select the correct type.", "error")
            return redirect(url_for("index"))

        # Choose algorithm based on extension

        try:
            output_name = f"stego_{input_path.stem}.{input_path.suffix.lstrip('.') }"
            output_path = OUTPUTS_DIR / output_name

            # Load encryption API
            enc_module = load_module_from_path(
                "encrypt_module",
                BASE_DIR / "encypt functions" / "encrypt.py",
            )
            encrypt_message = getattr(enc_module, "encrypt_message")
            decrypt_message = getattr(enc_module, "decrypt_message")

            if ext in {"png", "bmp"}:
                # Image LSB
                from PIL import Image
                lsb_module = load_module_from_path(
                    "lsb_img",
                    BASE_DIR / "encypt functions" / "lsb" / "lsb_img.py",
                )
                lsb_img_hide_text_with_length = getattr(lsb_module, "lsb_img_hide_text_with_length")
                ciphertext = encrypt_message(password, message)
                img = Image.open(str(input_path))
                new_img = lsb_img_hide_text_with_length(img, ciphertext)
                new_img.save(str(output_path))
                flash("Encoded file created: " + output_path.name, "success")
                return redirect(url_for("index", download=output_path.name))
            elif ext in {"avi", "mkv", "mov"}:
                # Sample Comparison video/audio
                encoder_module = load_module_from_path(
                    "video_audio_encoder",
                    BASE_DIR / "encypt functions" / "Sample Comparison" / "video_audio_encoder.py",
                )
                encode_message_in_video = getattr(encoder_module, "encode_message_in_video")
                # Read optional params
                fd_str = request.form.get("frame_duration") or ""
                cf_str = request.form.get("compare_fraction") or ""
                header_bits = request.form.get("header_bits") or ""
                footer_bits = request.form.get("footer_bits") or ""
                threshold_str = request.form.get("threshold") or ""

                kwargs = {}
                changed = []
                if fd_str:
                    try:
                        kwargs["frame_duration"] = float(fd_str)
                        changed.append(f"frame_duration={kwargs['frame_duration']}")
                    except ValueError:
                        pass
                if cf_str:
                    try:
                        kwargs["compare_fraction"] = float(cf_str)
                        changed.append(f"compare_fraction={kwargs['compare_fraction']}")
                    except ValueError:
                        pass
                if header_bits:
                    if all(c in "01" for c in header_bits):
                        kwargs["header"] = header_bits
                        changed.append(f"header={header_bits}")
                    else:
                        flash("Header must contain only 0 and 1.", "error")
                        return redirect(url_for("index"))
                if footer_bits:
                    if all(c in "01" for c in footer_bits):
                        kwargs["footer"] = footer_bits
                        changed.append(f"footer={footer_bits}")
                    else:
                        flash("Footer must contain only 0 and 1.", "error")
                        return redirect(url_for("index"))
                if threshold_str:
                    try:
                        kwargs["threshold"] = int(threshold_str)
                        changed.append(f"threshold={kwargs['threshold']}")
                    except ValueError:
                        flash("Threshold must be an integer.", "error")
                        return redirect(url_for("index"))

                # Encoder returns output path. Capture stdout to parse chosen frame size/duration.
                import io, contextlib, re
                captured = io.StringIO()
                with contextlib.redirect_stdout(captured):
                    final_output = encode_message_in_video(
                        str(input_path),
                        str(output_path),
                        message=encrypt_message(password, message),
                        **kwargs,
                    )
                output_path = Path(final_output)
                # Parse encoder output for frame size/duration
                log_text = captured.getvalue()
                m = re.search(r"Using frame size:\s*(\d+)\s+samples\s*\(([^)]+) seconds per frame\)", log_text)
                if m:
                    frame_size_used = m.group(1)
                    frame_duration_used = m.group(2)
                    changed.append(f"frame_size={frame_size_used}")
                    changed.append(f"frame_duration_used={frame_duration_used}")
                # Always show a single success message including any params available
                if changed:
                    flash(
                        "Encoded file created: " + output_path.name + " | Params: " + ", ".join(changed),
                        "success",
                    )
                else:
                    flash("Encoded file created: " + output_path.name, "success")
                # Redirect back to index with a download hint param
                return redirect(url_for("index", download=output_path.name))
            elif ext in {"txt", "css", "html"}:
                # Use mainWhiteS helpers; embed ciphertext
                ws_module = load_module_from_path(
                    "mainWhiteS",
                    BASE_DIR / "encypt functions" / "whitespace" / "mainWhiteS.py",
                )
                ciphertext = encrypt_message(password, message)
                text_to_binary = getattr(ws_module, "text_to_binary")
                binary_to_whitespace = getattr(ws_module, "binary_to_whitespace")
                embed_message = getattr(ws_module, "embed_message")
                bits = text_to_binary(ciphertext)
                ws_stream = binary_to_whitespace(bits)
                with open(input_path, 'r', encoding='utf-8', newline='') as f:
                    lines = f.readlines()
                if len(ws_stream) > len(lines):
                    flash(
                        f"Not enough lines in host file to embed message bits (have {len(lines)}, need {len(ws_stream)}).",
                        "error",
                    )
                    return redirect(url_for("index"))
                embed_message(str(input_path), str(output_path), ciphertext)
                flash("Encoded file created: " + output_path.name, "success")
                return redirect(url_for("index", download=output_path.name))
            elif ext == "wav":
                # LSB WAV steganography (uses module's own crypto)
                wav_module = load_module_in_package(
                    package_name="lsb",
                    module_name="lsb_wav",
                    module_path=BASE_DIR / "encypt functions" / "lsb" / "lsb_wav.py",
                    package_dir=BASE_DIR / "encypt functions" / "lsb",
                )
                encode_wav = getattr(wav_module, "encode_message")
                # Optional LSBs param (1-3)
                n_lsb_str = request.form.get("wav_n_lsb") or ""
                n_lsb = 1
                try:
                    if n_lsb_str:
                        n_lsb = max(1, min(3, int(n_lsb_str)))
                except ValueError:
                    n_lsb = 1
                # Call encoder; module handles encryption internally with password
                encode_wav(
                    audio_path=str(input_path),
                    message_text=message,
                    output_path=str(output_path),
                    n_lsb=n_lsb,
                    password=password,
                )
                flash(
                    f"Encoded file created: {output_path.name} | Params: n_lsb={n_lsb}",
                    "success",
                )
                return redirect(url_for("index", download=output_path.name))
            else:
                flash("Unsupported file type for encoding.", "error")
                return redirect(url_for("index"))

            flash(f"Encoded file created: {output_path.name}", "success")
        except Exception as e:
            flash(f"Encoding failed: {e}", "error")
            return redirect(url_for("index"))
        finally:
            if temp_dir:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
        # Fallback redirect (should be returned earlier)
        return redirect(url_for("index"))

    @app.post("/decode")
    def decode():
        chosen_type = request.form.get("decode_file_type")
        password = request.form.get("decode_password") or ""
        uploaded = request.files.get("decode_upload_file")

        if not chosen_type or chosen_type not in ALLOWED_EXTENSIONS:
            flash("Please choose a valid file type.", "error")
            return redirect(url_for("index"))

        # Determine input path (uploads only)
        input_path: Optional[Path] = None
        temp_dir: Optional[str] = None
        if uploaded and uploaded.filename:
            filename = secure_filename(uploaded.filename)
            if not allowed_file(filename):
                flash("Uploaded file type not allowed.", "error")
                return redirect(url_for("index"))
            temp_dir = tempfile.mkdtemp(prefix="stego_decode_")
            input_path = Path(temp_dir) / filename
            uploaded.save(str(input_path))
        else:
            flash("Please upload a file to decode.", "error")
            return redirect(url_for("index"))

        ext = input_path.suffix.lower().lstrip(".")
        if chosen_type.lower() != ext:
            flash("Selected file type and uploaded file do not match. Please select the correct type.", "error")
            return redirect(url_for("index"))
        decoded_message: Optional[str] = None
        try:
            if ext in {"png", "bmp"}:
                from PIL import Image
                lsb_module = load_module_from_path(
                    "lsb_img",
                    BASE_DIR / "encypt functions" / "lsb" / "lsb_img.py",
                )
                lsb_img_extract_text_from_image = getattr(lsb_module, "lsb_img_extract_text_from_image")
                enc_module = load_module_from_path(
                    "encrypt_module",
                    BASE_DIR / "encypt functions" / "encrypt.py",
                )
                decrypt_message = getattr(enc_module, "decrypt_message")
                img = Image.open(str(input_path))
                encrypted_blob = lsb_img_extract_text_from_image(img)
                decoded_message = decrypt_message(password, encrypted_blob)
            elif ext in {"avi", "mkv", "mov"}:
                decoder_module = load_module_from_path(
                    "video_audio_decoder",
                    BASE_DIR / "encypt functions" / "Sample Comparison" / "video_audio_decoder.py",
                )
                decode_audio_stego = getattr(decoder_module, "decode_audio_stego")

                # Extract audio via ffmpeg to wav then decode
                with tempfile.TemporaryDirectory() as tmpdir:
                    audio_wav = Path(tmpdir) / "audio.wav"
                    cmd = [
                        "ffmpeg", "-y", "-i", str(input_path), "-vn",
                        "-acodec", "pcm_s16le", "-ar", "48000", str(audio_wav)
                    ]
                    subprocess.run(cmd, check=True)
                    # Use defaults that match encoder defaults
                    # Optional params from form
                    d_fd = request.form.get("decode_frame_duration") or ""
                    d_cf = request.form.get("decode_compare_fraction") or ""
                    d_header = request.form.get("decode_header_bits") or ""
                    d_footer = request.form.get("decode_footer_bits") or ""
                    d_threshold = request.form.get("decode_threshold") or ""
                    kwargs = {}
                    if d_fd:
                        try:
                            kwargs["frame_duration"] = float(d_fd)
                        except ValueError:
                            pass
                    if d_cf:
                        try:
                            kwargs["compare_fraction"] = float(d_cf)
                        except ValueError:
                            pass
                    if d_header:
                        if all(c in "01" for c in d_header):
                            kwargs["header_bits"] = [int(b) for b in d_header]
                        else:
                            flash("Header must contain only 0 and 1.", "error")
                            return redirect(url_for("index"))
                    if d_footer:
                        if all(c in "01" for c in d_footer):
                            kwargs["footer_bits"] = [int(b) for b in d_footer]
                        else:
                            flash("Footer must contain only 0 and 1.", "error")
                            return redirect(url_for("index"))
                    if d_threshold:
                        try:
                            kwargs["threshold"] = int(d_threshold)
                        except ValueError:
                            flash("Threshold must be an integer.", "error")
                            return redirect(url_for("index"))
                    decoded = decode_audio_stego(str(audio_wav), **kwargs)
                    # Decrypt the extracted ciphertext
                    enc_module = load_module_from_path(
                        "encrypt_module",
                        BASE_DIR / "encypt functions" / "encrypt.py",
                    )
                    decrypt_message = getattr(enc_module, "decrypt_message")
                    # Handle both string and bytes from video decoder
                    try:
                        if isinstance(decoded, str):
                            # Already a string, decrypt it (handle encoding errors)
                            try:
                                decoded_message = decrypt_message(password, decoded.encode('utf-8'))
                            except UnicodeEncodeError:
                                # String contains invalid UTF-8, treat as bytes
                                decoded_message = decrypt_message(password, decoded.encode('utf-8', errors='replace'))
                        elif isinstance(decoded, bytes):
                            # Raw bytes, decrypt directly
                            decoded_message = decrypt_message(password, decoded)
                        else:
                            decoded_message = None
                    except Exception:
                        # Most likely parameter mismatch (e.g., wrong frame duration or header/footer)
                        flash(
                            "There was a problem with the parameters (e.g., frame duration/compare fraction/header/footer). Please try again.",
                            "error",
                        )
                        return redirect(url_for("index"))
            elif ext in {"txt", "css", "html"}:
                ws_module = load_module_from_path(
                    "mainWhiteS",
                    BASE_DIR / "encypt functions" / "whitespace" / "mainWhiteS.py",
                )
                extract_message = getattr(ws_module, "extract_message")
                enc_module = load_module_from_path(
                    "encrypt_module",
                    BASE_DIR / "encypt functions" / "encrypt.py",
                )
                decrypt_message = getattr(enc_module, "decrypt_message")
                encrypted = extract_message(str(input_path))
                decoded_message = decrypt_message(password, encrypted)
            elif ext == "wav":
                # WAV decode (module returns plaintext when password provided)
                wav_module = load_module_in_package(
                    package_name="lsb",
                    module_name="lsb_wav",
                    module_path=BASE_DIR / "encypt functions" / "lsb" / "lsb_wav.py",
                    package_dir=BASE_DIR / "encypt functions" / "lsb",
                )
                decode_wav = getattr(wav_module, "decode_message")
                n_lsb_str = request.form.get("decode_wav_n_lsb") or ""
                n_lsb = 1
                try:
                    if n_lsb_str:
                        n_lsb = max(1, min(3, int(n_lsb_str)))
                except ValueError:
                    n_lsb = 1
                decoded_message = decode_wav(
                    stego_audio_path=str(input_path),
                    n_lsb=n_lsb,
                    save_to_file=False,
                    password=password,
                )
            else:
                flash("Unsupported file type for decoding.", "error")
                return redirect(url_for("index"))

            if decoded_message is None:
                flash("Decoding failed or message empty. Check password/parameters.", "error")
            else:
                # Check if the message appears garbled (wrong password)
                if is_garbled_text(decoded_message):
                    flash(f"Decoded message (wrong password?): {decoded_message}", "error")
                else:
                    flash(f"Decoded message: {decoded_message}", "success")
        except Exception as e:
            flash(f"Decoding failed: {e}", "error")
        finally:
            if temp_dir:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

        return redirect(url_for("index"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


