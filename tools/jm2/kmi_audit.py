#!/usr/bin/env python3
# kmi_audit.py — KMI-strict audit of the OEM-prebuilt .ko corpus.
#
# Phase 2.5 deliverable (IMPLEMENTATION_PLAN.md §2.5). Measures, per
# OEM-prebuilt .ko, whether it will load against our post-Phase-1
# KMI-canonicalized kernel, and aggregates the result into a
# Phase-6 boot prediction.
#
# Per-module verdicts:
#   load-clean                       — every __versions sym resolves with matching CRC
#   load-fail-crc                    — sym present in our Module.symvers but CRC differs
#   load-fail-missing                — sym absent from our Module.symvers entirely
#   load-fail-module-layout          — module_layout CRC differs (single-symbol veto)
#   no-versions                      — .ko has no __versions section (rare; FORCE_LOAD-ish)
#   excluded-source-built-override   — a same-name source-built .ko exists; OEM prebuilt won't ship
#
# Classification per consumed symbol (within a load-clean OR load-fail module):
#   kmi-pure          — symbol is on the AOSP-canonical stablelist
#                       (gki/aarch64/symbols/{qcom,oplus,base}, ~4,738 syms)
#   kmi-extended      — symbol is in our local union/extras whitelist but NOT on AOSP
#                       canonical; "vendor-internal-but-we-export-it"
#   vendor-internal   — symbol is not in any whitelist; either kernel-internal export
#                       harvested through TRIM_UNUSED_KSYMS or missing from our build
#
# Re-runnable. Diff successive CSV runs to measure progress after
# canonicalization extensions or kernel changes.
#
# Usage:
#   tools/jm2/kmi_audit.py \
#       --kernel-symvers $OUT/obj/KERNEL_OBJ/Module.symvers \
#       --kmi-aosp-whitelist gki/aarch64/symbols/qcom \
#       --kmi-aosp-whitelist gki/aarch64/symbols/oplus \
#       --kmi-aosp-whitelist gki/aarch64/symbols/base \
#       --kmi-local-extension android/abi_gki_aarch64_oneplus_15 \
#       --kmi-local-extension android/abi_gki_aarch64_oneplus_15_extras \
#       --oem-corpus device/oneplus/infiniti-kernel \
#       --oem-corpus $OUT/system_dlkm/lib/modules \
#       --source-built-corpus $OUT/obj/PACKAGING/kernel_modules_intermediates/.../updates \
#       --modules-load $OUT/vendor_dlkm/lib/modules/modules.load \
#       --modules-load $OUT/system_dlkm/lib/modules/modules.load \
#       --csv-out kmi_audit_$(date +%F).csv \
#       --md-out kmi_strict_audit.md

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

# Reuse parsers from kmod_validate.py (sibling in tools/jm2/).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kmod_validate import (  # noqa: E402
    parse_modinfo,
    parse_versions,
    parse_module_symvers,
    load_stablelist,
)


# Subsystem clustering by .ko filename. Ordered: first-match wins.
SUBSYSTEM_PATTERNS = [
    (re.compile(r"^(msm_drm|display|dsi|dpu|iris|drm_panel|sde_)"), "display"),
    (re.compile(r"^(msm_kgsl|kgsl|adreno|gpu)"), "gpu"),
    (re.compile(r"^(msm-eva|msm_eva|msm_video|video[-_])"), "graphics-video"),
    (re.compile(r"^(msm_hw_fence|msm-mmrm|msm_hfi|sync_fence|msm_ext_display|synx)"), "mm-driver"),
    (re.compile(r"^(camera|cam_|oplus_camera|spectra)"), "camera"),
    (re.compile(r"^(cnss|qca|wlan|icnss)"), "wlan"),
    (re.compile(r"^(bt|btpower|btfm|btfmcodec|btfm_slim|bt_fm|bluetooth)"), "bt"),
    (re.compile(r"^(nfc_|nq-nci|pn5|nxp_)"), "nfc"),
    (re.compile(r"^(audio_|q6|adsp_|wcd|lpass|swr|aw87|tas|cs35|cirrus|machine|asoc|hdmi_)"), "audio"),
    (re.compile(r"^(oplus_chg|charger|chargepump|voocphy|ufcs|gauge|hboost)"), "charger"),
    (re.compile(r"^(oplus_bsp_tp_|oplus_hbp|synaptics|goodix|focal|novatek|ilitek|ft3|gt9|nt3|s39)"), "touch"),
    (re.compile(r"^(oplus_bsp_uff|uff_fp|goodix_fp|fingerprint|fp_drv)"), "fingerprint"),
    (re.compile(r"^(haptic|vibrator|qti_haptics|qcom-hv-haptics)"), "haptic"),
    (re.compile(r"^(oplus_bsp_dfr|dfr|panic|ramdump|ramoops|crashdump|minidump)"), "dfr"),
    (re.compile(r"^(oplus_network|rmnet|mhi|ip[46]_|kshark|ipa_|datarmnet)"), "network"),
    (re.compile(r"^(oplus_bsp_dft|olc|kevent|fb_kevent)"), "dft"),
    (re.compile(r"^(oplus_bsp_boot|cmdline|device_info|bootmode|oplus_projectinfo|oplus_proc)"), "boot-deviceinfo"),
    (re.compile(r"^(secure|qseecom|tz_log|qcrypto|smcinvoke|qrng|qcedev|hdcp|smmu_proxy|qce|spu_)"), "secure"),
    (re.compile(r"^(mm_|oplus_bsp_mm|osvelte|oplus_mm|mtk_oom)"), "mm"),
    (re.compile(r"^(amoled|.*adc|.*pmic|.*pm8|.*regulator|qpnp|spmi)"), "regulator-pmic"),
    (re.compile(r"^(sched|walt|cpufreq|lpm|idle|qcom-cpuss)"), "sched-pm"),
    (re.compile(r"^(qcom_glink|qcom_smd|qcom_smp2p|qcom_rpmsg|qcom_q6v5|qcom_sysmon|qcom_pil|rproc_qcom)"), "rproc-glink"),
    (re.compile(r"^(qcom_scm|qcom-scm|gh_|gunyah|hyp_|scmi)"), "firmware-virt"),
    (re.compile(r"^(thermal|cpu_cooling|qcom_thermal|qcom-spmi-temp)"), "thermal"),
    (re.compile(r"^(usb_|dwc3|f_qdss|coresight)"), "usb"),
    (re.compile(r"^(esim|sim_|modem)"), "modem-radio"),
]


def classify_subsystem(name: str) -> str:
    for pat, cluster in SUBSYSTEM_PATTERNS:
        if pat.search(name):
            return cluster
    return "misc"


def audit_module(ko_path: Path,
                 kernel_symvers: dict,
                 aosp_whitelist: set,
                 local_whitelist: set,
                 source_built_names: set,
                 modules_load_names: set) -> dict:
    """Run KMI audit on one OEM .ko. Returns one CSV-row dict."""
    info = parse_modinfo(ko_path)
    name = info.get("name", ko_path.stem.replace("-", "_"))
    # Module filename may use - while modinfo.name uses _; canonicalize for cross-ref.
    canon = name.replace("-", "_")
    file_canon = ko_path.stem.replace("-", "_")

    in_modules_load = (canon in modules_load_names) or (file_canon in modules_load_names)
    source_built_override = (canon in source_built_names) or (file_canon in source_built_names)

    versions = parse_versions(ko_path)
    if not versions:
        return {
            "module": ko_path.stem,
            "modinfo_name": name,
            "path": str(ko_path),
            "subsystem": classify_subsystem(ko_path.stem),
            "in_modules_load": int(in_modules_load),
            "source_built_override": int(source_built_override),
            "n_versions": 0,
            "n_kmi_pure": 0,
            "n_kmi_extended": 0,
            "n_vendor_internal_resolved": 0,
            "n_vendor_internal_missing": 0,
            "n_crc_mismatch": 0,
            "module_layout_status": "absent",
            "verdict": "excluded-source-built-override" if source_built_override else "no-versions",
            "sample_failing": "",
        }

    n_kmi_pure = 0
    n_kmi_extended = 0
    n_vendor_resolved = 0  # in our Module.symvers but not on any whitelist
    n_vendor_missing = 0
    n_crc_mismatch = 0
    module_layout_status = "absent"
    failing_samples: list[str] = []

    for sym, crc in versions:
        in_kernel = sym in kernel_symvers
        kernel_crc = kernel_symvers[sym][0] if in_kernel else None
        crc_ok = (kernel_crc == crc) if in_kernel else False
        on_aosp = sym in aosp_whitelist
        on_local = sym in local_whitelist

        if sym == "module_layout":
            if not in_kernel:
                module_layout_status = "missing"
            elif crc_ok:
                module_layout_status = "match"
            else:
                module_layout_status = f"mismatch({crc:08x}!={kernel_crc:08x})"

        if not in_kernel:
            n_vendor_missing += 1
            if len(failing_samples) < 8:
                failing_samples.append(f"{sym}=missing")
            continue
        if not crc_ok:
            n_crc_mismatch += 1
            if len(failing_samples) < 8:
                failing_samples.append(f"{sym}=crc({crc:08x}!={kernel_crc:08x})")
            continue
        # Resolved. Classify by whitelist membership.
        if on_aosp:
            n_kmi_pure += 1
        elif on_local:
            n_kmi_extended += 1
        else:
            n_vendor_resolved += 1

    # module_layout participates in n_crc_mismatch when mismatched. To compute
    # the "what if module_layout were fixed" secondary verdict, subtract it.
    layout_mismatched = module_layout_status.startswith("mismatch")
    layout_missing = module_layout_status == "missing"
    secondary_crc_mismatch = n_crc_mismatch - (1 if layout_mismatched else 0)
    secondary_vendor_missing = n_vendor_missing - (1 if layout_missing else 0)

    # Primary verdict ladder (module_layout veto applies — runtime reality).
    if source_built_override:
        verdict = "excluded-source-built-override"
    elif layout_mismatched or layout_missing:
        verdict = "load-fail-module-layout"
    elif n_crc_mismatch > 0:
        verdict = "load-fail-crc"
    elif n_vendor_missing > 0:
        verdict = "load-fail-missing"
    else:
        verdict = "load-clean"

    # Secondary verdict — what the module would resolve to AFTER module_layout
    # is canonicalized. Useful for planning the post-veto cleanup work.
    if source_built_override:
        secondary_verdict = "excluded-source-built-override"
    elif secondary_crc_mismatch > 0:
        secondary_verdict = "load-fail-crc"
    elif secondary_vendor_missing > 0:
        secondary_verdict = "load-fail-missing"
    else:
        secondary_verdict = "load-clean"

    return {
        "module": ko_path.stem,
        "modinfo_name": name,
        "path": str(ko_path),
        "subsystem": classify_subsystem(ko_path.stem),
        "in_modules_load": int(in_modules_load),
        "source_built_override": int(source_built_override),
        "n_versions": len(versions),
        "n_kmi_pure": n_kmi_pure,
        "n_kmi_extended": n_kmi_extended,
        "n_vendor_internal_resolved": n_vendor_resolved,
        "n_vendor_internal_missing": n_vendor_missing,
        "n_crc_mismatch": n_crc_mismatch,
        "module_layout_status": module_layout_status,
        "verdict": verdict,
        "secondary_verdict": secondary_verdict,
        "sample_failing": ";".join(failing_samples),
    }


CSV_FIELDS = [
    "module", "modinfo_name", "path", "subsystem",
    "in_modules_load", "source_built_override",
    "n_versions",
    "n_kmi_pure", "n_kmi_extended",
    "n_vendor_internal_resolved", "n_vendor_internal_missing",
    "n_crc_mismatch",
    "module_layout_status",
    "verdict", "secondary_verdict", "sample_failing",
]


VERDICT_ORDER = [
    "load-clean",
    "load-fail-missing",
    "load-fail-crc",
    "load-fail-module-layout",
    "no-versions",
    "excluded-source-built-override",
]


def load_baseline_csv(path: Path) -> dict:
    """Load a prior kmi_audit run's CSV. Returns {module: row}."""
    out = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            out[row["module"]] = row
    return out


def render_delta(rows: list[dict], baseline: dict) -> str:
    """Compute and render the delta vs baseline as markdown."""
    new_by = {r["module"]: r for r in rows}
    common = set(new_by) & set(baseline)
    only_new = set(new_by) - set(baseline)
    only_old = set(baseline) - set(new_by)

    flipped_to_clean: list[tuple[str, str, str]] = []  # (module, old_v, subsys)
    flipped_to_fail: list[tuple[str, str, str, str]] = []  # (module, old_v, new_v, subsys)
    verdict_changed_within_fail: list[tuple[str, str, str, str]] = []
    unchanged_clean = 0
    unchanged_fail = 0

    subsys_flip: dict[str, dict[str, int]] = defaultdict(
        lambda: {"to_clean": 0, "to_fail": 0, "within_fail": 0,
                 "unchanged_clean": 0, "unchanged_fail": 0}
    )

    for m in sorted(common):
        old_v = baseline[m]["verdict"]
        new_v = new_by[m]["verdict"]
        subsys = new_by[m]["subsystem"]
        if old_v == new_v:
            if new_v == "load-clean":
                unchanged_clean += 1
                subsys_flip[subsys]["unchanged_clean"] += 1
            elif new_v.startswith("load-fail"):
                unchanged_fail += 1
                subsys_flip[subsys]["unchanged_fail"] += 1
        else:
            if new_v == "load-clean":
                flipped_to_clean.append((m, old_v, subsys))
                subsys_flip[subsys]["to_clean"] += 1
            elif new_v.startswith("load-fail") and old_v == "load-clean":
                flipped_to_fail.append((m, old_v, new_v, subsys))
                subsys_flip[subsys]["to_fail"] += 1
            elif new_v.startswith("load-fail") and old_v.startswith("load-fail"):
                verdict_changed_within_fail.append((m, old_v, new_v, subsys))
                subsys_flip[subsys]["within_fail"] += 1

    out: list[str] = []
    out.append("\n---\n")
    out.append("## Delta vs baseline\n")
    out.append(f"Baseline rows: **{len(baseline)}**, new rows: **{len(new_by)}**, "
               f"in common: **{len(common)}** "
               f"(new-only: {len(only_new)}, baseline-only: {len(only_old)}).\n")
    out.append("### Aggregate flip counts\n")
    out.append("| Transition | Modules |")
    out.append("|---|---:|")
    out.append(f"| flipped: load-fail → load-clean (UNLOCK) | **{len(flipped_to_clean)}** |")
    out.append(f"| flipped: load-clean → load-fail (REGRESSION) | {len(flipped_to_fail)} |")
    out.append(f"| changed verdict within load-fail-* | {len(verdict_changed_within_fail)} |")
    out.append(f"| unchanged load-clean | {unchanged_clean} |")
    out.append(f"| unchanged load-fail-* | {unchanged_fail} |")
    out.append("")

    if flipped_to_clean:
        boot_unlocked = sum(1 for m, _, _ in flipped_to_clean
                            if new_by[m]["in_modules_load"] == "1")
        out.append(f"**{boot_unlocked} of the {len(flipped_to_clean)} unlocked modules "
                   "are in `modules.load`** (the load-bearing count for Phase 6 boot).\n")

    out.append("### Per-subsystem delta (boot-relevant transitions)\n")
    out.append("Captures the partial-convergence-with-subsystem-stratification case: "
               "which subsystems converged and which didn't. The post-change Bucket C "
               "scope is the union of `unchanged_fail` columns (subsystems still requiring "
               "source-build) plus any new `to_fail` regressions.\n")
    out.append("| Subsystem | to_clean | to_fail | within_fail | unchanged_clean | unchanged_fail |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for cluster in sorted(subsys_flip.keys()):
        c = subsys_flip[cluster]
        out.append(f"| {cluster} | {c['to_clean']} | {c['to_fail']} | "
                   f"{c['within_fail']} | {c['unchanged_clean']} | {c['unchanged_fail']} |")
    out.append("")

    # Show a sample of the actual flips (most interesting: to_clean first).
    if flipped_to_clean:
        out.append("### Sample of unlocked modules (first 30, sorted by subsystem)\n")
        out.append("| Module | Subsystem | Was |")
        out.append("|---|---|---|")
        for m, old_v, subsys in sorted(flipped_to_clean, key=lambda x: (x[2], x[0]))[:30]:
            out.append(f"| `{m}` | {subsys} | `{old_v}` |")
        out.append("")
    if flipped_to_fail:
        out.append("### REGRESSIONS — modules that were clean and now aren't\n")
        out.append("| Module | Subsystem | Was → Is |")
        out.append("|---|---|---|")
        for m, old_v, new_v, subsys in sorted(flipped_to_fail, key=lambda x: (x[3], x[0])):
            out.append(f"| `{m}` | {subsys} | `{old_v}` → `{new_v}` |")
        out.append("")

    return "\n".join(out) + "\n"


def render_markdown(rows: list[dict],
                    kernel_symvers_path: Path,
                    aosp_count: int,
                    local_count: int,
                    rerun_extras: dict) -> str:
    """Compose the analysis markdown."""
    today = date.today().isoformat()
    total = len(rows)

    # Distribution table (full + boot-loaded only).
    verdict_full = Counter(r["verdict"] for r in rows)
    verdict_boot = Counter(r["verdict"] for r in rows if r["in_modules_load"])
    total_boot = sum(verdict_boot.values())

    # Secondary verdict — what would happen if module_layout were canonicalized.
    secondary_boot = Counter(r["secondary_verdict"] for r in rows if r["in_modules_load"])

    # Per-subsystem breakdown — boot-loaded only.
    subsys_table: dict[str, Counter] = defaultdict(Counter)
    subsys_secondary: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        if r["in_modules_load"]:
            subsys_table[r["subsystem"]][r["verdict"]] += 1
            subsys_secondary[r["subsystem"]][r["secondary_verdict"]] += 1

    # Per-symbol leverage — missing symbols ranked by reference count.
    # Re-derive from rows: re-parse the failing-samples isn't reliable; we
    # need the raw symbol lists. Hand it in via rerun_extras['per_symbol_missing']
    # and rerun_extras['per_symbol_crc_mismatch'].
    per_symbol_missing: Counter = rerun_extras.get("per_symbol_missing", Counter())
    per_symbol_crc: Counter = rerun_extras.get("per_symbol_crc", Counter())

    # Module-layout summary.
    ml_match = sum(1 for r in rows if r["module_layout_status"] == "match")
    ml_mismatch = sum(1 for r in rows
                      if r["module_layout_status"].startswith("mismatch"))
    ml_missing = sum(1 for r in rows if r["module_layout_status"] == "missing")
    ml_absent = sum(1 for r in rows if r["module_layout_status"] == "absent")

    out: list[str] = []
    out.append(f"# KMI-strict audit — {today}\n")
    out.append("Per Phase 2.5 of IMPLEMENTATION_PLAN.md. Measures, per "
               "OEM-prebuilt `.ko`, whether it loads against our post-Phase-1 "
               "KMI-canonicalized kernel, and aggregates into a Phase-6 boot "
               "prediction.\n")
    out.append("Audit inputs:")
    out.append(f"- Kernel Module.symvers: `{kernel_symvers_path}`")
    out.append(f"- AOSP whitelist (qcom + oplus + base): **{aosp_count}** symbols")
    out.append(f"- Local extension whitelist (oneplus_15 + _extras): **{local_count}** symbols")
    out.append(f"- OEM modules audited: **{total}** (of which **{total_boot}** are in modules.load)\n")

    # --- module_layout veto ---
    out.append("## module_layout CRC — single-symbol veto\n")
    out.append("Per IMPLEMENTATION_PLAN §1.2, `module_layout` CRC mismatch "
               "makes NO module load regardless of any other consideration.\n")
    out.append(f"- match:    **{ml_match}**")
    out.append(f"- mismatch: **{ml_mismatch}**")
    out.append(f"- missing:  **{ml_missing}** (kernel doesn't export `module_layout` at all — would be a Phase-1 regression)")
    out.append(f"- absent:   **{ml_absent}** (no `__versions` section)\n")
    if ml_mismatch + ml_missing > 0:
        out.append("**VETO ACTIVE.** Phase 6 boot prediction is moot until "
                   "this is resolved. Investigate before any further analysis.\n")
    else:
        out.append("**VETO CLEAR.** Per-module CRC analysis below is meaningful.\n")

    # --- Distribution ---
    out.append("## Distribution\n")
    out.append("Verdict counts across the OEM corpus.\n")
    out.append("| Verdict | Full corpus | In `modules.load` (boot-loaded) |")
    out.append("|---|---:|---:|")
    for v in VERDICT_ORDER:
        out.append(f"| `{v}` | {verdict_full.get(v, 0)} | {verdict_boot.get(v, 0)} |")
    out.append(f"| **TOTAL** | **{total}** | **{total_boot}** |\n")

    # Phase 6 boot prediction = ratio of load-clean (or excluded-source-built-override) over modules.load.
    boot_ok = verdict_boot.get("load-clean", 0) + verdict_boot.get("excluded-source-built-override", 0)
    boot_pct = (boot_ok / total_boot * 100) if total_boot else 0.0
    out.append(f"**Phase 6 boot prediction (today):** {boot_ok}/{total_boot} modules in "
               f"modules.load resolve cleanly ({boot_pct:.1f}%).\n")

    # Secondary distribution: post-module_layout-fix.
    out.append("## Secondary verdict — assuming `module_layout` canonicalized\n")
    out.append("If we canonicalize `module_layout` (by source-building all modules "
               "against our kernel, OR by aligning kernel headers with OEM's), what "
               "fails next? This is the planning view for post-veto cleanup.\n")
    out.append("| Verdict | Boot-loaded count |")
    out.append("|---|---:|")
    for v in VERDICT_ORDER:
        if v == "load-fail-module-layout":
            continue
        out.append(f"| `{v}` | {secondary_boot.get(v, 0)} |")
    out.append("")
    secondary_ok = secondary_boot.get("load-clean", 0) + secondary_boot.get("excluded-source-built-override", 0)
    secondary_pct = (secondary_ok / total_boot * 100) if total_boot else 0.0
    out.append(f"**Phase 6 boot prediction (after `module_layout` fix):** "
               f"{secondary_ok}/{total_boot} = {secondary_pct:.1f}%. The delta "
               f"between {boot_pct:.1f}% (today) and {secondary_pct:.1f}% (post-fix) "
               "is the leverage of the single-symbol fix.\n")

    # --- Per-subsystem ---
    out.append("## Per-subsystem breakdown (boot-loaded only)\n")
    out.append("Primary verdicts (today, with `module_layout` veto active):\n")
    out.append("| Subsystem | Total | clean | fail-missing | fail-crc | fail-module-layout | no-versions | src-built |")
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for cluster in sorted(subsys_table.keys()):
        c = subsys_table[cluster]
        total_c = sum(c.values())
        out.append(f"| {cluster} | {total_c} | "
                   f"{c.get('load-clean', 0)} | "
                   f"{c.get('load-fail-missing', 0)} | "
                   f"{c.get('load-fail-crc', 0)} | "
                   f"{c.get('load-fail-module-layout', 0)} | "
                   f"{c.get('no-versions', 0)} | "
                   f"{c.get('excluded-source-built-override', 0)} |")
    out.append("")
    out.append("Secondary verdicts (after `module_layout` canonicalization):\n")
    out.append("| Subsystem | Total | clean | fail-missing | fail-crc | no-versions | src-built |")
    out.append("|---|---:|---:|---:|---:|---:|---:|")
    for cluster in sorted(subsys_secondary.keys()):
        c = subsys_secondary[cluster]
        total_c = sum(c.values())
        out.append(f"| {cluster} | {total_c} | "
                   f"{c.get('load-clean', 0)} | "
                   f"{c.get('load-fail-missing', 0)} | "
                   f"{c.get('load-fail-crc', 0)} | "
                   f"{c.get('no-versions', 0)} | "
                   f"{c.get('excluded-source-built-override', 0)} |")
    out.append("")

    # --- High-leverage canonicalization extensions ---
    out.append("## High-leverage canonicalization extensions\n")
    out.append("Missing vendor-internal symbols ranked by how many "
               "boot-loaded OEM modules reference them. Adding the top N to "
               "our union whitelist + EXPORT_SYMBOL'ing the producer (where "
               "available in our kernel source) unlocks all listed modules.\n")
    out.append("### Top 30 missing symbols (boot-loaded modules only)\n")
    out.append("| Symbol | Boot modules referencing |")
    out.append("|---|---:|")
    for sym, count in per_symbol_missing.most_common(30):
        out.append(f"| `{sym}` | {count} |")
    out.append("")
    if per_symbol_crc:
        # module_layout is the headline; pull it out separately so it doesn't
        # dominate the top of the list.
        ml_count = per_symbol_crc.pop("module_layout", 0)
        out.append("### CRC-mismatched symbols (boot-loaded)\n")
        out.append("Symbols our kernel exports but at a different CRC. Indicates "
                   "struct-layout / header divergence between OEM's build and ours. "
                   "Cannot be fixed by whitelist extension; needs source-side "
                   "alignment (header convergence) OR source-build of the consuming "
                   "module against our kernel.\n")
        if ml_count:
            out.append(f"**`module_layout`: {ml_count} boot modules** "
                       "(the veto symbol — single source of the catastrophic "
                       "failure; see veto section above). Listed separately so "
                       "subsequent rows show the second-most-leveraged CRC gaps.\n")
        out.append("### Top 20 non-`module_layout` CRC mismatches\n")
        out.append("| Symbol | Boot modules referencing |")
        out.append("|---|---:|")
        for sym, count in per_symbol_crc.most_common(20):
            out.append(f"| `{sym}` | {count} |")
        out.append("")

    # --- Recommendation ---
    out.append("## Bucket C scope recommendation\n")
    bucket_c_subsys = sorted(
        [(c, sum(v for k, v in counts.items() if k.startswith("load-fail"))) for c, counts in subsys_table.items()],
        key=lambda kv: -kv[1],
    )
    out.append("Subsystems ranked by load-fail count in boot-loaded set "
               "(higher = more Bucket-C-source-build pressure):\n")
    out.append("| Subsystem | Load-fail count |")
    out.append("|---|---:|")
    for cluster, n in bucket_c_subsys:
        if n > 0:
            out.append(f"| {cluster} | {n} |")
    out.append("")
    out.append("Interpretation guidance:\n")
    out.append("- If a subsystem is 100% load-clean → already Phase-6-ready.")
    out.append("- If load-fail is concentrated on a few high-leverage symbols → "
               "extending canonicalization (whitelist + maybe a one-line EXPORT) "
               "is cheaper than source-build.")
    out.append("- If load-fail-crc dominates → header/struct divergence; "
               "source-build is the only path (canonicalization can't fix CRC).")
    out.append("- If load-fail-missing dominates with diffuse symbols → "
               "vendor-heavy subsystem; full source-build required.")
    out.append("")

    return "\n".join(out) + "\n"


def main(argv):
    ap = argparse.ArgumentParser(description="KMI-strict audit of OEM-prebuilt .ko corpus.")
    ap.add_argument("--kernel-symvers", required=True,
                    help="Path to our post-Phase-1 kernel Module.symvers "
                         "(CRC-bearing manifest, ~9,992 lines).")
    ap.add_argument("--kmi-aosp-whitelist", action="append", default=[],
                    help="AOSP-canonical stablelist file (repeatable). "
                         "Typically gki/aarch64/symbols/{qcom,oplus,base}.")
    ap.add_argument("--kmi-local-extension", action="append", default=[],
                    help="Local-union or extras whitelist file (repeatable). "
                         "Typically android/abi_gki_aarch64_oneplus_15{,_extras}.")
    ap.add_argument("--oem-corpus", action="append", required=True,
                    help="Directory containing OEM-prebuilt .ko files. "
                         "Repeatable. All *.ko found are audited.")
    ap.add_argument("--source-built-corpus", action="append", default=[],
                    help="Directory containing our source-built .ko files "
                         "(for source-built-override detection). Repeatable.")
    ap.add_argument("--modules-load", action="append", default=[],
                    help="modules.load file path (repeatable). Names listed "
                         "are flagged in_modules_load=1.")
    ap.add_argument("--csv-out", default="-",
                    help="Per-module CSV output path. '-' = stdout.")
    ap.add_argument("--md-out",
                    help="Markdown analysis output path. Required for aggregate "
                         "tables to be produced.")
    ap.add_argument("--baseline-csv",
                    help="Prior kmi_audit run's CSV. When provided, the markdown "
                         "gets a 'Delta vs baseline' section with per-module flips "
                         "and per-subsystem delta tables — surfaces the partial-"
                         "convergence-with-subsystem-stratification case.")
    args = ap.parse_args(argv)

    kernel_symvers_path = Path(args.kernel_symvers)
    kernel_symvers = parse_module_symvers(kernel_symvers_path)
    print(f"[kmi_audit] Loaded kernel Module.symvers: {len(kernel_symvers)} symbols",
          file=sys.stderr)

    aosp_whitelist: set = set()
    for p in args.kmi_aosp_whitelist:
        before = len(aosp_whitelist)
        aosp_whitelist.update(load_stablelist(Path(p)))
        print(f"[kmi_audit] AOSP whitelist {p}: +{len(aosp_whitelist) - before} (cum {len(aosp_whitelist)})",
              file=sys.stderr)

    local_whitelist: set = set()
    for p in args.kmi_local_extension:
        before = len(local_whitelist)
        local_whitelist.update(load_stablelist(Path(p)))
        print(f"[kmi_audit] Local extension {p}: +{len(local_whitelist) - before} (cum {len(local_whitelist)})",
              file=sys.stderr)

    source_built_names: set = set()
    for d in args.source_built_corpus:
        dp = Path(d)
        if not dp.exists():
            print(f"[kmi_audit] source-built-corpus dir not found: {d}", file=sys.stderr)
            continue
        for ko in dp.rglob("*.ko"):
            source_built_names.add(ko.stem.replace("-", "_"))
    print(f"[kmi_audit] Source-built corpus: {len(source_built_names)} unique names",
          file=sys.stderr)

    modules_load_names: set = set()
    for p in args.modules_load:
        path = Path(p)
        if not path.exists():
            print(f"[kmi_audit] modules.load not found: {p}", file=sys.stderr)
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name = line.replace(".ko", "").replace("-", "_")
            modules_load_names.add(name)
    print(f"[kmi_audit] modules.load: {len(modules_load_names)} unique entries",
          file=sys.stderr)

    # Discover OEM .ko corpus.
    oem_kos: list[Path] = []
    seen: set = set()
    for d in args.oem_corpus:
        dp = Path(d)
        if not dp.exists():
            print(f"[kmi_audit] oem-corpus dir not found: {d}", file=sys.stderr)
            continue
        for ko in sorted(dp.rglob("*.ko")):
            if ko.name in seen:
                continue
            seen.add(ko.name)
            oem_kos.append(ko)
    print(f"[kmi_audit] OEM corpus: {len(oem_kos)} unique .ko files", file=sys.stderr)

    # Run audit. Track per-symbol leverage as we go (need raw symbol lists,
    # not just the truncated sample_failing strings).
    rows: list[dict] = []
    per_symbol_missing: Counter = Counter()
    per_symbol_crc: Counter = Counter()
    for i, ko in enumerate(oem_kos, 1):
        if i % 50 == 0:
            print(f"[kmi_audit] audited {i}/{len(oem_kos)}…", file=sys.stderr)
        row = audit_module(ko, kernel_symvers, aosp_whitelist, local_whitelist,
                           source_built_names, modules_load_names)
        rows.append(row)
        # Per-symbol leverage (boot-loaded modules only): scan __versions again
        # to extract the precise lists. Re-parse rather than caching to keep
        # the audit_module() interface clean.
        if row["in_modules_load"] and row["verdict"] in ("load-fail-missing", "load-fail-crc", "load-fail-module-layout"):
            versions = parse_versions(ko)
            for sym, crc in versions:
                if sym not in kernel_symvers:
                    per_symbol_missing[sym] += 1
                elif kernel_symvers[sym][0] != crc:
                    per_symbol_crc[sym] += 1
    print(f"[kmi_audit] audit complete: {len(rows)} rows", file=sys.stderr)

    # Write CSV.
    if args.csv_out == "-":
        out_f = sys.stdout
    else:
        out_f = open(args.csv_out, "w", newline="")
    w = csv.DictWriter(out_f, fieldnames=CSV_FIELDS)
    w.writeheader()
    for row in rows:
        w.writerow(row)
    if out_f is not sys.stdout:
        out_f.close()
        print(f"[kmi_audit] wrote CSV: {args.csv_out}", file=sys.stderr)

    # Write markdown.
    if args.md_out:
        md = render_markdown(
            rows,
            kernel_symvers_path,
            aosp_count=len(aosp_whitelist),
            local_count=len(local_whitelist),
            rerun_extras={
                "per_symbol_missing": per_symbol_missing,
                "per_symbol_crc": per_symbol_crc,
            },
        )
        if args.baseline_csv:
            baseline = load_baseline_csv(Path(args.baseline_csv))
            print(f"[kmi_audit] baseline: {len(baseline)} rows from {args.baseline_csv}",
                  file=sys.stderr)
            md += render_delta(rows, baseline)
        Path(args.md_out).write_text(md)
        print(f"[kmi_audit] wrote markdown: {args.md_out}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
