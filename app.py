from __future__ import annotations

import os
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from werkzeug.utils import secure_filename

# Import steganography functions
from wav_files.stego_core import encode_message, decode_message

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("wav_files") / "output_files"
ALLOWED_EXTENSIONS = {"wav"}

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

def allowed_file(filename: str) -> bool:
	return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
	return render_template("index.html")

@app.post("/encode")
def encode_route():
	file = request.files.get("audio")
	message_text = request.form.get("message", "")
	password = request.form.get("password", "")
	n_lsb = int(request.form.get("n_lsb", 1))
	if not file or file.filename == "":
		flash("יש לבחור קובץ WAV.", "error")
		return redirect(url_for("index"))
	if not allowed_file(file.filename):
		flash("סוג קובץ לא נתמך. יש להעלות WAV מונו 16bit.", "error")
		return redirect(url_for("index"))
	if not password:
		flash("יש להזין סיסמה.", "error")
		return redirect(url_for("index"))
	# Save upload
	upload_name = secure_filename(file.filename)
	upload_path = UPLOAD_DIR / upload_name
	file.save(upload_path)
	# Build output path in project output_files
	out_name = upload_path.stem + "_hidden.wav"
	out_path = OUTPUT_DIR / out_name
	try:
		encode_message(str(upload_path), message_text, str(out_path), n_lsb=n_lsb, password=password)
		flash("ההודעה הוטמעה בהצלחה!", "success")
		return redirect(url_for("download", filename=out_name))
	except Exception as e:
		flash(str(e), "error")
		return redirect(url_for("index"))

@app.post("/decode")
def decode_route():
	file = request.files.get("audio")
	password = request.form.get("password", "")
	n_lsb = int(request.form.get("n_lsb", 1))
	if not file or file.filename == "":
		flash("יש לבחור קובץ WAV.", "error")
		return redirect(url_for("index"))
	if not allowed_file(file.filename):
		flash("סוג קובץ לא נתמך. יש להעלות WAV מונו 16bit.", "error")
		return redirect(url_for("index"))
	if not password:
		flash("יש להזין סיסמה.", "error")
		return redirect(url_for("index"))
	upload_name = secure_filename(file.filename)
	upload_path = UPLOAD_DIR / upload_name
	file.save(upload_path)
	try:
		plaintext = decode_message(str(upload_path), n_lsb=n_lsb, password=password)
		flash("ההודעה חולצה בהצלחה!", "success")
		return render_template("index.html", decoded_text=plaintext)
	except Exception as e:
		flash(str(e), "error")
		return redirect(url_for("index"))

@app.get("/download/<filename>")
def download(filename: str):
	path = OUTPUT_DIR / secure_filename(filename)
	if not path.exists():
		flash("קובץ לא נמצא.", "error")
		return redirect(url_for("index"))
	return send_file(path, as_attachment=True, download_name=path.name)

if __name__ == "__main__":
	app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000))) 