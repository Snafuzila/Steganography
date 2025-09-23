import tkinter as tk
from tkinter import filedialog, messagebox
import os
from stego_core import encode_message, decode_message

print("✅ GUI script is running")

def browse_wav():
    path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
    if path:
        wav_path.set(path)
        update_max_chars(path)

def browse_message():
    path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
    if path:
        msg_path.set(path)

def update_max_chars(path):
    try:
        import wave
        with wave.open(path, 'rb') as f:
            frames = f.getnframes()
        n = int(lsb.get())
        capacity = (frames * n) // 8
        max_label.config(text=f"Max chars: {capacity}")
    except Exception as e:
        max_label.config(text="Max chars: ?")

def embed():
    try:
        pw = password.get()
        if not pw:
            raise ValueError("Password is required.")

        audio = wav_path.get()
        out_folder = os.path.join(os.path.dirname(audio), "output_files")
        os.makedirs(out_folder, exist_ok=True)

        filename = os.path.basename(audio).replace(".wav", "_hidden.wav")
        out = os.path.join(out_folder, filename)

        msg = msg_path.get() if msg_path.get() else message_entry.get()
        n = int(lsb.get())

        encode_message(audio, msg, out, n_lsb=n, password=pw)
        messagebox.showinfo("Success", f"Message hidden in:\n{out}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def extract():
    try:
        pw = password.get()
        if not pw:
            raise ValueError("Password is required.")

        audio = wav_path.get()
        n = int(lsb.get())
        result = decode_message(audio, n_lsb=n, password=pw)
        messagebox.showinfo("Recovered Message", result)
    except Exception as e:
        messagebox.showerror("Error", str(e))

root = tk.Tk()
root.title("Audio Steganography")

wav_path = tk.StringVar()
msg_path = tk.StringVar()
password = tk.StringVar()
lsb = tk.StringVar(value="1")

tk.Label(root, text="WAV File:").grid(row=0, column=0, sticky="e")
tk.Entry(root, textvariable=wav_path, width=40).grid(row=0, column=1)
tk.Button(root, text="Browse", command=browse_wav).grid(row=0, column=2)

tk.Label(root, text="Message:").grid(row=1, column=0, sticky="e")
message_entry = tk.Entry(root, width=40)
message_entry.grid(row=1, column=1)
tk.Button(root, text="From File", command=browse_message).grid(row=1, column=2)

tk.Label(root, text="Password:").grid(row=2, column=0, sticky="e")
tk.Entry(root, textvariable=password, show="*", width=40).grid(row=2, column=1)

tk.Label(root, text="LSBs:").grid(row=3, column=0, sticky="e")
tk.Spinbox(root, from_=1, to=3, textvariable=lsb, width=5, command=lambda: update_max_chars(wav_path.get())).grid(row=3, column=1, sticky="w")

max_label = tk.Label(root, text="Max chars: ?")
max_label.grid(row=3, column=2)

tk.Button(root, text="🔐 Embed Message", command=embed, bg="#aaffaa").grid(row=4, column=0, pady=10)
tk.Button(root, text="🕵️ Extract Message", command=extract, bg="#aaaaff").grid(row=4, column=1, pady=10)

root.mainloop()
