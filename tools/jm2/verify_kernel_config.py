#!/usr/bin/env python3
"""verify_kernel_config.py — pre-flight gate for kernel config-fragment work.

Asserts that a built kernel binary (vmlinux) actually has the CONFIG
values you intended. Catches the failure mode where a config fragment
is committed to `arch/arm64/configs/` but never wired into
`TARGET_KERNEL_CONFIG`, so Kbuild's merge step never sees it and the
shipped kernel reflects the dev-baseline rather than the intended
profile.

This check is INVISIBLE from build output alone. The fragment author
sees a clean `m bootimage` exit, a clean kmi_audit run, and an
internally-consistent verdict — none of which expose the real
discrepancy. Only IKCONFIG extraction from the shipped vmlinux reveals
that the binary doesn't reflect the intended config.

Use this BEFORE treating any kmi_audit result, CRC analysis, or
config-flip experiment outcome as load-bearing. It's cheap (~200ms
on a 200MB vmlinux) and prevents an entire class of unmeasured-flip
mistakes.

## Background

The 2026-05-12 Path B'' "ZERO convergence" verdict was authored from
audit output produced against the May-12 vmlinux, which still had all
12 B'' flags = y. The fragment was committed but never wired into
TARGET_KERNEL_CONFIG. Discovered 2026-05-15 during Phase 6 boot-failure
investigation. See kmi_strict_audit.md "Re-validation 2026-05-15 —
actual B'' measurement" and DEFERRED_FOLLOWUPS.md "Pre-flight
verification gate for config-fragment work" for the full story.

## Usage

Verify a single flag:

    verify_kernel_config.py \\
        --vmlinux out/target/product/infiniti/obj/KERNEL_OBJ/vmlinux \\
        --expected CONFIG_KASAN=n

Verify a batch from a fragment file (parses `# CONFIG_X is not set`
and `CONFIG_X=y/m/n/string` lines):

    verify_kernel_config.py \\
        --vmlinux out/target/product/infiniti/obj/KERNEL_OBJ/vmlinux \\
        --expected-from arch/arm64/configs/production_profile.config

Combined with mtime-advance check (assert vmlinux is newer than a
reference timestamp — useful for verifying a rebuild actually happened):

    verify_kernel_config.py \\
        --vmlinux ... \\
        --expected-from production_profile.config \\
        --reference-mtime 1715800000

## Exit codes

  0 — all expectations match (or the only mismatches are Kconfig-pinned
      flags listed in --tolerated-pinned)
  1 — at least one expectation does not match the built kernel
  2 — script error (missing vmlinux, can't extract ikconfig, etc.)

## Tolerated mismatches

Some flags are pinned by Kconfig select-chains: even if you set
`# CONFIG_X is not set`, another fragment's `CONFIG_Y=y` may select X.
Path B'' identified DEBUG_KERNEL and LIST_HARDENED as such.
`--tolerated-pinned CONFIG_X` causes verify to report a mismatch as a
WARNING (still exits 0). Use sparingly and document each one.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
KERNEL_TREE_DEFAULT = SCRIPT_DIR.parent.parent.parent / "sm8850"
EXTRACT_IKCONFIG_DEFAULT = KERNEL_TREE_DEFAULT / "scripts" / "extract-ikconfig"

CONFIG_LINE_SET = re.compile(r"^(CONFIG_[A-Z0-9_]+)=(.*)$")
CONFIG_LINE_NOT_SET = re.compile(r"^# (CONFIG_[A-Z0-9_]+) is not set$")


def parse_config_text(text: str) -> dict[str, str]:
    """Parse a Kconfig file (.config or fragment) into {name: value}.

    Values are 'y', 'm', 'n' (for `is not set`), or a quoted/unquoted
    string for non-tristate symbols.
    """
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            m = CONFIG_LINE_NOT_SET.match(line)
            if m:
                out[m.group(1)] = "n"
            continue
        m = CONFIG_LINE_SET.match(line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def extract_ikconfig(vmlinux: Path, extract_tool: Path) -> dict[str, str]:
    """Run extract-ikconfig on vmlinux, parse the embedded .config."""
    if not extract_tool.exists() or not os.access(extract_tool, os.X_OK):
        sys.exit(f"error: extract-ikconfig not executable at {extract_tool}")
    try:
        result = subprocess.run(
            [str(extract_tool), str(vmlinux)],
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        sys.exit(f"error: extract-ikconfig failed: {e.stderr}")
    return parse_config_text(result.stdout)


def parse_expected_args(expected: list[str]) -> dict[str, str]:
    """Parse --expected CONFIG=value entries."""
    out: dict[str, str] = {}
    for entry in expected:
        if "=" not in entry:
            sys.exit(f"error: --expected '{entry}' missing = (use CONFIG_X=y/m/n/value)")
        name, value = entry.split("=", 1)
        if not name.startswith("CONFIG_"):
            sys.exit(f"error: --expected '{entry}': name must start with CONFIG_")
        out[name] = value
    return out


def parse_expected_from_files(paths: Iterable[Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in paths:
        if not p.exists():
            sys.exit(f"error: --expected-from path does not exist: {p}")
        out.update(parse_config_text(p.read_text()))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="verify_kernel_config.py",
        description="Verify shipped kernel binary actually has intended CONFIG values.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit 0 = all expectations satisfied (or only WARNINGs from "
            "--tolerated-pinned).\nExit 1 = at least one mismatch.\n"
            "Exit 2 = script error."
        ),
    )
    ap.add_argument(
        "--vmlinux", required=True, type=Path,
        help="Path to vmlinux (the binary to verify)",
    )
    ap.add_argument(
        "--expected", action="append", default=[], metavar="CONFIG_X=value",
        help="Expected CONFIG entry (repeatable). Value: y/m/n or string.",
    )
    ap.add_argument(
        "--expected-from", action="append", default=[], type=Path, metavar="PATH",
        help="Expected CONFIG entries from a Kconfig fragment file (repeatable).",
    )
    ap.add_argument(
        "--reference-mtime", type=float, default=None, metavar="EPOCH",
        help="Assert vmlinux mtime > this epoch second (rebuild-happened check).",
    )
    ap.add_argument(
        "--ikconfig-extract", type=Path, default=EXTRACT_IKCONFIG_DEFAULT,
        help=f"Path to extract-ikconfig (default: {EXTRACT_IKCONFIG_DEFAULT})",
    )
    ap.add_argument(
        "--tolerated-pinned", action="append", default=[], metavar="CONFIG_X",
        help=(
            "Treat mismatches for these flags as WARNING (still exit 0). "
            "Use for Kconfig-pinned flags like DEBUG_KERNEL or LIST_HARDENED. "
            "Repeatable. Document why each is tolerated in the caller's notes."
        ),
    )
    ap.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print all checks, not just mismatches.",
    )
    args = ap.parse_args(argv)

    if not args.vmlinux.exists():
        print(f"error: vmlinux not found at {args.vmlinux}", file=sys.stderr)
        return 2

    if args.reference_mtime is not None:
        actual_mtime = args.vmlinux.stat().st_mtime
        if actual_mtime <= args.reference_mtime:
            print(
                f"FAIL: vmlinux mtime check — vmlinux mtime "
                f"{actual_mtime:.0f} <= reference {args.reference_mtime:.0f}. "
                "Kernel did NOT rebuild since reference timestamp.",
                file=sys.stderr,
            )
            return 1
        if args.verbose:
            print(
                f"OK:   vmlinux mtime {actual_mtime:.0f} > reference "
                f"{args.reference_mtime:.0f} ({actual_mtime - args.reference_mtime:.0f}s newer)"
            )

    expected = parse_expected_args(args.expected)
    expected.update(parse_expected_from_files(args.expected_from))

    if not expected:
        print("error: no expectations provided (use --expected or --expected-from)", file=sys.stderr)
        return 2

    actual = extract_ikconfig(args.vmlinux, args.ikconfig_extract)
    if not actual:
        print("error: ikconfig extraction returned no data", file=sys.stderr)
        return 2

    tolerated = set(args.tolerated_pinned)
    failures: list[tuple[str, str, str]] = []
    warnings: list[tuple[str, str, str]] = []

    for name, want in expected.items():
        # Treat absent symbols as "n" (Kconfig default for unset bool).
        got = actual.get(name, "n")
        if got != want:
            entry = (name, want, got)
            if name in tolerated:
                warnings.append(entry)
            else:
                failures.append(entry)
        elif args.verbose:
            print(f"OK:   {name}={want}")

    if warnings:
        print("\nTolerated pinned mismatches (Kconfig select-chain — exit 0):", file=sys.stderr)
        for name, want, got in warnings:
            print(f"  WARN  {name}: want={want} got={got}", file=sys.stderr)

    if failures:
        print(
            f"\nFAIL: {len(failures)} of {len(expected)} expectations not satisfied "
            "by shipped kernel:",
            file=sys.stderr,
        )
        for name, want, got in failures:
            print(f"  FAIL  {name}: want={want} got={got}", file=sys.stderr)
        print(
            "\nThe vmlinux at "
            f"{args.vmlinux}\ndoes not match the intended config. "
            "Likely root cause: fragment not wired into TARGET_KERNEL_CONFIG, "
            "or .config layered in an unexpected order, or build cache stale.",
            file=sys.stderr,
        )
        return 1

    n = len(expected)
    n_warn = len(warnings)
    print(f"OK: {n - n_warn}/{n} CONFIG expectations satisfied (vmlinux: {args.vmlinux})")
    if warnings:
        print(f"    + {n_warn} tolerated pinned mismatches (above)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
