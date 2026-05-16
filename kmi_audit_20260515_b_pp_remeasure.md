# KMI-strict audit — 2026-05-15

Per Phase 2.5 of IMPLEMENTATION_PLAN.md. Measures, per OEM-prebuilt `.ko`, whether it loads against our post-Phase-1 KMI-canonicalized kernel, and aggregates into a Phase-6 boot prediction.

Audit inputs:
- Kernel Module.symvers: `/home/jmulesa/android/lineage/out/target/product/infiniti/obj/KERNEL_OBJ/Module.symvers`
- AOSP whitelist (qcom + oplus + base): **4696** symbols
- Local extension whitelist (oneplus_15 + _extras): **10545** symbols
- OEM modules audited: **557** (of which **0** are in modules.load)

## module_layout CRC — single-symbol veto

Per IMPLEMENTATION_PLAN §1.2, `module_layout` CRC mismatch makes NO module load regardless of any other consideration.

- match:    **0**
- mismatch: **557**
- missing:  **0** (kernel doesn't export `module_layout` at all — would be a Phase-1 regression)
- absent:   **0** (no `__versions` section)

**VETO ACTIVE.** Phase 6 boot prediction is moot until this is resolved. Investigate before any further analysis.

## Distribution

Verdict counts across the OEM corpus.

| Verdict | Full corpus | In `modules.load` (boot-loaded) |
|---|---:|---:|
| `load-clean` | 0 | 0 |
| `load-fail-missing` | 0 | 0 |
| `load-fail-crc` | 0 | 0 |
| `load-fail-module-layout` | 557 | 0 |
| `no-versions` | 0 | 0 |
| `excluded-source-built-override` | 0 | 0 |
| **TOTAL** | **557** | **0** |

**Phase 6 boot prediction (today):** 0/0 modules in modules.load resolve cleanly (0.0%).

## Secondary verdict — assuming `module_layout` canonicalized

If we canonicalize `module_layout` (by source-building all modules against our kernel, OR by aligning kernel headers with OEM's), what fails next? This is the planning view for post-veto cleanup.

| Verdict | Boot-loaded count |
|---|---:|
| `load-clean` | 0 |
| `load-fail-missing` | 0 |
| `load-fail-crc` | 0 |
| `no-versions` | 0 |
| `excluded-source-built-override` | 0 |

**Phase 6 boot prediction (after `module_layout` fix):** 0/0 = 0.0%. The delta between 0.0% (today) and 0.0% (post-fix) is the leverage of the single-symbol fix.

## Per-subsystem breakdown (boot-loaded only)

Primary verdicts (today, with `module_layout` veto active):

| Subsystem | Total | clean | fail-missing | fail-crc | fail-module-layout | no-versions | src-built |
|---|---:|---:|---:|---:|---:|---:|---:|

Secondary verdicts (after `module_layout` canonicalization):

| Subsystem | Total | clean | fail-missing | fail-crc | no-versions | src-built |
|---|---:|---:|---:|---:|---:|---:|

## High-leverage canonicalization extensions

Missing vendor-internal symbols ranked by how many boot-loaded OEM modules reference them. Adding the top N to our union whitelist + EXPORT_SYMBOL'ing the producer (where available in our kernel source) unlocks all listed modules.

### Top 30 missing symbols (boot-loaded modules only)

| Symbol | Boot modules referencing |
|---|---:|

## Bucket C scope recommendation

Subsystems ranked by load-fail count in boot-loaded set (higher = more Bucket-C-source-build pressure):

| Subsystem | Load-fail count |
|---|---:|

Interpretation guidance:

- If a subsystem is 100% load-clean → already Phase-6-ready.
- If load-fail is concentrated on a few high-leverage symbols → extending canonicalization (whitelist + maybe a one-line EXPORT) is cheaper than source-build.
- If load-fail-crc dominates → header/struct divergence; source-build is the only path (canonicalization can't fix CRC).
- If load-fail-missing dominates with diffuse symbols → vendor-heavy subsystem; full source-build required.


---

## Delta vs baseline

Baseline rows: **652**, new rows: **557**, in common: **557** (new-only: 0, baseline-only: 95).

### Aggregate flip counts

| Transition | Modules |
|---|---:|
| flipped: load-fail → load-clean (UNLOCK) | **0** |
| flipped: load-clean → load-fail (REGRESSION) | 0 |
| changed verdict within load-fail-* | 0 |
| unchanged load-clean | 0 |
| unchanged load-fail-* | 557 |

### Per-subsystem delta (boot-relevant transitions)

Captures the partial-convergence-with-subsystem-stratification case: which subsystems converged and which didn't. The post-change Bucket C scope is the union of `unchanged_fail` columns (subsystems still requiring source-build) plus any new `to_fail` regressions.

| Subsystem | to_clean | to_fail | within_fail | unchanged_clean | unchanged_fail |
|---|---:|---:|---:|---:|---:|
| audio | 0 | 0 | 0 | 0 | 29 |
| boot-deviceinfo | 0 | 0 | 0 | 0 | 1 |
| bt | 0 | 0 | 0 | 0 | 4 |
| camera | 0 | 0 | 0 | 0 | 2 |
| charger | 0 | 0 | 0 | 0 | 3 |
| dfr | 0 | 0 | 0 | 0 | 21 |
| dft | 0 | 0 | 0 | 0 | 2 |
| display | 0 | 0 | 0 | 0 | 1 |
| fingerprint | 0 | 0 | 0 | 0 | 1 |
| firmware-virt | 0 | 0 | 0 | 0 | 16 |
| gpu | 0 | 0 | 0 | 0 | 2 |
| graphics-video | 0 | 0 | 0 | 0 | 2 |
| haptic | 0 | 0 | 0 | 0 | 1 |
| misc | 0 | 0 | 0 | 0 | 320 |
| mm | 0 | 0 | 0 | 0 | 3 |
| mm-driver | 0 | 0 | 0 | 0 | 6 |
| network | 0 | 0 | 0 | 0 | 39 |
| regulator-pmic | 0 | 0 | 0 | 0 | 22 |
| rproc-glink | 0 | 0 | 0 | 0 | 9 |
| sched-pm | 0 | 0 | 0 | 0 | 2 |
| secure | 0 | 0 | 0 | 0 | 10 |
| thermal | 0 | 0 | 0 | 0 | 3 |
| touch | 0 | 0 | 0 | 0 | 27 |
| usb | 0 | 0 | 0 | 0 | 21 |
| wlan | 0 | 0 | 0 | 0 | 10 |

