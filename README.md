# 🧠 Initial Project Specification Document

---

## 📌 Project Name
**StegX – A Steganography System for Encryption and Information Concealment**

## 📚 Course Name
**Steganography Project – Holon Institute of Technology - 2025, Semester B**

---

## 👥 Team Members
- Noiman Ron  
- Kunin Daniel  
- Chayut Dor  
- Attiya Boaz  
- Lamay Ofek  

## 👨‍🏫 Instructor
**Zimon Roi**

---

## 1. 🧾 General Background

The need for privacy, confidentiality, and secure information transmission has become more prevalent in the digital age.  
This project involves developing a system that implements **steganography principles** — concealing information inside digital files in a way that is invisible to the eye.

The system will allow users to **embed files or text** into various formats such as images, audio files, videos, and documents — using dedicated hiding algorithms, **without visibly altering the file**.

Additionally, the project includes developing a **user-friendly interface** and the ability to **extract hidden information**, with **optional encryption** and basic content protection.

---

## 2. 🎯 Objectives and Goals

### 🎯 **Project Objective**
Build a complete steganographic system that enables **transparent data hiding** (text, files) in various formats, while **preserving the integrity** of the outer file.

### ✅ **Main Goals**
- Develop dedicated algorithms for **data hiding and extraction**
- Support the following formats: `PNG`, `BMP`, `WAV`, `AVI`, `MKV`, `MOV`, `TEXT`, `HTML`, `CSS`
- Build an **internal encryption mechanism (AES-256)** to maintain confidentiality
- Develop a **user-friendly interface** (initially CLI, potentially GUI later)
- Document all code and algorithms clearly
- Perform **tests and experiments** using various file types

---

## 3. 🧪 Technological Overview

### 🐍 **Programming Language**
- **Python** – Chosen for its strong support in digital file processing, encryption, UI frameworks, and vast library ecosystem.

### 📚 **Relevant Libraries (selected or under consideration)**
- `Pillow` – Image file processing  
- `PyDub`, `wave` – Audio file handling  
- `PyCryptodome` – Encryption  
- `PyMuPDF`, `python-docx` – Document (PDF, DOCX) handling  
- `Tkinter` or `PyQt` – GUI interface (if GUI development is selected)

### 📂 **Supported Formats**
- **Images:** PNG, BMP  
- **Audio:** WAV  
- **Video:** AVI, MKV, MOV  
- **Text/Documents:** TEXT, HTML, CSS  

### 🧠 **Selected Algorithms**
- **LSB (Least Significant Bit):** For embedding in images (`PNG`, `BMP`) and audio (`WAV`)  
- **Whitespace Steganography:** For hiding text in `TEXT`, `HTML`, `CSS` documents  
- **Comparison of Samples (השוואת סימפולים):** For embedding in video (`AVI`, `MKV`, `MOV`)

---

## 🔮 Future Implementation Recommendations
- Share code and logic between handling `WAV` and future support for `FLAC` (Echo Hiding)
- Explore and evaluate existing Python libraries such as `pydub`, `PyPDF2`, `python-docx`
- Organize the project using **modular structure** – one class/module per format
- Create **test cases** to validate that the **original content is not altered**

---
