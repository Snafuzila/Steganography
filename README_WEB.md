# Web UI for Steganography (Flask)

## Setup
1. Create and activate venv (Windows PowerShell):
   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install deps:
   ```powershell
   pip install -r requirements.txt
   ```
3. Ensure `openssl` is available in PATH. On Windows, install from official source or via Git for Windows.

## Run
```powershell
$env:FLASK_APP="app.py"
python app.py
```

Open `http://localhost:5000`.

Uploads go to `uploads/`. Encoded files saved to `wav_files/output_files/`. 