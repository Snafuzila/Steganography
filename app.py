import os
import io
import importlib.util
import tempfile
import subprocess
from flask import Flask, render_template, request, send_file, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_ROOT = os.path.join(BASE_DIR, 'encypt functions')  # path contains a space

# Helpers to import modules from files where package path has spaces

def import_from_path(module_name: str, file_path: str):
	"""Dynamically import a module from an arbitrary file path."""
	spec = importlib.util.spec_from_file_location(module_name, file_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)  # type: ignore
	return module

# Load modules
lsb_path = os.path.join(MODULES_ROOT, 'lsb', 'lsb_img.py')
whitespace_path = os.path.join(MODULES_ROOT, 'whitespace', 'mainWhiteS.py')
aes_path = os.path.join(MODULES_ROOT, 'encrypt.py')
legacy_crypto_path = os.path.join(BASE_DIR, 'old versions', 'crypto_utils.py')
video_enc_path = os.path.join(MODULES_ROOT, 'Sample Comparison', 'video_audio_encoder.py')
video_dec_path = os.path.join(MODULES_ROOT, 'Sample Comparison', 'video_audio_decoder.py')

lsb_mod = import_from_path('lsb_img', lsb_path)
whitespace_mod = import_from_path('mainWhiteS', whitespace_path)
aes_mod = import_from_path('encrypt', aes_path)
legacy_crypto_mod = import_from_path('legacy_crypto_utils', legacy_crypto_path)
video_enc_mod = import_from_path('video_audio_encoder', video_enc_path)
video_dec_mod = import_from_path('video_audio_decoder', video_dec_path)

ALLOWED_IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.bmp'}
ALLOWED_VIDEO_EXTS = {'.mkv', '.avi', '.mp4'}
ALLOWED_TEXT_EXTS = {'.txt', '.html', '.css'}

app = Flask(__name__)
app.secret_key = os.environ.get('APP_SECRET', 'dev-secret')


def _ext(path: str) -> str:
	return os.path.splitext(path)[1].lower()


@app.get('/')
def index():
	return render_template('index.html')


@app.post('/encode/lsb-image')
def encode_lsb_image():
	message = (request.form.get('message') or '').strip()
	if not message:
		flash('Message is required', 'error')
		return redirect(url_for('index'))

	upload = request.files.get('file')
	if not upload or upload.filename == '':
		flash('Image file is required', 'error')
		return redirect(url_for('index'))

	ext = _ext(upload.filename)
	if ext not in ALLOWED_IMAGE_EXTS:
		flash('Unsupported image format', 'error')
		return redirect(url_for('index'))

	image = Image.open(upload.stream)
	result_img = lsb_mod.lsb_img_hide_text_with_length(image, message)
	buf = io.BytesIO()
	result_img.save(buf, format='PNG')
	buf.seek(0)
	return send_file(buf, mimetype='image/png', as_attachment=True, download_name='stego.png')


@app.post('/decode/lsb-image')
def decode_lsb_image():
	upload = request.files.get('file')
	if not upload or upload.filename == '':
		flash('Image file is required', 'error')
		return redirect(url_for('index'))
	image = Image.open(upload.stream)
	text = lsb_mod.lsb_img_extract_text_from_image(image)
	return jsonify({ 'message': text })


@app.post('/encode/whitespace')
def encode_whitespace():
	password = request.form.get('password') or ''
	message = request.form.get('message') or ''
	upload = request.files.get('file')
	if not upload or upload.filename == '':
		flash('Host file is required', 'error')
		return redirect(url_for('index'))

	ext = _ext(upload.filename)
	if ext not in ALLOWED_TEXT_EXTS:
		flash('Unsupported text format', 'error')
		return redirect(url_for('index'))

	with tempfile.TemporaryDirectory() as tmp:
		in_path = os.path.join(tmp, secure_filename(upload.filename))
		out_path = os.path.join(tmp, 'stego' + ext)
		upload.save(in_path)
		whitespace_mod.embed_encrypted_message(in_path, out_path, message, password)
		return send_file(out_path, as_attachment=True, download_name=f'stego{ext}')


@app.post('/decode/whitespace')
def decode_whitespace():
	password = request.form.get('password') or ''
	upload = request.files.get('file')
	if not upload or upload.filename == '':
		flash('Stego file is required', 'error')
		return redirect(url_for('index'))
	with tempfile.TemporaryDirectory() as tmp:
		in_path = os.path.join(tmp, secure_filename(upload.filename))
		upload.save(in_path)
		cipher = whitespace_mod.extract_encrypted_message(in_path)
		plain = None
		# Try new AES/CBC first
		try:
			plain = aes_mod.decrypt_message(password, cipher)
		except Exception:
			plain = None
		# Fallback to legacy urlsafe CFB scheme
		if not plain:
			try:
				plain = legacy_crypto_mod.decrypt_message(cipher, password)
			except Exception:
				plain = None
		return jsonify({ 'message': plain or '' })


@app.post('/encode/video-audio')
def encode_video_audio():
	message = request.form.get('message')
	upload = request.files.get('file')
	if not upload or upload.filename == '':
		flash('Video file is required', 'error')
		return redirect(url_for('index'))

	ext = _ext(upload.filename)
	if ext not in ALLOWED_VIDEO_EXTS:
		flash('Unsupported video format', 'error')
		return redirect(url_for('index'))

	with tempfile.TemporaryDirectory() as tmp:
		in_path = os.path.join(tmp, secure_filename(upload.filename))
		out_path = os.path.join(tmp, 'output' + ext)
		upload.save(in_path)
		res_path = video_enc_mod.encode_message_in_video(in_path, out_path, message=message)
		return send_file(res_path, as_attachment=True, download_name=os.path.basename(res_path))


@app.post('/decode/video-audio')
def decode_video_audio():
	upload = request.files.get('file')
	frame_duration = float(request.form.get('frame_duration') or 0.1)
	compare_fraction = float(request.form.get('compare_fraction') or 0.5)
	if not upload or upload.filename == '':
		flash('Video file is required', 'error')
		return redirect(url_for('index'))
	with tempfile.TemporaryDirectory() as tmp:
		in_path = os.path.join(tmp, secure_filename(upload.filename))
		upload.save(in_path)
		# Extract audio same as CLI
		audio_wav = os.path.join(tmp, 'audio.wav')
		subprocess.run(['ffmpeg','-y','-i', in_path, '-vn','-acodec','pcm_s16le','-ar','48000','-ac','2', audio_wav], check=True)
		msg = video_dec_mod.decode_audio_stego(audio_wav, frame_duration=frame_duration, compare_fraction=compare_fraction)
		return jsonify({ 'message': msg if msg is not None else '' })


if __name__ == '__main__':
	app.run(debug=True)
