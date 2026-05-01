# OnePlus 15 (infiniti) — Implementation Plan

**Date:** 2026-05-01
**Inputs:** `blockers.md` (audit + bucket analysis + KMI strategy), Opus
Web's framing recommendations (KMI-first sequencing, subsystem waves,
translation recipe, validation infrastructure, scope discipline)
**Outcome targeted:** flashable LineageOS 23.2 build that boots on
hardware with a defensible source/prebuilt posture, and from there a
trajectory toward fully source-built externals.

---

## 1. Goals & success criteria

### Minimum Viable Build (MVB) — flash target

The first flashable build must satisfy:

1. Source-built `vmlinux` / `Image` from `kernel/oneplus/sm8850/`,
   built in **GKI/KMI-strict mode**: `Module.symvers` ≈ 4,733 lines
   (the qcom + oplus + base stablelist union), CRCs canonical against
   the `android16-6.12-2025-06_r8` ACK baseline.
2. Source-built `dtb.img` and `dtbo.img` (already done this session,
   carried forward).
3. Modules:
   - **All Bucket A** (122) — already in-tree built.
   - **All Bucket B** (52) — already external-built via `mka kernel`.
   - **All KMI-clean Bucket-C/D residual** stay as **OEM prebuilts**,
     loading via the GKI mechanism against the canonicalized kernel.
   - **All non-KMI prebuilts** (count TBD by Track B — likely 50–80
     modules) are source-built from `vendor/{oplus/kernel,qcom/opensource}/`.
4. Boot validation: every module in `modules.load` either loads
   cleanly or is explicitly marked permitted-fail with rationale.
5. Hardware boot test: device reaches launcher; display, touch,
   WiFi, cellular, audio, camera, fingerprint, NFC, GPS, charging
   all functional or explicitly noted as deferred.

**No FORCE_LOAD, no `CONFIG_MODVERSIONS=n` workarounds**, no Kconfig
stubbing. If a module won't load, it becomes a Bucket C source-build
target rather than a tainted load.

### Final/stretch goal — full source-built externals

Independent of what Track B classification reveals about KMI cleanliness:

**Source-build every module in `vendor/oplus/kernel/` and the
`vendor/qcom/opensource/` subsystems that ship as kernel modules.**
This means even modules Track B classifies as KMI-clean (which would
*work* as prebuilts) are eventually replaced by source builds.

Reasoning: the GKI-sanctioned prebuilt path is correct as MVB but
leaves us dependent on OnePlus blob refreshes for security/CVE work
on those modules. Owning the source build for everything removes
that dependency. This is multi-month work; not part of MVB.

### Bucket D (truly proprietary) — final phase

After full Bucket C source-build, the residual will be the actually
proprietary modules (vendor codec/sensor IPs, possibly some Atmel/STM
touch variants, possibly `qti_amoled_ecm` and a few others). Final
posture for these: GKI-sanctioned prebuilts if KMI-clean, FORCE_LOAD
with documented per-symbol audit otherwise, or accept loss of feature
if neither is acceptable.

---

## 2. Work shape & framing

This is a **translation task**, not a creation task. OnePlus has
authored Bazel `BUILD.bazel` files for every module in scope. Our job
is to translate those Bazel specs into Kbuild Makefiles that
`mka kernel` can consume. Bazel files are ground truth — read them,
don't derive composition from C source.

The unit of work is the **subsystem**, not the module. Bucket C
recovery is ~6–8 subsystem waves (DFR, network, WLAN, Adreno, video,
bt-kernel, smaller miscellany, stretch-goal-only KMI-clean rewrites).
Within each wave, modules share Kbuild idioms, Kconfig fragments,
and dependencies. Work them as units, not individually.

The most important sequencing principle: **measurement before
construction.** Do KMI canonicalization (Track A) and KMI
classification (Track B) before writing any Kbuild file. The
classification CSV tells us how big the construction work actually
is; pre-committing to wire-up before measuring risks doing 200
modules of work that wasn't needed.

---

## 3. Phase 0 — Pre-flight: KMI baseline verification

**Goal:** prove our kernel patches don't break KMI types before
investing in canonicalization. If they do, find that out in hours,
not weeks.

### 0.1 Establish a clean reference baseline

- Identify the exact ACK SHA we're based on: `f1bdb13583da85a47fcf1632a78ef52d6e6da651`
  (`android16-6.12-2025-06_r8`). Confirmed from `android/ACK_SHA`.
- Confirm our HEAD has all 7 jm2 patches applied.
- Diff our HEAD against the ACK SHA. List every changed file. Bucket
  the diff: (a) Kbuild/Makefile/Kconfig/defconfig (KMI-safe by
  construction), (b) init-time wiring (mostly KMI-safe), (c) struct
  definitions / EXPORT_SYMBOL additions / function signatures
  (potentially KMI-affecting).

### 0.2 Run the ABI checker

- Locate the ABI verification tooling. Candidates:
  `kernel/oneplus/sm8850-modules/kernel_platform/build/kernel/abi/`,
  `kernel_platform/build/build_abi.sh`, or the Bazel
  `//build:kernel_aarch64_abi` target.
- Run against our built kernel. Compare resulting `abi.stg` against
  `kernel/oneplus/sm8850/gki/aarch64/abi.stg` (the ACK baseline) and
  `gki/aarch64/abi.stg.allowed_breaks` (any pre-approved deltas).
- If the diff is empty: KMI is intact, proceed to Phase 1.
- If the diff is non-empty: identify which patch caused which break;
  rework patch to stay below KMI surface (most common: move the
  intrusive code to an out-of-tree module instead of touching
  in-tree exports), or escalate to "request stablelist addition" or
  "fall back to bulk wire-up" decision.

### 0.3 Deliverables of Phase 0

- `~/android/kmi_baseline.md` — written record of the patch audit:
  which jm2 patches touch which KMI surface, ABI checker output,
  any required reworks, sign-off statement that the source kernel
  is GKI-compliant.
- Patch reworks (if any) committed as new commits on the affected
  jm2 fork branches.

**Gate:** Phase 1 cannot start until kmi_baseline.md says GO.

**Estimate:** 1 day if patches are clean, up to 1 week if rework
needed.

---

## 4. Phase 1 — Track A: kernel KMI canonicalization

**Goal:** rebuild the source kernel in KMI-strict mode so its
`Module.symvers` shrinks from 18,408 lines to ~4,733 (the qcom + oplus
+ base stablelist union), with canonical CRCs that match the form
OEM-built KMI-clean modules expect.

### 1.1 Wire KMI knobs into our kbuild flow

- Add to defconfig fragment(s):
  ```
  CONFIG_TRIM_UNUSED_KSYMS=y
  ```
- Surface the `KMI_SYMBOL_LIST` variables that
  `build.config.msm.perf` uses for the Kleaf path, into our
  `mka kernel` Make invocation. Equivalent of:
  ```
  KMI_SYMBOL_LIST=android/abi_gki_aarch64_qcom
  KMI_SYMBOL_LIST_ADDITIONS=android/abi_gki_aarch64_oplus
  TRIM_NONLISTED_KMI=1
  ```
  These thread through to scripts/gen_autoksyms.sh and the kbuild's
  `-fdata-sections`/`-ffunction-sections` link path.
- Verify the in-kernel files `android/abi_gki_aarch64_qcom` and
  `android/abi_gki_aarch64_oplus` exist or create symlinks to the
  `gki/aarch64/symbols/{qcom,oplus}` files. This is the file the
  kernel build looks up; the `gki/aarch64/symbols/` versions are
  the AOSP-published source of truth.

### 1.2 Rebuild and verify shrinkage

- `mka kernel` clean rebuild.
- Check `out/target/product/infiniti/obj/KERNEL_OBJ/Module.symvers`
  line count. Expected: ~4,733 (down from 18,408).
- Spot-check fundamental symbols:
  - `_printk` CRC in our Module.symvers
  - Pull `oplus_bsp_haptic.ko` `__versions` section (a known OEM
    prebuilt with `__versions` populated), find its `_printk` CRC
  - **They should now match.** If not, KMI canonicalization isn't
    working — debug before proceeding.
- Verify `module_layout` CRC matches between our kernel and a
  known-good OEM-prebuilt module. This is the single most important
  check; if `module_layout` mismatches, no module loads.

### 1.3 Boot the canonicalized kernel

- Build a full ROM with the canonicalized kernel + the existing
  Bucket A + B source-built modules + the OEM prebuilts (the same
  hybrid we have today).
- Boot in cuttlefish/QEMU if possible, otherwise this becomes a
  Phase 5 task at hardware test time.
- Goal: catch KMI-strict-mode build failures (some in-tree code may
  reference internal symbols that get trimmed) and fix or
  source-build the consumer.

### 1.4 Deliverables of Phase 1

- `kernel/oneplus/sm8850/arch/arm64/configs/lineage_genksyms_workaround.config`
  (or new fragment) updated with the KMI knobs.
- jm2 commit on `kernel/oneplus/sm8850` documenting the change.
- README update.
- Verification log: Module.symvers counts before/after, `_printk`
  CRC match proof, `module_layout` CRC match proof.

**Gate:** Phase 3 cannot start until Track A is verified working.
Phase 2 (validation infrastructure) can run in parallel with Phase 1.

**Estimate:** 2–4 days.

---

## 5. Phase 2 — Validation infrastructure (parallel with Phase 1)

**Goal:** invest one engineer-day in tooling that turns "did the build
succeed?" into "is this module structurally and ABI-correct?" Pays
back across hundreds of modules.

### 2.1 Per-module validator

`tools/kmod_validate.py` (or shell script) — takes a `.ko` and the
running kernel's `Module.symvers`, emits structured report:

| Field | Source |
|-------|--------|
| Module name, vermagic | `modinfo` |
| Has `__versions` section | `eu-readelf -p __versions <ko>` |
| `__versions` symbol count | parse the section |
| CRC match rate vs `Module.symvers` | join by symbol name |
| Unresolved external symbols | `modprobe --dry-run` or our own resolver |
| KMI-cleanliness % | fraction of `__versions` symbols on the qcom+oplus+base stablelist |
| `__init`/`__exit` presence | section scan |
| Verdict | derived: load-clean / load-tainted / load-fail |

Output: one CSV row per module. Append-only log keyed on (module,
build_time).

### 2.2 BUILD.bazel ↔ Kbuild diff checker

`tools/bazel_kbuild_diff.py` — takes a BUILD.bazel target and a
generated Kbuild file, asserts:

- Every `srcs = [...]` entry has a matching `obj-y +=` or `obj-m +=`
  line in the Kbuild
- Every `copts = [...]` flag appears in `ccflags-y` or `CFLAGS_<obj>`
- Every `deps = [...]` is satisfied by the kernel's
  `Module.symvers` or by an earlier Kbuild's `KBUILD_EXTRA_SYMBOLS`
- Every `data = [...]` (firmware blobs, binding header includes)
  has a matching install path

Output: pass/fail with structured diff report. Most wire-up bugs are
"forgot to translate one line of BUILD.bazel"; this catches them in
seconds.

### 2.3 Wave-completion gate

`tools/wave_gate.py` — takes a wave manifest (list of modules
expected to land in this wave), runs `kmod_validate.py` and
`bazel_kbuild_diff.py` on each, asserts:

- Every module in scope produces a `.ko`
- Every `.ko` has correct vermagic
- All CRCs resolve (matching kernel or earlier-wave modules)
- No module is silently missing (`grep -L` against expected list)
- Wave-status doc exists at expected path

If any assertion fails, the wave is incomplete — no advancement to
the next wave. Hard gate.

### 2.4 Deliverables of Phase 2

- Three scripts in `~/android/tools/` (or `lineage/scripts/jm2/`)
- A "validation README" documenting the recipe and gate semantics
- Initial CSV with current state (all 557 prebuilts run through the
  validator pre-Phase-3, so we have a baseline to diff against)

**Estimate:** 1 day, parallel with Phase 1.

---

## 6. Phase 3 — Track B: KMI classification of all 557 prebuilts

**Goal:** measure, don't estimate, how many modules are KMI-clean
vs need source-building.

### 3.1 Run the classifier

For each `.ko` in `device/oneplus/infiniti-kernel/` and each in
`out/target/product/infiniti/vendor_dlkm/lib/modules/`:

1. Extract `__versions` symbol list (the symbols this module imports
   that are validated by CRC at modprobe time).
2. Intersect with the union of `gki/aarch64/symbols/{base,qcom,oplus}`
   (4,733 stablelist symbols).
3. Compute KMI-cleanliness ratio = |intersection| / |__versions|.
4. Classify:
   - **K1 (KMI-clean)**: ratio = 1.0 — module is sanctioned-prebuilt
     against any GKI-compliant Android 16 kernel including ours
     (post Track A).
   - **K2 (borderline)**: 0.8 ≤ ratio < 1.0 — most stable, a few
     internal-API imports. Decision: source-build (preferred), or
     audit the non-KMI symbols for struct-layout safety and accept
     the ABI risk.
   - **K3 (non-KMI)**: ratio < 0.8 — heavily uses internal kernel
     APIs. Must source-build (Bucket C wave).

### 3.2 Output: classification CSV

Sortable by ratio, by subsystem (DFR / network / WLAN / etc.), by
size. Drives Phase 5 wave ordering.

### 3.3 Sanity-check the priors

The pasted analysis suggested 60–70% K1 / 20–30% K2 / 10–15% K3.
Track B may come back materially different (40/40/20 or 80/10/10).
The plan is robust to either: phases 5 / 7+ scale to whatever
Track B says.

If K3 turns out > 200 modules, the MVB scope expands into the
stretch-goal territory and timeline grows. Communicate the actual
number when it lands rather than holding to the prior.

### 3.4 Deliverables of Phase 3

- `~/android/kmi_classification.csv` — one row per prebuilt
- `~/android/phase3_report.md` — written analysis: prior vs measured,
  wave-by-wave count of K3 modules, recommended subset to wire up
  for MVB, recommended subset to defer to stretch-goal phase.
- A *measured* MVB scope: "we need to source-build N modules for the
  flash-test build."

**Estimate:** 1 day.

---

## 7. Phase 4 — Translation recipe + first proof-point module

**Goal:** before scaling wire-up to dozens of modules, write the
recipe down and validate it on one module end-to-end.

### 4.1 Authoring the recipe

`~/android/wire_up_recipe.md` — explicit step-by-step:

- Where to find a module's BUILD.bazel
- How to translate `srcs` / `copts` / `deps` / `data` to
  Kbuild syntax (Makefile + Kbuild + Kconfig)
- How to handle parent-Makefile entries that Bazel elides
- How to author `CONFIG_OPLUS_FEATURE_*` Kconfig stanzas without
  stubbing
- How to declare module dependencies via `KBUILD_EXTRA_SYMBOLS`
- How to surface the new Kbuild from `kernel/oneplus/sm8850-modules/`
  through to `mka kernel` (the Phase A–F integration pattern)
- The validation checklist (vermagic, `__versions`, CRCs,
  modprobe --dry-run, KMI-cleanliness)

This doc is the bus-factor mitigator. If different waves are worked
by different sessions, the recipe is the contract.

### 4.2 Proof-point module

Pick **one** small, well-understood module from Track B's K3 list —
ideally something with few `srcs` and no dependencies, e.g. one of
the OnePlus utility modules. Wire it up end-to-end:

1. Read its BUILD.bazel
2. Apply the recipe to produce Kbuild + Makefile + Kconfig
3. Build via `mka kernel`
4. Run through `kmod_validate.py` and `bazel_kbuild_diff.py`
5. Verify the produced `.ko` loads (modprobe --dry-run + actual
   probe in cuttlefish if available)

Do not estimate the rest of Phase 5+ until this proof-point is
green.

### 4.3 Deliverables of Phase 4

- `wire_up_recipe.md`
- One module wired up + committed, passing all validators

**Estimate:** 2 days (1 day recipe + 1 day proof-point).

---

## 8. Phase 5 — Minimum Viable Build (MVB) wire-up

**Goal:** source-build the K3 (non-KMI) subset Track B identified.
Result is a flashable build that passes the KMI gate cleanly.

### 5.1 Wave order (driven by dependency direction)

Per Opus Web's framing, waves are ordered foundational-first, not
parallel:

1. **Wave 1 — Foundational utilities.** Small modules that other
   modules link against: `oplus_cfg`, `oplus_overlay`, `oplus_patch`,
   anything in `vendor/oplus/kernel/system/` that exports symbols.
   Few deps, unblocks everything.
2. **Wave 2 — In-tree drivers from sm8850 source.** Pinctrl, clock,
   regulator drivers from `kernel/oneplus/sm8850/drivers/` (the
   original 147 estimate). Probe early; deps for almost everything.
3. **Wave 3 — DFR framework.** 13 subsystems under
   `vendor/oplus/kernel/dfr/`. Internally coupled, externally
   simple — touches watchdog/panic which is largely KMI.
4. **Wave 4 — OnePlus network optimization.** Self-contained;
   doesn't block downstream. `vendor/oplus/kernel/network/`.
5. **Wave 5 — WLAN platform + driver.** Hairiest single subsystem.
   Dedicated wave with explicit completion criteria. cnss2 +
   cnss_utils + icnss2 + qcacld-3.0. The success criteria for this
   wave is "WiFi works in cuttlefish/hardware test."
6. **Wave 6 — Adreno GPU.** `vendor/qcom/opensource/graphics-kernel/`,
   ~85 .c files. Self-contained but large.
7. **Wave 7 — Video & Bluetooth.** `video-driver/`, `bt-kernel/`.
   Smaller, can land late.
8. **Wave 8 — Misc / tail.** Touchpanel chips, secure modules,
   stragglers.

But: only land what's in K3 from Track B. If Track B says DFR is
mostly K1 (KMI-clean prebuilts), skip wave 3 for MVB and revisit in
the stretch-goal phase.

### 5.2 Per-wave loop

For each wave:

1. List in-scope modules (from K3 ∩ subsystem)
2. Read BUILD.bazel for each, apply recipe
3. Build via `mka kernel`, validate each via Phase 2 tooling
4. **Wave gate**: run `wave_gate.py`. Pass = wave done.
5. Write `~/android/wave_<N>_status.md` — paragraph on what landed,
   what was harder than expected, validation results, plan
   adjustments for next wave.
6. Commit the wave's wire-up changes to the `sm8850-modules` jm2
   fork. Push.

### 5.3 Checkpointing

After each wave, the build must remain green against **both**:

- Source-built kernel + (Bucket A + B + waves 1..N source-built + the
  *measured* K1/K2 prebuilts as KMI-sanctioned)
- OEM kernel + full prebuilt module set (the Option-3 fallback)

If a wave breaks the OEM-kernel fallback, that's a regression that
must be fixed before the wave is marked complete. The fallback is
how we recover if a wave introduces an unexpected blocker.

### 5.4 Deliverables of Phase 5

- N waves of jm2 commits on `sm8850-modules` and (where in-tree
  drivers needed enabling) `sm8850`
- `wave_<N>_status.md` per wave
- An MVB ROM that passes Phase 2 validators end-to-end
- A "release-candidate" tag on each jm2 fork

**Estimate (preliminary, refined after Track B):** 1–2 weeks if
priors hold, 3–6 weeks if K3 is larger than expected.

---

## 9. Phase 6 — Hardware flash test (MVB)

**Goal:** flash and boot the MVB on physical hardware. Validate
basic functionality.

### 6.1 Pre-flash audit

Re-run the audit-style checks from `blockers.md` §1 against the MVB
ROM. Now they should all pass:

- KMI-strict source kernel
- Module CRCs all match (Phase 2 validators all green)
- VINTF target-level=202504 ✓ (carries over)
- Source-built dtb.img / dtbo.img ✓ (carries over)
- All HAL service binaries present ✓ (carries over)

### 6.2 Update flash docs

`flash_guide.md` and `flash_safety_audit.md` rewrite — by this point
the docs from April 26 should be replaced wholesale with MVB-correct
content. Key updates:

- Filename
- Source-built kernel (no longer "OxygenOS prebuilt")
- KMI-strict + GKI-sanctioned-prebuilt-residual story
- Module count breakdown (source-built : KMI-prebuilt : non-KMI
  source-built : truly proprietary)
- Bluetooth HAL binary status (re-check; may resolve when wired
  modules unblock the install path)
- Method B partition list (add `dtb`, `vbmeta_vendor`)
- OTA payload firmware-partitions caveat for Method A (sideload)

### 6.3 Flash & boot

- Method B (fastboot flash) per Opus Web's recommendation; sideload
  path remains valid but explicitly calls out firmware-partition
  reflash to OTA 0280 stock.
- Cold boot. Capture full dmesg + logcat from first boot.
- Functional spot-checks: launcher, display, touch, WiFi, cellular,
  audio, camera, fingerprint, NFC, GPS, charging, vibration, USB.
- Diff `dmesg` against expected. Modules that fail to load will be
  visible here; each must be triaged into "expected residual",
  "needs Phase 7+ source-build", or "regression — block release."

### 6.4 Deliverables of Phase 6

- Working device booted on the MVB ROM ✅ (or written-up failure
  mode if not)
- Updated `flash_guide.md` + `flash_safety_audit.md`
- `~/android/mvb_boot_report.md` — what worked, what didn't, what
  the dmesg/logcat looked like, gap list for Phase 7+

**Estimate:** 2–3 days (most of it is patient post-boot triage).

---

## 10. Phase 7+ — Full Bucket C source-build (stretch goal)

**Goal (per user's directive):** independent of KMI cleanliness,
source-build every module in `vendor/oplus/kernel/` and the
`vendor/qcom/opensource/` kernel-module subsystems. Replace
KMI-sanctioned prebuilts with our own source builds for full
self-sufficiency.

### 7.1 Why pursue this even after MVB ships

- Removes dependency on OnePlus blob refreshes for security/CVE
  patching of those modules. We can patch and rebuild in days, not
  wait for next OOS OTA.
- Matches the LineageOS philosophy of source-built ROMs.
- Reduces uncertainty around future Android 17 / kernel 6.13+
  upgrades — when ABI shifts, our source build adapts; vendor
  prebuilts become stale.

### 7.2 Sequencing

Run additional waves following the same recipe + validation pattern
from Phase 5. Order by:

1. K2 (borderline) modules first — these are most at-risk in the
   prebuilt path because their CRCs are sensitive to kernel
   internals.
2. K1 (clean) modules in the largest subsystems (WLAN, Adreno,
   video, audio) — most strategic.
3. K1 modules in smaller subsystems — lowest priority, can be done
   ad-hoc.

This stretches over months. Each wave produces a release-tagged jm2
fork commit.

### 7.3 Deliverables of Phase 7+

- jm2 fork commits per wave, same recipe + validation gates
- Per-wave status doc
- Final state: ~530+ source-built modules, ~10–25 prebuilt residual
  (true Bucket D — vendor codec/sensor IPs without source)

### 7.4 Estimate

Months. Open-ended, prioritize against other work. The MVB delivered
in Phase 6 unblocks day-to-day use of the device; Phase 7+ is the
finish line.

---

## 11. Phase 8 — Bucket D residual handling

After Phase 7+ closes, the irreducible residual is some small set
(estimated 10–25 modules) of truly-proprietary modules with no
source in any tree.

For each:

- Run Track-B-style classification. If KMI-clean → keep as
  GKI-sanctioned prebuilt. If non-KMI → either accept loss of
  feature, FORCE_LOAD with documented per-symbol audit, or escalate
  to "request OEM source release" / accept-the-feature-as-removed.
- Document each in a `bucket_d_residual.md` audit file with: module
  name, function, source-availability search trail, KMI status,
  decision, rationale.

This is days of work, mostly write-up; the actual decisions are
forced by the prior phases.

---

## 12. Forbidden patterns (from Opus Web, ratified)

These are **non-negotiable** through all phases:

- ❌ **Do not disable `CONFIG_MODVERSIONS`.** It's how we know
  modules will load. Suppressing the check destroys the information
  the rest of the plan depends on.
- ❌ **Do not enable `CONFIG_MODULE_FORCE_LOAD` as a coping
  mechanism during wire-up.** Reserved exclusively for Phase 8
  Bucket-D residual decisions.
- ❌ **Do not `#ifdef`-stub Kconfig symbols** to make builds pass.
  Add the Kconfig entry and enable in defconfig.
- ❌ **Do not skip modules** to declare a wave done. Hard gate via
  `wave_gate.py`. "80% done" isn't a thing.
- ❌ **Do not estimate from "I see source files exist."** First
  module of each wave must build green and pass validators before
  scoping the rest.
- ❌ **Do not chase tangents.** Out-of-scope improvements
  (upstreaming fixes, refactoring OnePlus build infrastructure,
  cleaning up Lineage's kernel patches beyond what the wave
  requires) → deferred backlog file. Revisit after Phase 7+.
- ❌ **Do not break the Option-3 fallback.** Each commit must keep
  the OEM-kernel-prebuilt path green so we can always retreat to a
  flashable state.

The one allowed scope expansion: **adding missing `EXPORT_SYMBOL`s**
to the kernel for modules to link. These are cheap, often
necessary, and sometimes warrant upstream submission. Accumulate a
list in `kernel_export_additions.md` for later upstream review.

---

## 13. Checkpointing & status discipline

- Every commit on a jm2 fork during Phases 1, 5, 7+ keeps the build
  green against both the source-kernel and the OEM-kernel paths.
- Per-wave: `~/android/wave_<N>_status.md` written before the wave
  is marked complete. Captures what landed, what was harder than
  expected, validation results, what's deferred to next wave.
- Per-phase: short status update appended to this implementation
  plan as the work progresses. Don't update the plan body — append
  a "Phase N completed YYYY-MM-DD" section at the end. Easier to
  diff later.
- Surface assumptions in writing at every wave boundary. The
  Bucket D 236→25 reclassification happened because external
  review prompted recheck; the agent should be doing that recheck
  preemptively.

---

## 14. Decision points

Two explicit decision points where the plan branches:

### After Phase 0

- **GO**: KMI baseline clean. Proceed to Phase 1.
- **NO-GO**: KMI baseline shows breaks from jm2 patches. Decide:
  rework patches, request stablelist additions (slow), or fall back
  to bulk-wire-up (no Track A; everything in Bucket C must be
  source-built; timeline grows to original 4–8 weeks for MVB).

### After Phase 3

- **Priors hold** (60–70% K1 / 20–30% K2 / 10–15% K3): Phase 5 MVB
  wire-up is 1–2 weeks. Plan as written.
- **K3 < expected** (e.g., < 50 modules): MVB is a short Phase 5,
  Phase 6 hardware test happens within ~2 weeks of today. Phase 7+
  is the bulk of remaining work.
- **K3 > expected** (e.g., > 200 modules): Phase 5 grows to 4–6
  weeks. MVB is delayed. Phase 7+ stretch goal becomes mostly
  redundant (most of Bucket C already source-built for MVB).

The plan is robust to all three outcomes; only the timeline shifts.

---

## 15. Today's flash-zip disposition

Per user directive: today's `lineage-23.2-20260501-UNOFFICIAL-infiniti.zip`
**will not be flashed**. It's preserved as a milestone artifact
proving source kernel + dtb/dtbo + VINTF + 7 jm2 forks work
end-to-end via `mka kernel`. Reference value only.

Implication: no need to update `flash_guide.md` /
`flash_safety_audit.md` against the May 1 build. Those docs get a
single rewrite in Phase 6 against the MVB. Saves ~half a day of
intermediate doc churn.

---

## 16. Estimated total timeline (rough, refines after Phase 3)

| Phase | Days | Cumulative |
|-------|-----:|-----------:|
| 0 — KMI baseline verification | 1–5 | 1–5 |
| 1 — Track A canonicalization | 2–4 | 3–9 |
| 2 — Validation infrastructure (parallel with 1) | 1 | 3–9 |
| 3 — Track B classification | 1 | 4–10 |
| 4 — Recipe + proof-point module | 2 | 6–12 |
| 5 — MVB wire-up (K3 subset) | 5–14 | 11–26 |
| 6 — Hardware flash test | 2–3 | 13–29 |
| **MVB shipped** | | **2–4 weeks** |
| 7+ — Full Bucket C stretch goal | weeks–months | open-ended |
| 8 — Bucket D residual handling | days | small tail |

MVB delivery target: **end of May 2026** if priors hold and KMI
baseline is clean on first check. 4-week window with reasonable
buffer for the Phase 0 / Phase 3 surprises.

---

## 17. Open questions for the user before kicking off

1. Confirm the user wants Phase 7+ (full source-build of all Bucket
   C, even KMI-clean modules) as the stretch goal — current plan
   reflects this directive.
2. Hardware availability for Phase 6 boot test: when can the device
   be put in fastboot mode for the MVB flash? Affects when Phase 5
   needs to land.
3. Tolerance for Phase 0 NO-GO: if jm2 patches break KMI and rework
   is needed, are we OK with patch reworks that might require
   moving in-tree code to out-of-tree modules? Or is "fall back to
   bulk wire-up" the preferred fallback?
4. Allocation of work to subagents: which phases should be human-
   driven, which are mechanical enough to delegate to subagents
   (Phase 2 tooling? Phase 4 recipe authoring? Wave loops in
   Phase 5)? Plan currently leaves this open; the agent will
   propose subagent splits when each phase begins.

---

*End of plan. Updates appended below as work progresses.*
