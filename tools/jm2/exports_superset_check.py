#!/usr/bin/env python3
# exports_superset_check.py — pre-flash static check for the
# "source-built .ko is missing EXPORT_SYMBOLs that the OEM prebuilt
# offered" bug class.
#
# Surfaced 2026-05-02 by sub-wave 2C v2: brunch-closeout depmod failed
# because OEM-prebuilt audio modules (oplus_audio_daemon, machine_dlkm)
# consume EXPORT_SYMBOLs that adsp-loader.c gates behind
# `#ifdef OPLUS_ARCH_EXTENDS`. Source-built adsp_loader_dlkm omitted
# the define → omitted the exports → depmod unresolved-symbol.
#
# Rule: every source-built .ko that has an OEM-prebuilt counterpart must
# export a SUPERSET of the OEM's exports. Additive is fine; missing is
# a bug.
#
# Peer to dt_consistency_check.py: same playbook (static, pre-flash,
# CSV out, nonzero exit on bug class).
#
# v1 LIMITATIONS:
#   - Doesn't validate symbol *signatures* (CRC __versions). vermagic
#     gate handles that at modprobe time; this tool is about presence.
#   - Doesn't follow MODULE_ALIAS chains.
#   - Heuristic OEM counterpart match (basename + hyphen/underscore).

import argparse
import csv
import re
import subprocess
import sys
from glob import glob
from pathlib import Path


KSYMTAB_RE = re.compile(r'\b__ksymtab_(\S+)$')


def get_exports(ko_path: Path) -> set:
    """Extract EXPORT_SYMBOL names from a .ko via llvm-nm.
    EXPORT_SYMBOL(foo) emits a __ksymtab_foo entry in the symbol table."""
    try:
        out = subprocess.check_output(
            ["llvm-nm", "--defined-only", str(ko_path)],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8", errors="ignore")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()
    exports = set()
    for line in out.splitlines():
        m = KSYMTAB_RE.search(line)
        if m:
            exports.add(m.group(1))
    return exports


def find_oem_counterpart(name: str, oem_dir: Path) -> Path | None:
    """Try exact match, then hyphen/underscore variants."""
    if not oem_dir.exists():
        return None
    candidates = [
        name,
        name.replace("_", "-"),
        name.replace("-", "_"),
    ]
    for cand in candidates:
        p = oem_dir / f"{cand}.ko"
        if p.exists():
            return p
    return None


def classify(src_exports: set, oem_exports: set) -> str:
    # NOTE: "no-oem-counterpart" is decided in main() based on whether
    # find_oem_counterpart() returned None — NOT here. This function
    # only decides the verdict assuming both sides exist; both-empty
    # is a legitimate pass-exact (e.g. no-op stubs, leaf consumers).
    missing = oem_exports - src_exports
    added = src_exports - oem_exports
    if missing:
        return "fail-missing-exports"
    if added:
        return "pass-additive"
    return "pass-exact"


def main(argv):
    ap = argparse.ArgumentParser(
        description="Source-built vs OEM-prebuilt EXPORT_SYMBOL "
                    "superset-rule static check (v1).",
    )
    ap.add_argument("--source-built-glob", required=True,
                    help="Glob for source-built .ko files "
                         "(e.g. out/.../updates/*.ko or **/*.ko).")
    ap.add_argument("--oem-dir", required=True,
                    help="Directory containing OEM-prebuilt .ko files "
                         "(e.g. device/oneplus/infiniti-kernel).")
    ap.add_argument("-o", "--output", default="-",
                    help="CSV output path; '-' for stdout.")
    ap.add_argument("--verbose", action="store_true",
                    help="Print per-module symbol diffs to stderr.")
    args = ap.parse_args(argv)

    oem_dir = Path(args.oem_dir)
    if not oem_dir.exists():
        print(f"error: oem dir not found: {oem_dir}", file=sys.stderr)
        return 2

    src_paths = [Path(p) for p in glob(args.source_built_glob, recursive=True)]
    if not src_paths:
        print(f"error: no source-built .ko matched glob: "
              f"{args.source_built_glob}", file=sys.stderr)
        return 2

    rows = []
    for src in sorted(src_paths):
        name = src.stem
        oem = find_oem_counterpart(name, oem_dir)
        src_exports = get_exports(src)
        oem_exports = get_exports(oem) if oem else set()
        verdict = classify(src_exports, oem_exports)
        if oem is None:
            verdict = "no-oem-counterpart"
        missing = sorted(oem_exports - src_exports)
        added = sorted(src_exports - oem_exports)
        rows.append({
            "module": name,
            "src_export_count": len(src_exports),
            "oem_export_count": len(oem_exports),
            "missing_count": len(missing),
            "added_count": len(added),
            "missing_exports": ";".join(missing) or "-",
            "added_exports": ";".join(added) or "-",
            "verdict": verdict,
        })
        if args.verbose and (missing or added):
            print(f"# {name}: missing={missing} added={added}",
                  file=sys.stderr)

    out_stream = sys.stdout if args.output == "-" else open(args.output, "w", newline="")
    fieldnames = ["module", "src_export_count", "oem_export_count",
                  "missing_count", "added_count",
                  "missing_exports", "added_exports", "verdict"]
    w = csv.DictWriter(out_stream, fieldnames=fieldnames)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    if out_stream is not sys.stdout:
        out_stream.close()

    summary = {}
    for r in rows:
        summary[r["verdict"]] = summary.get(r["verdict"], 0) + 1
    print(f"# exports_superset_check v1 summary:", file=sys.stderr)
    for k in sorted(summary):
        print(f"#   {k}: {summary[k]}", file=sys.stderr)

    return 1 if summary.get("fail-missing-exports", 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
