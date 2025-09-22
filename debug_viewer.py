from colorama import init, Fore, Style

init(autoreset=True)

def whitespace_to_bits(line):
    if line.endswith(' \n') or line.endswith('\t\n'):
        last = line[-2]
        if last == ' ':
            return '0'
        elif last == '\t':
            return '1'
    return None

def binary_to_text(binary):
    chars = [binary[i:i+8] for i in range(0, len(binary), 8)]
    return ''.join(chr(int(b, 2)) for b in chars if len(b) == 8)

def debug_stego_lines(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    report = []
    bits = ''

    print("\n🧪 Debugging whitespace stego content:\n")

    for i, line in enumerate(lines):
        b = whitespace_to_bits(line)
        if b is not None:
            color = Fore.BLUE if b == '0' else Fore.RED
            label = 'SPACE' if b == '0' else 'TAB'
            print(f"Line {i+1:02d} ends with: {color}{label}{Style.RESET_ALL} → bit: {b}")
            report.append(f"Line {i+1:02d} ends with: {label} → bit: {b}")
            bits += b

    print(f"\n🧩 Full bit stream ({len(bits)} bits):")
    print(Fore.YELLOW + bits + Style.RESET_ALL)
    report.append(f"\nFull bit stream ({len(bits)} bits):\n{bits}")

    text = binary_to_text(bits)
    print("\n🔓 Extracted characters:")
    print(Fore.GREEN + text + Style.RESET_ALL)
    report.append(f"\nExtracted characters:\n{text}")

    # שמירת דוח לקובץ
    with open("debug_output.txt", 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    print("\n📄 Debug report saved to debug_output.txt")

# === Run ===
if __name__ == "__main__":
    debug_stego_lines("stego_output.txt")
