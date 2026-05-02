#!/usr/bin/env python3
# wave_gate.py — per-wave hard gate
#
# Each Bucket-C wave's completion criteria: every module in the wave's
# manifest builds, has correct vermagic, has matching CRCs against the
# kernel's Module.symvers, and resolves all imports against either the
# kernel or a sibling-module .ko.
#
# Run after a wave's wire-up is putatively complete. Exits non-zero
# on any failure. Surfaces *which* modules fail and why so the wave
# can iterate without a re-run.
#
# Manifest format: one module name per line, optional comment after '#'.
# Example:
#   # Wave 3 — DFR framework
#   oplus_bsp_dfr_combkey_monitor
#   oplus_bsp_dfr_dump_reason
#   oplus_bsp_dfr_init_watchdog
#   ...
#
# Phase 2 of the OnePlus 15 LineageOS implementation plan.

import argparse
import csv
import sys
from pathlib import Path


def read_manifest(path: Path) -> list:
    out = []
    for line in path.read_text().splitlines():
        s = line.split("#", 1)[0].strip()
        if s:
            out.append(s)
    return out


def read_csv(path: Path) -> list:
    return list(csv.DictReader(path.read_text().splitlines()))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", required=True,
                    help="Wave manifest: one module name per line")
    ap.add_argument("--csv", required=True,
                    help="kmod_validate.py CSV covering at least the wave's modules")
    ap.add_argument("--allow-unresolved", type=int, default=0,
                    help="Tolerate up to N unresolved imports per module "
                         "(useful when a wave depends on a future wave)")
    args = ap.parse_args(argv)

    expected = set(read_manifest(Path(args.wave)))
    rows = read_csv(Path(args.csv))
    by_name = {r["module"]: r for r in rows}

    missing = sorted(expected - set(by_name))
    if missing:
        for m in missing:
            print(f"FAIL: {m}: module not built (no row in CSV)")

    failures = list(missing)  # treat missing as failures by name
    for name in sorted(expected & set(by_name)):
        r = by_name[name]
        verdict = r["verdict"]
        unresolved = int(r.get("unresolved_count", "0"))
        if verdict == "pass":
            continue
        if verdict == "fail-unresolved-imports" and unresolved <= args.allow_unresolved:
            print(f"WARN: {name}: {unresolved} unresolved (within --allow-unresolved)")
            continue
        sample = r.get("sample_mismatches", "")
        sample_str = f"  ({sample})" if sample else ""
        print(f"FAIL: {name}: {verdict}{sample_str}")
        failures.append(name)

    print()
    print(f"wave: {len(expected)} expected, "
          f"{len(expected & set(by_name))} built, "
          f"{len(expected) - len(failures)} pass, "
          f"{len(failures)} fail")

    if failures:
        return 1
    print("OK: wave gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
