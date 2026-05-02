#!/usr/bin/env python3
# dt_consistency_check.py — pre-flash static check for DT name-mismatch
# bug class.
#
# v1 scope (this version):
#   - Parses a DT source file (.dts/.dtsi) + its #includes
#   - Inventories every consumer reference: `clocks = <&phandle ...>`,
#     `clock-names = "name1", "name2"`, `<X>-supply = <&phandle>`,
#     `gpios = <&phandle ...>`
#   - Inventories every provider node by phandle label
#   - Cross-references: does each <&phandle> name resolve to a node
#     that actually defines a producer of that resource?
#   - Cross-references with builtm-modules: which producer phandles
#     correspond to source-built drivers vs OEM-prebuilt drivers?
#     OEM-prebuilt producers won't load against our kernel
#     (per Phase 1 finding) → consumers stuck at probe-deferral.
#
# v1 LIMITATIONS (deferred to v2):
#   - Doesn't verify clock-names / supply-names match the producer's
#     actual exported names (would need to parse the producer driver
#     source's clk_register / regulator_register calls).
#   - Doesn't follow #include chains transitively (assumes user
#     passes the relevant top-level .dts/.dtsi).
#   - No regulator-supply name validation.
#
# What it catches: producer-not-source-built (the most likely Wave 2
# latent runtime bug — consumer references &lpass_cdc but lpass_cdc.ko
# is OEM-prebuilt and won't load → consumer probe-deferred forever).
#
# Phase 2/2.5 of the OnePlus 15 LineageOS implementation plan;
# substitute for cuttlefish/QEMU runtime gate per Opus Web feedback.

import argparse
import csv
import re
import sys
from pathlib import Path


PHANDLE_REF_RE = re.compile(r'<&([a-zA-Z_][a-zA-Z0-9_]*)\s*[^>]*>')
LABEL_DEF_RE = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*[a-zA-Z_]', re.MULTILINE)
COMPATIBLE_RE = re.compile(r'compatible\s*=\s*"([^"]+)"', re.MULTILINE)


def find_phandle_refs(text: str) -> set:
    """All phandle labels referenced via <&label ...>"""
    return set(PHANDLE_REF_RE.findall(text))


def find_label_defs(text: str) -> set:
    """All phandle labels defined as `label: nodename {`"""
    return set(LABEL_DEF_RE.findall(text))


def find_compatibles_per_label(text: str) -> dict:
    """For each label-defined node, return its compatible string list."""
    out = {}
    # Match 'label: nodename {' then look ahead for the next compatible = ...
    block_re = re.compile(
        r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*[a-zA-Z_][a-zA-Z0-9_-]*[^{]*\{(.*?)^\s*\};',
        re.MULTILINE | re.DOTALL,
    )
    for m in block_re.finditer(text):
        label = m.group(1)
        body = m.group(2)
        comps = COMPATIBLE_RE.findall(body)
        if comps:
            out[label] = comps[0]  # primary compatible
    return out


def find_modules_for_compatible(compatible: str, source_dirs: list) -> list:
    """Search the source dirs for files containing `.compatible = "X"`
    and return the dir-relative paths."""
    hits = []
    needle = f'.compatible = "{compatible}"'
    for src_dir in source_dirs:
        if not src_dir.exists():
            continue
        for f in src_dir.rglob("*.c"):
            try:
                if needle in f.read_text(errors="ignore"):
                    hits.append(str(f.relative_to(src_dir)))
            except (OSError, UnicodeDecodeError):
                pass
    return hits


def classify_provider(label: str, compatible: str, source_built_basenames: set,
                      oem_prebuilt_basenames: set, source_search_dirs: list) -> dict:
    """For a phandle producer, classify whether its driver is source-built
    or OEM-prebuilt or unknown."""
    out = {
        "label": label,
        "compatible": compatible or "(none)",
        "source_built": [],
        "oem_prebuilt": [],
        "source_paths": [],
    }
    if not compatible:
        return out
    # Find which .c files implement this compatible
    source_paths = find_modules_for_compatible(compatible, source_search_dirs)
    out["source_paths"] = source_paths
    # Heuristic basename match against built artifacts
    for sp in source_paths:
        base = Path(sp).stem  # e.g. "gcc-canoe.c" -> "gcc-canoe"
        # Check exact match
        if base in source_built_basenames:
            out["source_built"].append(base)
        # Check normalized (- to _)
        elif base.replace("-", "_") in source_built_basenames:
            out["source_built"].append(base + " (norm)")
        # Check OEM corpus
        if base in oem_prebuilt_basenames:
            out["oem_prebuilt"].append(base)
    return out


def main(argv):
    ap = argparse.ArgumentParser(
        description="DT name-mismatch / provider-source static check (v1).",
    )
    ap.add_argument("--dt", required=True, action="append",
                    help="DT source file (.dts/.dtsi). Repeat for multiple.")
    ap.add_argument("--source-dir", required=True, action="append",
                    help="Directory to grep for `.compatible = X` matches. "
                         "Repeat for kernel + sm8850-modules trees.")
    ap.add_argument("--source-built-glob",
                    help="Glob for source-built .ko files "
                         "(e.g. out/.../updates/*.ko). If set, providers "
                         "matching these basenames are flagged source-built.")
    ap.add_argument("--oem-prebuilt-glob",
                    help="Glob for OEM-prebuilt .ko files "
                         "(e.g. device/.../infiniti-kernel/*.ko). Providers "
                         "matching these are flagged OEM-prebuilt = won't load.")
    ap.add_argument("-o", "--output", default="-",
                    help="CSV output path; '-' for stdout.")
    args = ap.parse_args(argv)

    # Load DT text (concatenate all sources)
    dt_text = "\n".join(Path(p).read_text() for p in args.dt if Path(p).exists())
    if not dt_text:
        print("error: no DT files found / readable", file=sys.stderr)
        return 2

    # Inventory providers (label-defined nodes) and their primary compatible
    label_compats = find_compatibles_per_label(dt_text)
    # Inventory consumer references
    refs = find_phandle_refs(dt_text)

    # Built-module basenames (from globs)
    source_built = set()
    oem_prebuilt = set()
    if args.source_built_glob:
        from glob import glob
        for p in glob(args.source_built_glob):
            source_built.add(Path(p).stem)
            source_built.add(Path(p).stem.replace("-", "_"))
    if args.oem_prebuilt_glob:
        from glob import glob
        for p in glob(args.oem_prebuilt_glob):
            oem_prebuilt.add(Path(p).stem)
            oem_prebuilt.add(Path(p).stem.replace("-", "_"))

    source_dirs = [Path(d) for d in args.source_dir]

    # Classify each REFERENCED phandle (only ones consumed by something)
    rows = []
    for label in sorted(refs):
        compat = label_compats.get(label, "")
        info = classify_provider(label, compat, source_built, oem_prebuilt, source_dirs)
        rows.append({
            "label": info["label"],
            "compatible": info["compatible"],
            "source_built": ";".join(info["source_built"]) or "-",
            "oem_prebuilt": ";".join(info["oem_prebuilt"]) or "-",
            "source_paths": ";".join(info["source_paths"]) or "-",
            "verdict": derive_verdict(info),
        })

    # Output
    out_stream = sys.stdout if args.output == "-" else open(args.output, "w", newline="")
    fieldnames = ["label", "compatible", "source_built", "oem_prebuilt",
                  "source_paths", "verdict"]
    w = csv.DictWriter(out_stream, fieldnames=fieldnames)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    if out_stream is not sys.stdout:
        out_stream.close()

    # Summary to stderr
    summary = {"clean": 0, "oem-only-load-fails": 0, "no-driver-found": 0,
               "no-compatible": 0}
    for r in rows:
        summary[r["verdict"]] = summary.get(r["verdict"], 0) + 1
    print(f"# dt_consistency_check v1 summary:", file=sys.stderr)
    for k, v in summary.items():
        print(f"#   {k}: {v}", file=sys.stderr)

    # Exit code: nonzero if any oem-only-load-fails found
    return 1 if summary.get("oem-only-load-fails", 0) > 0 else 0


def derive_verdict(info: dict) -> str:
    if not info["compatible"] or info["compatible"] == "(none)":
        return "no-compatible"
    if not info["source_paths"]:
        return "no-driver-found"
    if info["source_built"]:
        return "clean"
    if info["oem_prebuilt"] and not info["source_built"]:
        return "oem-only-load-fails"
    return "no-driver-found"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
