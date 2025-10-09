import os
import re
import io
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from flask import Flask, render_template, request, send_from_directory, redirect, url_for, flash
from werkzeug.utils import secure_filename

from stego.utils import encrypt as encrypt_module
from stego.lsb import lsb_img, lsb_wav
from stego.sample_comparison import video_audio_encoder, video_audio_decoder
from stego.whitespace import mainWhiteS


BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


ALLOWED_EXTENSIONS = {"txt", "css", "html", "mov", "mkv", "avi", "png", "bmp", "wav"}

SELECT_CHOICES = {"txt", "css", "html", "wav", "image", "video"}

CHOICE_TO_EXTS = {
    "txt": {"txt"},
    "css": {"css"},
    "html": {"html"},
    "wav": {"wav"},
    "image": {"png", "bmp"},
    "video": {"avi", "mkv", "mov"},
}
ALLOWED_OPTIONS = [
    {"value": "txt", "label": "txt"},
    {"value": "css", "label": "css"},
    {"value": "html", "label": "html"},
    {"value": "wav", "label": "wav"},
    {"value": "image", "label": "image (png/bmp)"},
    {"value": "video", "label": "video (avi/mkv/mov)"},
]


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

    @app.context_processor
    def inject_globals():
        return {
            "allowed_options": ALLOWED_OPTIONS, 
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
        chosen_type = (request.form.get("file_type") or "").lower()
        password = request.form.get("password") or ""
        message = request.form.get("message") or ""
        uploaded = request.files.get("upload_file")

        # Validations of inputs
        if not chosen_type or chosen_type not in SELECT_CHOICES:
            flash("Please choose a valid file type.", "error")
            return redirect(url_for("index"))

        if not password:
            flash("Password is required.", "error")
            return redirect(url_for("index"))

        if not message:
            flash("Message is required.", "error")
            return redirect(url_for("index"))

        if not uploaded or not uploaded.filename:
            flash("Please upload a file to encode.", "error")
            return redirect(url_for("index"))

        filename = secure_filename(uploaded.filename)
        if not allowed_file(filename):
            flash("Uploaded file type not allowed.", "error")
            return redirect(url_for("index"))

        temp_dir = tempfile.mkdtemp(prefix="stego_encode_")
        input_path = Path(temp_dir) / filename
        uploaded.save(str(input_path))

        ext = input_path.suffix.lower().lstrip(".")
        # UPDATED: ensure selected group matches uploaded file extension
        if ext not in CHOICE_TO_EXTS[chosen_type]:
            shutil.rmtree(temp_dir, ignore_errors=True)
            flash("Selected type and uploaded file do not match.", "error")
            return redirect(url_for("index"))

        try:
            output_path = OUTPUTS_DIR / f"stego_{input_path.stem}.{ext}"

            if ext in {"png", "bmp"}:
                # Use complete helper (handles encryption + embedding)
                lsb_img.encode_file(str(input_path), str(output_path), message, password)
                flash("Encoded file created: " + output_path.name, "success")
                return redirect(url_for("index", download=output_path.name))

            elif ext in {"avi", "mkv", "mov"}:
                fd_str = request.form.get("frame_duration") or ""
                cf_str = request.form.get("compare_fraction") or ""
                header_bits = request.form.get("header_bits") or ""
                footer_bits = request.form.get("footer_bits") or ""

                kwargs = {}
                if fd_str:
                    try:
                        kwargs["frame_duration"] = float(fd_str)
                    except ValueError:
                        pass
                if cf_str:
                    try:
                        kwargs["compare_fraction"] = float(cf_str)
                    except ValueError:
                        pass

                header_warning = footer_warning = None
                if header_bits:
                    valid_len = len(header_bits) >= 16 and len(header_bits) % 8 == 0
                    valid_chars = all(c in "01" for c in header_bits)
                    if valid_len and valid_chars:
                        kwargs["header"] = header_bits
                    else:
                        header_warning = "Invalid header; using default."
                if footer_bits:
                    valid_len = len(footer_bits) >= 16 and len(footer_bits) % 8 == 0
                    valid_chars = all(c in "01" for c in footer_bits)
                    if valid_len and valid_chars:
                        kwargs["footer"] = footer_bits
                    else:
                        footer_warning = "Invalid footer; using default."

                res = video_audio_encoder.encode_message_in_video_details(
                    str(input_path),
                    str(output_path),
                    message=encrypt_module.encrypt_message(password, message),
                    **kwargs
                )
                output_path = Path(res.output_path)

                # Only show params that are not DEFAULT
                details = []
                if res.header_display != "DEFAULT":
                    details.append(f"header={res.header_display}")
                if res.footer_display != "DEFAULT":
                    details.append(f"footer={res.footer_display}")
                if res.compare_fraction_display != "DEFAULT":
                    details.append(f"compare_fraction={res.compare_fraction_display}")
                # Always show frame info
                details += [
                    f"frame_size={res.frame_size}",
                    f"frame_duration_used={res.frame_duration:.8f}",
                ]
                warnings = [w for w in (header_warning, footer_warning) if w]
                if warnings:
                    details.append("Warnings: " + "; ".join(warnings))

                msg = "Encoded file created: " + output_path.name
                if details:
                    msg += " | " + ", ".join(details)
                flash(msg, "success")
                return redirect(url_for("index", download=output_path.name))

            elif ext in {"txt", "css", "html"}:
                # Complete helper (encrypt + embed). We can pre-check capacity.
                # Quick capacity check: encrypted length in bits must be <= lines.
                ciphertext = encrypt_module.encrypt_message(password, message)
                with open(input_path, 'r', encoding='utf-8', newline='') as f:
                    lines = f.readlines()
                needed_bits = len(mainWhiteS.text_to_binstr(ciphertext))
                if needed_bits > len(lines):
                    flash(f"Not enough lines (have {len(lines)}, need {needed_bits}).", "error")
                    return redirect(url_for("index"))

                ok = mainWhiteS.encode_file(str(input_path), str(output_path), message, password)
                if not ok:
                    flash("Encoding failed: capacity insufficient.", "error")
                    return redirect(url_for("index"))
                flash("Encoded file created: " + output_path.name, "success")
                return redirect(url_for("index", download=output_path.name))

            elif ext == "wav":
                n_lsb_str = request.form.get("wav_n_lsb") or "1"
                try:
                    n_lsb = int(n_lsb_str)
                    if n_lsb not in (1, 2, 3):
                        raise ValueError
                except ValueError:
                    flash("Invalid n_lsb (use 1-3). Defaulted to 1.", "warning")
                    n_lsb = 1
                # WAV module already accepts password and performs embedding
                lsb_wav.encode_message(
                    audio_path=str(input_path),
                    message_text=message,
                    output_path=str(output_path),
                    n_lsb=n_lsb,
                    password=password,
                )
                flash(f"Encoded file created: {output_path.name} | Params: n_lsb={n_lsb}", "success")
                return redirect(url_for("index", download=output_path.name))

            else:
                flash("Unsupported file type.", "error")
                return redirect(url_for("index"))

        except Exception as e:
            flash(f"Encoding failed: {e}", "error")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return redirect(url_for("index"))

    @app.post("/decode")
    def decode():
        chosen_type = (request.form.get("decode_file_type") or "").lower()
        password = request.form.get("decode_password") or ""
        uploaded = request.files.get("decode_upload_file")

        # Validate against grouped choices
        if not chosen_type or chosen_type not in SELECT_CHOICES:
            flash("Please choose a valid file type.", "error")
            return redirect(url_for("index"))
        if not uploaded or not uploaded.filename:
            flash("Please upload a file to decode.", "error")
            return redirect(url_for("index"))

        filename = secure_filename(uploaded.filename)
        if not allowed_file(filename):
            flash("Uploaded file type not allowed.", "error")
            return redirect(url_for("index"))

        temp_dir = tempfile.mkdtemp(prefix="stego_decode_")
        input_path = Path(temp_dir) / filename
        uploaded.save(str(input_path))

        ext = input_path.suffix.lower().lstrip(".")
        # Ensure selected group matches uploaded file extension
        if ext not in CHOICE_TO_EXTS[chosen_type]:
            shutil.rmtree(temp_dir, ignore_errors=True)
            flash("Selected type and file do not match.", "error")
            return redirect(url_for("index"))

        try:
            # Branch by actual extension
            if ext in {"png", "bmp"}:
                decoded_message = lsb_img.decode_file(str(input_path), password)

            elif ext in {"avi", "mkv", "mov"}:
                with tempfile.TemporaryDirectory() as tmpdir:
                    audio_wav = Path(tmpdir) / "audio.wav"
                    cmd = ["ffmpeg", "-y", "-i", str(input_path), "-vn", "-acodec", "pcm_s16le", "-ar", "48000", str(audio_wav)]
                    subprocess.run(cmd, check=True)

                    d_fd = request.form.get("decode_frame_duration") or ""
                    d_cf = request.form.get("decode_compare_fraction") or ""
                    d_header = request.form.get("decode_header_bits") or ""
                    d_footer = request.form.get("decode_footer_bits") or ""

                    kwargs = {}
                    if d_fd:
                        try: kwargs["frame_duration"] = float(d_fd)
                        except ValueError: pass
                    if d_cf:
                        try: kwargs["compare_fraction"] = float(d_cf)
                        except ValueError: pass
                    if d_header and len(d_header) >= 16 and len(d_header) % 8 == 0 and all(c in "01" for c in d_header):
                        kwargs["header_bits"] = [int(b) for b in d_header]
                    if d_footer and len(d_footer) >= 16 and len(d_footer) % 8 == 0 and all(c in "01" for c in d_footer):
                        kwargs["footer_bits"] = [int(b) for b in d_footer]

                    raw = video_audio_decoder.decode_audio_stego(str(audio_wav), **kwargs)

                    # Graceful handling of wrong params/password (raw missing or decrypt fails)
                    if raw in (None, b"", ""):
                        flash("Decoding failed - Wrong parameters or password were provided", "error")
                        return redirect(url_for("index"))
                    try:
                        decoded_message = encrypt_module.decrypt_message(
                            password,
                            raw if isinstance(raw, bytes) else raw.encode("utf-8", errors="replace")
                        )
                    except Exception:
                        flash("Decoding failed - Wrong parameters or password were provided", "error")
                        return redirect(url_for("index"))

            elif ext in {"txt", "css", "html"}:
                # Complete helper for whitespace
                decoded_message = mainWhiteS.decode_file(str(input_path), password)

            elif ext == "wav":
                d_n_lsb_str = request.form.get("decode_wav_n_lsb") or "1"
                try:
                    n_lsb = int(d_n_lsb_str)
                    if n_lsb not in (1, 2, 3):
                        raise ValueError
                except ValueError:
                    flash("Invalid n_lsb (use 1-3). Defaulted to 1.", "warning")
                    n_lsb = 1
                decoded_message = lsb_wav.decode_message(
                    stego_audio_path=str(input_path),
                    n_lsb=n_lsb,
                    save_to_file=False,
                    password=password,
                )
            else:
                flash("Unsupported file type.", "error")
                return redirect(url_for("index"))

            if not decoded_message:
                flash("Decoding failed or message empty.", "error")
            elif any(ord(c) < 32 and c not in ("\n", "\r", "\t") for c in decoded_message):
                flash(f"Decoded message (possibly wrong password): {decoded_message}", "error")
            else:
                flash(f"Decoded message: {decoded_message}", "success")

        except Exception as e:
            flash(f"Decoding failed: {e}", "error")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return redirect(url_for("index"))

    @app.get("/encode")
    def encode_get():
        return redirect(url_for("index"))

    @app.get("/decode")
    def decode_get():
        return redirect(url_for("index"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))



