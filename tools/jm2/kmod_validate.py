#!/usr/bin/env python3
# kmod_validate.py — per-module ABI validator
#
# Given a built .ko, this answers two questions:
#   1. Will it load against our source-built kernel?
#      (vermagic match + every __versions CRC found in our Module.symvers)
#   2. How KMI-clean is its surface?
#      (fraction of __versions symbols on the GKI stablelist union)
#
# Outputs one CSV row per .ko on stdout (or merged into a file via -o).
# Designed for batch use: `find … -name '*.ko' | xargs kmod_validate.py`.
#
# Phase 2 of the OnePlus 15 LineageOS implementation plan
# (kernel/oneplus/sm8850-modules/IMPLEMENTATION_PLAN.md §5).

import argparse
import csv
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

# llvm-objcopy / llvm-readelf from AOSP prebuilts (handles aarch64 cleanly,
# the host binutils do not).
LLVM_BIN = Path("/home/jmulesa/android/lineage/prebuilts/clang/host/linux-x86/clang-r563880c/bin")
OBJCOPY = LLVM_BIN / "llvm-objcopy"
READELF = LLVM_BIN / "llvm-readelf"
NM = LLVM_BIN / "llvm-nm"


def parse_modinfo(ko_path: Path) -> dict:
    """Pull the .modinfo section, return key=value dict."""
    try:
        out = subprocess.run(
            [str(READELF), "-p", ".modinfo", str(ko_path)],
            check=True, capture_output=True, text=True
        ).stdout
    except subprocess.CalledProcessError:
        return {}
    info = {}
    # llvm-readelf -p output: '[ offset] key=value' lines
    for line in out.splitlines():
        m = re.match(r"^\[\s*[0-9a-f]+\]\s+(.*?)$", line)
        if not m:
            continue
        kv = m.group(1)
        if "=" not in kv:
            continue
        k, _, v = kv.partition("=")
        # Some keys repeat (parm, parmtype, import_ns, alias…); keep first.
        info.setdefault(k.strip(), v.strip())
    return info


def parse_versions(ko_path: Path) -> list:
    """Extract __versions section, return list of (symbol, crc32) tuples.

    Each entry is 64 bytes: 8-byte little-endian CRC + 56-byte NUL-padded name.
    Returns [] if section is absent or empty.
    """
    import tempfile
    raw = b""
    # objcopy writes the file via a separate fd; we must close + reopen
    # rather than using tempfile's persistent fd or we read 0 bytes.
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        out_path = tf.name
    try:
        try:
            subprocess.run(
                [str(OBJCOPY), "-O", "binary",
                 "--only-section=__versions", str(ko_path), out_path],
                check=True, capture_output=True
            )
        except subprocess.CalledProcessError:
            return []
        with open(out_path, "rb") as f:
            raw = f.read()
    finally:
        try:
            os.unlink(out_path)
        except FileNotFoundError:
            pass
    entries = []
    for i in range(0, len(raw), 64):
        chunk = raw[i:i+64]
        if len(chunk) < 64:
            break
        crc = struct.unpack("<Q", chunk[:8])[0] & 0xFFFFFFFF
        name = chunk[8:].rstrip(b"\0").decode("utf-8", errors="ignore")
        if name:
            entries.append((name, crc))
    return entries


def parse_module_symvers(symvers_path: Path) -> dict:
    """Parse a kbuild Module.symvers file. Returns dict: symbol -> (crc32, source, kind)."""
    out = {}
    with open(symvers_path) as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            crc_str, name, source = parts[0], parts[1], parts[2]
            kind = parts[3] if len(parts) > 3 else ""
            try:
                crc = int(crc_str, 16) & 0xFFFFFFFF
            except ValueError:
                continue
            out[name] = (crc, source, kind)
    return out


def parse_undefined(ko_path: Path) -> set:
    """nm -u over the .ko, return set of unresolved symbol names."""
    try:
        out = subprocess.run(
            [str(NM), "-u", str(ko_path)],
            check=True, capture_output=True, text=True
        ).stdout
    except subprocess.CalledProcessError:
        return set()
    syms = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-2].lower() == "u":
            syms.add(parts[-1])
        elif len(parts) == 1:
            syms.add(parts[0])
    return syms


def load_stablelist(path: Path) -> set:
    """Load AOSP-style symbol list (lines under '[abi_symbol_list]' header,
    or a flat one-symbol-per-line file).
    """
    symbols = set()
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("[") or s.startswith("#"):
                continue
            symbols.add(s)
    return symbols


def vermagic_release(s: str) -> str:
    """Pull the kernel-release prefix off a vermagic string.

    'vermagic=6.12.23-4k-gdaa2b7eae23f-dirty SMP preempt …' →
       '6.12.23-4k-gdaa2b7eae23f-dirty'
    """
    return s.split(None, 1)[0] if s else ""


def validate(ko_path: Path, symvers: dict, stablelist: set,
             expected_release: str) -> dict:
    info = parse_modinfo(ko_path)
    name = info.get("name", ko_path.stem)
    vermagic = info.get("vermagic", "")
    release = vermagic_release(vermagic)
    intree = info.get("intree", "")
    scmversion = info.get("scmversion", "")

    versions = parse_versions(ko_path)
    has_versions = len(versions) > 0

    crc_match = 0
    crc_mismatch = 0
    crc_unknown = 0
    sample_mismatches = []
    for sym, crc in versions:
        if sym in symvers:
            kcrc = symvers[sym][0]
            if kcrc == crc:
                crc_match += 1
            else:
                crc_mismatch += 1
                if len(sample_mismatches) < 5:
                    sample_mismatches.append(f"{sym}({crc:08x}!={kcrc:08x})")
        else:
            crc_unknown += 1
    crc_match_rate = (crc_match / len(versions)) if versions else 0.0

    kmi_clean_count = sum(1 for sym, _ in versions if sym in stablelist)
    kmi_clean_rate = (kmi_clean_count / len(versions)) if versions else 0.0

    undefined = parse_undefined(ko_path)
    # An "unresolved" symbol is undefined in the .ko AND not in our Module.symvers
    # (where it would be resolvable at modprobe time).
    unresolved = undefined - set(symvers.keys())

    # Verdict ladder: hard fails first.
    if not vermagic:
        verdict = "fail-no-vermagic"
    elif expected_release and release != expected_release:
        verdict = "fail-vermagic-mismatch"
    elif crc_mismatch > 0:
        verdict = "fail-crc-mismatch"
    elif crc_unknown > 0:
        verdict = "fail-crc-unknown-symbol"
    elif unresolved:
        verdict = "fail-unresolved-imports"
    else:
        verdict = "pass"

    return {
        "module": name,
        "path": str(ko_path),
        "size_kb": round(ko_path.stat().st_size / 1024, 1),
        "intree": intree,
        "scmversion": scmversion,
        "vermagic_release": release,
        "vermagic_match": "yes" if release == expected_release else "no",
        "has_versions": int(has_versions),
        "versions_count": len(versions),
        "crc_match": crc_match,
        "crc_mismatch": crc_mismatch,
        "crc_unknown": crc_unknown,
        "crc_match_rate": round(crc_match_rate, 4),
        "kmi_clean_count": kmi_clean_count,
        "kmi_clean_rate": round(kmi_clean_rate, 4),
        "undefined_count": len(undefined),
        "unresolved_count": len(unresolved),
        "verdict": verdict,
        "sample_mismatches": ";".join(sample_mismatches),
    }


CSV_FIELDS = [
    "module", "path", "size_kb",
    "intree", "scmversion", "vermagic_release", "vermagic_match",
    "has_versions", "versions_count",
    "crc_match", "crc_mismatch", "crc_unknown", "crc_match_rate",
    "kmi_clean_count", "kmi_clean_rate",
    "undefined_count", "unresolved_count",
    "verdict", "sample_mismatches",
]


def main(argv):
    ap = argparse.ArgumentParser(
        description="Per-module ABI validator. Outputs CSV.",
    )
    ap.add_argument("--symvers", required=True, action="append",
                    help="Path to a Module.symvers file. May be repeated for "
                         "external module trees so intermodule references "
                         "resolve. Pass the kernel's Module.symvers first.")
    ap.add_argument("--stablelist",
                    help="AOSP-format or flat symbol list to compute KMI-cleanliness against")
    ap.add_argument("--expected-release",
                    help="Expected kernel release string (vermagic prefix). "
                         "If omitted, derived from `Module.symvers`'s parent dir.")
    ap.add_argument("-o", "--output", default="-",
                    help="Output CSV path; '-' for stdout (default)")
    ap.add_argument("--header", action="store_true",
                    help="Always emit CSV header (default: yes when --output is a file)")
    ap.add_argument("--no-header", action="store_true",
                    help="Suppress CSV header")
    ap.add_argument("ko", nargs="+", help="Module .ko files to validate")
    args = ap.parse_args(argv)

    # Merge all symvers files; first arg wins on conflicts (kernel takes precedence).
    symvers = {}
    for p in reversed(args.symvers):
        for k, v in parse_module_symvers(Path(p)).items():
            symvers[k] = v
    # Then re-overlay first arg so kernel exports always win.
    for k, v in parse_module_symvers(Path(args.symvers[0])).items():
        symvers[k] = v
    stablelist = load_stablelist(Path(args.stablelist)) if args.stablelist else set()
    expected_release = args.expected_release or ""
    if not expected_release:
        # Heuristic: walk up from kernel Module.symvers looking for kernel.release.
        kernel_symvers = Path(args.symvers[0])
        for parent in [kernel_symvers.parent, kernel_symvers.parent.parent]:
            kr = parent / "include/config/kernel.release"
            if kr.exists():
                expected_release = kr.read_text().strip()
                break

    rows = []
    for kop in args.ko:
        kp = Path(kop)
        if not kp.exists():
            print(f"warning: {kop} not found", file=sys.stderr)
            continue
        rows.append(validate(kp, symvers, stablelist, expected_release))

    out_stream = sys.stdout if args.output == "-" else open(args.output, "w", newline="")
    write_header = not args.no_header and (args.header or args.output != "-")
    w = csv.DictWriter(out_stream, fieldnames=CSV_FIELDS)
    if write_header:
        w.writeheader()
    for row in rows:
        w.writerow(row)
    if out_stream is not sys.stdout:
        out_stream.close()


if __name__ == "__main__":
    main(sys.argv[1:])
