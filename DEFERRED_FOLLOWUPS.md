# Deferred follow-ups

Tracker for work items that surface during Phase 5+ wire-up but are
out-of-scope for the current wave. Per `IMPLEMENTATION_PLAN.md` §12,
"anything that isn't strictly necessary to get the 360 modules
building with matching CRCs goes into a deferred backlog. Land
Bucket C, validate against hardware with the source-built kernel,
*then* decide whether the deferred items are worth pursuing."

Format: each entry has trigger context + concrete tasks + rationale
for deferring. Items move out of this file when they're either
landed (commit hash) or explicitly accepted as won't-do.

---

## Wire `BOARD_PREBUILT_KERNEL=true` build switch

**Surfaced:** 2026-05-02 (Wave 1 close-out review).

**Context:**
`IMPLEMENTATION_PLAN.md` §5.3 says each wave must keep both build
paths green:
1. Source-built kernel + waves 1..N source-built modules
2. OEM kernel + full prebuilt module set (the Option-3 fallback)

We don't have a one-line switch to toggle path 2. Verifying it would
currently require manual boot.img surgery (replace source kernel
`Image` with OEM `Image`, re-pack, re-flash). What we DO verify is
that the OEM prebuilt corpus at `device/oneplus/infiniti-kernel/` is
untouched and that `BOARD_VENDOR_KERNEL_MODULES` wildcard still
references it, so the fallback is *structurally* intact even if not
exercised end-to-end per wave.

**Concrete tasks:**

1. Add `TARGET_PREBUILT_KERNEL := $(LOCAL_PATH)/../infiniti-kernel/Image`
   guarded by a build flag in
   `device/oneplus/sm8850-common/BoardConfigCommon.mk`:

   ```makefile
   ifeq ($(BOARD_PREBUILT_KERNEL),true)
   TARGET_PREBUILT_KERNEL := $(LOCAL_PATH)/../infiniti-kernel/Image
   # disable kernel-source build path
   TARGET_KERNEL_EXT_MODULES :=
   else
   # ... existing source-build wiring
   endif
   ```

2. Confirm the OEM kernel binary exists at the assumed path
   (`device/oneplus/infiniti-kernel/Image`). If only `boot.img` is
   shipped, add a build-time unpack step to extract Image from it.

3. Add a wrapper `~/android/iter_brunch_fallback.sh` that runs
   `brunch` with `BOARD_PREBUILT_KERNEL=true`.

4. Update `wave_<N>_status.md` template to require BOTH builds green
   before marking a wave complete.

5. Optionally: add a CI-like `tools/jm2/verify_both_paths.sh` that
   runs both builds and asserts both produce flashable
   `lineage-...zip` files.

**Effort estimate:** 1–2 days. The `TARGET_PREBUILT_KERNEL` plumbing
in LineageOS device builds is well-documented; the harder part is
ensuring the resulting boot.img has correct GKI ABI metadata + that
the prebuilt module set's vermagic still matches.

**Rationale for deferring:** The structural fallback path (OEM
prebuilts in `BOARD_VENDOR_KERNEL_MODULES` wildcard) is intact and
the source-built path is what matters for MVB. The "both paths
green" requirement is a defensive posture that's most valuable when
we approach hardware test time and want a cheap retreat. Doing the
plumbing now would slow Phase 5 wire-up without immediate payoff.

**When to revisit:** Right before Phase 6 hardware test, OR if a
Phase 5 wave introduces a regression that we suspect breaks the
fallback (then the switch is the diagnostic tool that confirms).

---

## HDMI audio codec wire-up (audio-kernel needs msm_ext_display include path)

**Surfaced:** 2026-05-02 (sub-wave 2C v1 build).

**Context:**
audio-kernel's `asoc/codecs/msm_hdmi_codec_rx.c` `#include
<msm_ext_display.h>` — header lives in the mm-drivers/msm_ext_display
external module's include dir. audio-kernel's Kbuild doesn't currently
wire that include path. v1 of sub-wave 2C deferred by commenting out
`CONFIG_SND_SOC_MSM_HDMI_CODEC_RX=m` in both `canoeauto.conf` and
`canoeautoconf.h`. Audio cluster builds cleanly without it.

**Concrete tasks:**
1. Add `EXTRA_CFLAGS += -I$(KBUILD_EXTMOD)/../../mm-drivers/msm_ext_display/include`
   (or equivalent path resolution) to audio-kernel/asoc/codecs/Kbuild
   under the canoe gate
2. Verify msm_ext_display is built BEFORE audio-kernel in
   TARGET_KERNEL_EXT_MODULES ordering (it is — listed before
   audio-kernel in current order)
3. Re-enable CONFIG_SND_SOC_MSM_HDMI_CODEC_RX in both canoeauto.conf
   and canoeautoconf.h
4. Build, validate `hdmi_dlkm.ko` lands

**Rationale for deferring:** HDMI audio is a tail feature. Most
canoe devices use built-in speakers + headphone jack via lpass-cdc,
not HDMI output. The 30+ other audio modules in the cluster are
unblocked by the deferral. Closing this gap is wire-up, not
infrastructure.

**When to revisit:** When something downstream depends on HDMI
audio (display driver requesting audio path? user feedback about
HDMI sound?), OR when sub-wave 2D-2I has a similar
include-path-from-other-external pattern that benefits from the
same fix landing once.

---

## Make Phase 3 classifier handle hyphen/underscore normalization

**Surfaced:** 2026-05-02 (Wave 1 prep — the "76 unmapped" triage
found the Phase 3 classifier didn't normalize `-`↔`_` between
modules.load names and the canonical-CSV `MODULE_NAME` field, leading
to 66 false-positive "unmapped" entries that were actually mapped).

**Concrete task:**
Update `tools/jm2/kmod_validate.py` (or a new helper) to canonicalize
module names by `.replace("-", "_")` when joining modules.load
entries against built-module CSVs. Re-run baseline classification.

**Rationale for deferring:** The triage already produced the
correct 217-modules-needing-wire-up scope number. The classifier
inconsistency is cosmetic for the rest of Phase 5 — we have the
right list. Worth fixing for accuracy of any future re-runs but
not blocking.

**When to revisit:** Anytime kmod_validate.py is touched, or before
generating any future baseline CSV.

---

## ~~Cuttlefish / QEMU runtime-validation gate~~

**RESOLVED 2026-05-02: WON'T-DO (superseded by static-check pair).**

The static-check substitutes — `dt_consistency_check.py` (landed
`e79fb87` + glob fix `4b0ff4c`) and `exports_superset_check.py`
(landed `0eb0b0f`) — together cover the two highest-value classes of
latent runtime bug at static-analysis cost:

1. DT-consumer-references-non-loadable-producer (caught in 2A.5: 5
   missed canoe clock controllers, an MVB-blocker)
2. Source-built .ko missing OEM-prebuilt's EXPORT_SYMBOLs (would have
   caught 2C v2's OPLUS_ARCH_EXTENDS depmod failure pre-flash)

Empirical evidence after 4 sub-waves (2A, 2A.5, 2B, 2C): every latent
runtime bug we've encountered fits one of these two classes. Brunch
closeout (depmod, vermagic match, CRC match) catches the rest. No
sub-wave has produced a bug requiring ARM64 emulation to detect.

The cost-benefit math has flipped: cuttlefish/QEMU setup is hours of
investment + minutes per sub-wave to operate; the two static checkers
each took <1 day to build and run in seconds. The static gate is
strictly cheaper AND has caught real bugs the runtime gate would have
caught later anyway.

**Reopen triggers (raise bar — static gate has earned trust):**
- Phase 6 hardware test surfaces ≥3 latent runtime bugs that fit
  NEITHER static-check class (i.e., truly novel runtime-only failure
  modes)
- A wave's brunch-closeout produces a structurally-valid ROM that
  fails to boot in a way that costs more than 1 day to root-cause AND
  a third static-check tool can't be built to catch the bug class

**Surfaced:** 2026-05-02 (Opus Web post-2A review).

**Context:**
The static validation gates we run pre-flash (vermagic match, CRC
match, OF compatible match) catch a meaningful class of bugs but
defer ALL runtime behaviors to Phase 6 hardware test:

- Probe-time errors (regulator-not-found, GPIO-not-available)
- Init ordering / DT compatible-match races
- Parent-clock-not-found warnings on consumers we didn't grep for
- IOMMU mapping mismatches on DMA-buffer-using modules
- Suspend/resume code paths

With Wave 2's ~213 modules + subsequent waves, latent runtime bugs
that pass static validation will accumulate. Phase 6 hardware test
will then be a multi-day debugging mode-shift (build → flash →
boot → dmesg → debug, hours per cycle) vs the current pre-flash
pace (minutes per cycle).

**The decision (not yet made):**

A. **Stand up cuttlefish / QEMU runtime validation NOW.** A few
hours of one-time setup (kernel-build flag tweaks, GKI image
extraction, smoke-test scripting) + minutes per sub-wave to run
the smoke test. Catches ~50–80% of latent runtime bugs while
feedback loops are still tight.

B. **Defer all runtime validation to Phase 6.** Accept that Phase 6
will spend N days debugging accumulated latents. Faster Wave 2
landing rate today; slower hardware bring-up later.

The right choice depends on:
- Whether cuttlefish/QEMU is feasible for sm8850 (canoe vendor DT
  may have hardware-specific bindings that don't have QEMU
  equivalents — needs investigation)
- User's tolerance for Phase 6 surprise vs Wave 2 friction
- Whether Wave 2 modules touch DMA / IOMMU / suspend paths that
  static analysis can't catch

**Concrete tasks for path A (if chosen):**
1. Investigate sm8850 cuttlefish / QEMU support (probably leans
   on Google's `aosp_cf_arm64_phone` cuttlefish image with a
   custom kernel slot)
2. Build smoke-test script that runs mka kernel + boot in
   cuttlefish + greps dmesg for ERR/WARN classes (parent clock
   not found, probe deferred, regulator not found, etc.)
3. Add as Step 9 in WIRE_UP_RECIPE.md (post-build, pre-commit)
4. Run after each sub-wave landing

**When to revisit:** Before sub-wave 2C accumulates non-trivial
landings. The audio cluster will be the first place latent runtime
bugs are likely to manifest (probe-time clock-tree references,
DAI registration timing, ASoC machine-driver matching).

---

## EXPORT_SYMBOL upstream submission cadence

**Surfaced:** 2026-05-02 (EXPORT_SYMBOL_HANDLING.md authoring).

**Context:**
Phase 5+ will generate kernel-side EXPORT_SYMBOL additions
(estimated 50–150 over the full wire-up). The handling doc says
"Batch upstream submissions every 4–6 wave landings" but currently
no upstream submission process is set up — no contact with AOSP /
Qualcomm CAF / OnePlus OSS maintainers, no submission template, no
review cadence.

**Concrete tasks:**

1. Identify upstream maintainer contacts for the relevant trees
   (AOSP Common Kernel, Qualcomm CAF, OnePlus OSS).
2. Draft a submission template (cover letter, per-symbol commit body
   format).
3. After ~4 waves of EXPORT additions accumulate, do a first batch
   submission as a test of the pipeline.
4. Track upstream-status in `kernel_export_additions.md` (file
   referenced by EXPORT_SYMBOL_HANDLING.md but not yet created;
   creates itself organically when the first wave needs an export).

**Rationale for deferring:** Phase 5 wire-up generates the export
backlog that motivates the submission pipeline. Setting up the
pipeline before we have anything to submit is premature. Wave 1
landed with zero EXPORT additions; the file isn't needed yet.

**When to revisit:** Either when the first wave generates a
non-trivial EXPORT addition (creates `kernel_export_additions.md`
organically), OR after 4 waves accumulate (whichever comes first).

**Update 2026-05-04 (post-2F.1):** 7 consecutive sub-waves at 0
EXPORTs (Phase 4 keyevent_handler + 2A + 2A.5 + 2C + 2H + 2D +
2F.1). Cumulative Wave 2 EXPORT count: **0**. The 50–150 estimate
in EXPORT_SYMBOL_HANDLING.md was wrong by orders of magnitude.

**Retirement criteria (refined):** Retire this entry after Wave 2
closes AND cumulative EXPORT count is ≤ 2. Threshold is
cumulative across Wave 2, not per-sub-wave. Anything more than 2
warrants a small upstream patch series even if the modal sub-wave
is zero. Currently 2 EXPORTs of buffer remaining across 2F.2 +
2F.3 + any late surprises before retention is triggered.

---

## Display-cluster export gaps surfaced by exports_superset_check (2026-05-02)

**Surfaced:** 2026-05-02 by exports_superset_check.py smoke run on
the latest source-built corpus. Both modules pre-date Wave 2 (built
during Phase B of the original bring-up). Latent since whenever the
display cluster was first source-built; would have manifested at
Phase 6 hardware test as "display works in some configs and not
others" or "display drivers probe but rendering paths fail."

**Diagnosis (each ≤30 min, characterization done):**

### msm_drm: 321 missing exports

- 80/401 source-built/OEM. 296 of 321 missing are `iris_*` symbols
  (Pixelworks Iris7P display visual-processor extensions).
- Source files present at
  `vendor/qcom/opensource/display-drivers/msm/iris/{core,vendor}/{common,iris7p}/*.c`
  (40+ files).
- OEM `targets/canoe.bzl` (lines 46–49) enables `CONFIG_PXLW_IRIS`
  + `CONFIG_PXLW_IRIS7P`. Bazel-flow honors these and pulls in the
  iris .o files (gated in `display_modules.bzl` line 194+).
- Our Kbuild path uses `config/gki_canoedispconf.h` which does NOT
  define `CONFIG_PXLW_IRIS` or `CONFIG_PXLW_IRIS7P`. Result:
  `msm/Kbuild` lines 102 + 349 (`ifeq (${CONFIG_PXLW_IRIS},y)`)
  short-circuit; iris source isn't compiled into msm_drm.ko.
- Class: **config-gating misalignment** (Bazel→Kbuild translation
  incompleteness from Phase B). Same family as 2C; different
  specific knob. NOT OPLUS_ARCH_EXTENDS-class.
- Note: gates are `=y` (built-in) not `=m` (separate module). Iris
  is statically linked into msm_drm.ko in the OEM build.

### msm_hw_fence: 5 missing exports

- 17/22 source-built/OEM. 5 missing are all `synx_hwfence_*`
  (synx-fence interop layer between hw_fence and synx subsystems).
- Source files present at
  `vendor/qcom/opensource/mm-drivers/hw_fence/src/hw_fence_drv_interop.c`
  and `src/msm_hw_fence_synx_translation.c`.
- Current `vendor/qcom/opensource/mm-drivers/hw_fence/Kbuild`
  defines `msm_hw_fence-y :=` over a fixed list of 5 .o files;
  the two synx-related .c files are NOT in the list.
- Class: **Kbuild obj-list incompleteness** (subset of config-gating
  family). Same root cause: Phase B Bazel→Kbuild translation
  missed the synx-translation cluster of source files.

**Concrete tasks (Phase H+1 patch series, before Wave 2 closes):**

1. **msm_drm**:
   - Add `export CONFIG_PXLW_IRIS=y` and `export
     CONFIG_PXLW_IRIS7P=y` to `config/gki_canoedisp.conf`.
   - Add `#define CONFIG_PXLW_IRIS 1` and `#define CONFIG_PXLW_IRIS7P 1`
     to `config/gki_canoedispconf.h`.
   - Verify EXTRA_CFLAGS / include paths are wired so iris source
     can find `msm/iris/core/include/`, `msm/iris/vendor/`,
     `msm/iris/core/{common,iris7p}/`. Mirror the Bazel
     `iris_core_headers` / `iris_vendor_headers` cc_library
     include paths into `msm/Kbuild` PWATOP setup if needed.
   - Verify iris source has no `#ifdef OPLUS_ARCH_EXTENDS` gates;
     if it does, lift `OPLUS_ARCH_EXTENDS` define into the disp
     autoconf header (analogous to canoeautoconf.h fix in 2C v3).
   - Re-run exports_superset_check; expect msm_drm verdict
     `pass-exact` or `pass-additive`.
   - Effort: half-day (likely; full day if include-path or
     ARCH_EXTENDS wrinkle).

2. **msm_hw_fence**:
   - Add `src/hw_fence_drv_interop.o` and
     `src/msm_hw_fence_synx_translation.o` to `msm_hw_fence-y` in
     `vendor/qcom/opensource/mm-drivers/hw_fence/Kbuild`.
   - Verify `-I$(MSM_HW_FENCE_ROOT)../synx-kernel/...` include
     paths (already wired in Kbuild) suffice for the new files.
   - Re-run exports_superset_check; expect `pass-exact`.
   - Effort: 30–60 min.

**Rationale for deferring (not blocking Wave 2 close):** Both gaps
are pre-existing (Phase B latent); no Wave 2 sub-wave depends on
them. Folding into a Phase H+1 patch series after 2H/2D/2F
finish keeps Wave 2 momentum + lets the agent batch the OPLUS_ARCH_EXTENDS
audit step across all three modules at once.

**When to revisit:** As soon as 2H/2D/2F land, before Wave 2
release-candidate tag, before Phase 6 hardware test. Hard
prerequisite for Phase 6 — display latent bugs in hardware test
context cost an order of magnitude more to root-cause than fixing
the build now.

---

## Symbol-signature mismatch checker (next-most-likely pre-flash gap)

**Surfaced:** 2026-05-02 by Opus Web review post-exports_superset_check.

**Context:**
The static-check pair (dt_consistency_check + exports_superset_check)
catches structural mismatches: missing producers, missing exports.
Neither catches **signature** mismatch: source-built module exports
`int foo(struct bar *)` while OEM expects `int foo(struct baz *)`.
Both depmod and superset-check pass; consumer crashes at runtime
when it dereferences the wrong struct.

The kernel's CRC __versions section is supposed to catch this at
modprobe time, but only if both producer and consumer were compiled
against the same header — for OEM-prebuilt-consumer + source-built-
producer, the OEM's __versions CRCs and our genksyms-generated CRCs
are computed against different header contents and may diverge even
when the actual ABI is compatible (or, worse, may agree when it
isn't, given hash collisions or whitelist trim).

**Concrete tasks (if/when this bug class trips):**
1. Build `tools/jm2/symbol_signature_check.py` peer to
   exports_superset_check. For each shared export between source-built
   and OEM .ko, extract the corresponding `__crc_<name>` value (kernel
   genksyms CRC) and compare. Flag any divergence as a
   `signature-divergence` verdict.
2. Output: CSV with module / symbol / src_crc / oem_crc / verdict.
3. Initially advisory (warn-only): we don't yet know how often
   benign CRC divergence happens for ABI-compatible signatures.

**Rationale for deferring proactively:**
Cost of being wrong about WHICH bug class bites next is real. The
two static checkers we built were both built reactively after a
specific bug surfaced — and each landed in <1 day with high
confidence in correctness. Building a signature-mismatch tool
proactively means investing time in a tool we may never need, OR
that has a high false-positive rate that requires a second
calibration pass. Better to wait until the bug class actually trips.

**Reopen trigger:** First sub-wave where a source-built module has
all expected exports (passes exports_superset_check) and clean
depmod (passes vermagic + CRC) but a runtime issue surfaces that
roots to ABI signature divergence between source-built and OEM
builds. Most likely subsystems: subsystems with structural-header
divergence between OEM patches and AOSP-aligned headers (DRM, KGSL,
camera).

---

## dt_consistency_check.py: extend to flag compatibles with no DT node

**Surfaced:** 2026-05-03 during 2H prep correction cycle.

**Context:** Prep section originally claimed 2 of 4 oplus_network
modules' compatibles weren't in canoe DT. Wider grep (including
`kernel_platform/qcom/opensource/devicetree/oplus/`) found them in
`infiniti_overlay_common.dtsi`. The original narrower grep would
have produced a false-negative "won't probe" report if the user
hadn't pushed back. The right fix isn't more careful manual greps;
it's mechanizing the check.

**Tool gap:** Current `dt_consistency_check.py` validates phandle-
reachability — does a phandle in a loaded module's source point at
a producer that's also loadable? It does NOT check the inverse: if
a driver declares a `compatible = "X"`, is there at least one DT
node with `compatible = "X"` somewhere in the as-shipped DT?

**Concrete tasks:**

1. Add `--check-compat-orphans` mode to dt_consistency_check.py
   (or peer tool `dt_compat_orphan_check.py` — judgment call when
   we get there).
2. Inputs: source-tree root (for `of_match_table` extraction via
   regex on `.compatible = "..."`), DT roots (canoe-kernel-dts/ +
   `kernel_platform/qcom/opensource/devicetree/oplus/` + any future
   overlay dirs).
3. Output: CSV listing each driver's compatibles, whether each
   resolved to ≥1 DT node, and verdict (`pass-bound` / `orphan` /
   `bound-via-overlay-X`).
4. Useful for surfacing genuinely dead modules (modules.load
   contains them, but nothing in DT binds, and no userspace trigger
   maps either).

**When to build:** After 2D, alongside the symbol-signature checker
decision (currently both deferred until concrete bug instances
surface — 2H gave us only a false-negative-near-miss, not a real
bug to specify against).

---

## noop_modules.md tracking across Wave 2

**Surfaced:** 2026-05-03 (2H prep, rf_cable_monitor finding).

**Context:** `oplus_network_rf_cable_monitor.ko` is a 30 KB module
in OEM `modules.load` whose only behavior is `op_rf_cable_init()
{return 0;}` and an empty exit. No platform_driver, no probe, no
sysfs hooks. The OEM ships it for build-graph completeness; it does
nothing on the device.

**Implication:** "In modules.load" is not a reliable proxy for
"functionally required." Some Wave 2 modules may be similarly
empty, which means our wire-up effort scales sublinearly with
apparent surface area for those modules.

**Two sub-classes to distinguish:**

- **obvious-stub**: init/exit return 0, no platform_driver, no
  sysfs/proc/file_operations registration. Detectable from a
  static read of the .c file. rf_cable_monitor exemplar.
- **runtime-effective-no-op**: real platform_driver registration,
  real probe(), but activation gate
  (`#ifdef CONFIG_OPLUS_FEATURE_FOO_FOR_BENGAL_ONLY`, project-id
  check, region-string check) short-circuits on canoe. Module
  loads, probe runs, then does nothing. Static source review will
  call this class "real module"; only runtime observation or
  careful gate-grep will distinguish it. The more interesting
  class — wire-up effort is real, downstream contribution is zero.

**Concrete tasks:**

1. Maintain `noop_modules.md` with two columns: `obvious-stub` and
   `runtime-effective-no-op` (if observed). Track count + names.
2. After Wave 2 closes, file a downstream-optimization task for
   `vendor_dlkm` slimming if combined count > 10.
3. obvious-stub detection is statically tractable: parse `.c` for
   `module_init/exit` macros, follow into the functions, look for
   absence of `__platform_driver_register`, `proc_create`,
   `device_create_file`, `sysfs_create_file`, `class_create`,
   `cdev_init`, etc.
4. runtime-effective-no-op detection: grep init/probe paths for
   project-id checks (`get_project()`, `oplus_get_project()`),
   region-string compares, or `#ifdef CONFIG_OPLUS_FEATURE_*`
   gates that aren't enabled in canoeauto.conf. By 2D the agent
   should expect to see this class and call it out by name.

**When to build:** Tracking starts now (manual entries in
`noop_modules.md`). Tool only if count grows enough to make manual
inspection expensive. obvious-stub tool is straightforward;
runtime-effective-no-op tool needs gate-evaluation logic that
overlaps with the dt_consistency_check compat-orphan extension.

---

## vendor_dlkm slimming via runtime-effective-no-op removal

**Surfaced:** 2026-05-03 (sub-wave 2D closeout — first bulk
population of noop_modules.md).

**Context:** Wave 2 has crossed 17 noop entries already (1
obvious-stub + 16 runtime-effective-no-op). The 16 runtime-
effective-no-op entries are all per-chip touch leaves whose
`compatible` strings don't match canoe DT — driver registers
platform_driver, never probes. Per-leaf .ko sizes range
200-600 KB; 16 entries × ~200 KB average = ~3 MB of vendor_dlkm
that ships but does nothing on canoe.

OEM keeps these in modules.load because the same source tree
ships across many OnePlus devices — different panels per
device — and the modules.load is shared. We don't have that
constraint; we only flash to canoe.

**Concrete tasks:**

1. After Wave 2 closes, audit final noop_modules.md count.
2. For each runtime-effective-no-op entry, decide: remove from
   modules.load (and from TARGET_KERNEL_EXT_MODULES if no
   in-tree consumer needs the symvers)? Keep "ships but doesn't
   load" (still in updates/ but not in modules.load)?
3. If removing entirely: filter the per-chip leaves whose
   compatibles don't match canoe DT out of TARGET_KERNEL_EXT_MODULES,
   leaving only the ones that bind on canoe (oplus_hbp_core,
   oplus_bsp_tp_hbp_syna_s3910, plus their build-time deps).
4. Re-run brunch closeout and verify vendor_dlkm size delta.

**When to act:** After Wave 2 closes (post-2F/2E/2G/2I). Don't
attempt during active sub-wave wire-up — the goal of Wave 2 is
parity with OEM's loaded set first; optimization is downstream.

**Rough savings projection:** ~3 MB of vendor_dlkm. Not large
in absolute terms but a clean, low-risk win once the pattern is
documented.

---

## exports_superset_check.py: support multiple --source-built-glob args

**Surfaced:** 2026-05-04 during 2F.2 verification.

**Context:** Passing multiple `--source-built-glob` flags to the tool
causes argparse to retain only the LAST one. Subsequent multi-module
verifications had to fall back to a per-module shell loop.

**Concrete tasks:**

1. Change argparse setup from default `store` action to
   `action='append'` so repeated `--source-built-glob` flags
   accumulate.
2. Update the glob expansion to iterate over every accumulated glob.
3. Optionally accept multiple positional arguments instead.

**When to act:** Cosmetic; not blocking any sub-wave. Cleanup pass
after Wave 2 closes.

---

## WIRE_UP_RECIPE Step 7.x structural cleanup pass at Wave 2 closeout

**Surfaced:** 2026-05-06 (post-2E batch 1, Opus Web institutional review).

**Context:** Wave 2 has accreted named diagnostic steps in the Step 7.x
range as new failure-mode classes have surfaced:

- 7.5: nm undefined-refs check (2D oplus_hbp_core)
- 7.6: Make/C asymmetry silent-skip (2F.1 audio + 2F.3 charger)
- 7.7: OEM-source `-Werror=unterminated-string-initialization` class (2F.2 + 2F.3)
- 7.8: OEM-Bazel-environment-coupled signature (2F.3)
- 7.8a: OEM-build-system-coupled meta-table (2E prep)
- 7.8b: OEM-techpack-overlay-coupled + modinfo-match check (2E batch 1)
- 7.8c: Name-collision false-positive (2E batch 1)
- 7.9: Iteration-count escalation (2F.3 post-mortem)
- 7.10: Cumulative-evidence canonical format (2E batch 1 closeout)

The numbering is getting crowded. The classes don't all share a
clean meta-pattern: 7.5/7.7 are toolchain-specific, 7.8/7.8b/7.8c
are about OEM build-system coupling and its verification pitfalls,
7.6 is a Make/C asymmetry, 7.9 is iteration-budget meta, 7.10 is
documentation hygiene. The 7.8 family is internally coherent but
sits awkwardly alongside 7.9/7.10.

**Concrete tasks (post-Wave-2):**

1. Group the OEM-build-system-coupling family as Step 7.8 with
   sub-letters (already done structurally, but rename so the
   numbering is intentional, not accreted).
2. Promote 7.9/7.10 to Section 8 (or higher) titled "Wave-level
   meta-rules" — distinct from the per-module recipe steps in 7.x.
3. Move 7.5/7.6/7.7 toolchain-specific steps into an "Anti-patterns
   / known toolchain quirks" subsection.
4. Re-number consistently and update internal cross-references.

**Rationale for deferring:** Restructuring during active wave
landings risks breaking cross-references in the prep docs that
agents are reading mid-iteration. Cleanup at Wave 2 closeout
is the right time — pattern is fully exposed, no in-flight
references to invalidate.

**When to revisit:** End of Wave 2 (after 2I, 2E batch 2, 2G).
Pair with the closeout retrospective.

---

## Format

To add new entries:

```
## <One-line title>

**Surfaced:** YYYY-MM-DD (where/when).

**Context:** ...

**Concrete tasks:** ...

**Rationale for deferring:** ...

**When to revisit:** ...
```

When an item moves out (landed or accepted as won't-do), strike it
through with `~~`-markers and prepend a "RESOLVED YYYY-MM-DD: ..."
line. Don't delete — historical record matters.
