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

## ~~Wire `BOARD_PREBUILT_KERNEL=true` build switch~~

**RESOLVED 2026-05-08** (commit `f1e12df` in
`device/oneplus/sm8850-common`). The switch landed in
`BoardConfigCommon.mk` and was verified end-to-end via
`~/android/iter_brunch_fallback.sh` at fallback_v6_clean: boot.img
gets the OEM kernel binary, vendor_dlkm.img has 557 modules all
with OEM vermagic (0 source-built), modules.load 310/310 present.
ROM zip 2.38 GB, structurally equivalent to the proven April 26
build.

Three concrete corrections vs the original recipe surfaced during
implementation, each captured in the commit message:
- Use `$(COMMON_PATH)`, not `$(LOCAL_PATH)` (LOCAL_PATH unset in
  BoardConfig context — failed at v3).
- Must also set `TARGET_FORCE_PREBUILT_KERNEL := true` to flip
  kernel.mk:248's `FULL_KERNEL_BUILD := true` default to false
  (without it, source kernel still builds and replaces OEM Image —
  failed at v2).
- Keep `TARGET_KERNEL_SOURCE` / `TARGET_KERNEL_CONFIG` set so
  kernel.mk:140 can derive `TARGET_KERNEL_VERSION` from
  `$(TARGET_KERNEL_SOURCE)/Makefile` (clearing them broke version
  detection — failed at v1).

Five iterations to clean (v1-v6). Original effort estimate 1-2 days
was high; actual implementation ~2 hours including 4 brunch
iterations, primarily because the three kernel.mk gating layers
weren't documented in one place.

Phase 6 hardware test is now actionable on this fallback path.

---

(Original entry preserved below for historical context.)

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

## `vendor_strip_check.py` — recursive 7.8b cascade detector

**Surfaced:** 2026-05-11 (2E batch 2 pre-flight; named in
WIRE_UP_RECIPE.md Step 7.8e).

**Context:**
The 2E batch 2 prep discovered that the 6 candidate modules' BUILD.bazel
`deps` lists reference modules that ARE in our source tree but are
missing both Kconfig stanzas and Makefile `obj-$()` entries — the
same "techpack-overlay-coupled" pattern as the target module itself,
recursively. The work estimate for "patch one module" becomes
"patch N modules" when the cascade is non-trivial. Discovering this
iteratively at modpost time (one undefined symbol per build cycle)
is slow and confusing. A static pre-flight check would surface the
full cascade graph before tactical wire-up starts.

**Concrete tasks:**

1. Build `tools/jm2/vendor_strip_check.py` peer to
   `dt_consistency_check.py` and `exports_superset_check.py`.
2. Inputs:
   - target module path (read its BUILD.bazel `deps`)
   - kernel tree root (check each dep's source / Kconfig / Makefile presence)
3. Mode `--single`: per-target one-shot — for each dep, emit the
   7.8b signature verdict (source_present, kconfig_present,
   makefile_present, needs_replication).
4. Mode `--transitive`: recursive walk — for each dep that needs
   replication, look up ITS deps too, until reaching modules that
   are fully wired. Output graph + depth per dep.
5. CSV output: `dep_module, source_present, kconfig_present,
   makefile_present, needs_replication, recursion_depth,
   discovered_via`.
6. Integration: surface in WIRE_UP_RECIPE Step 7.8e as the
   pre-flight check that converts cascade discovery from
   "modpost-iteration cost" to "30-second static cost."

**Rationale for deferring:** 2E batch 2's cascade is identified
already (qcom-amoled-regulator → debug-regulator → proxy-consumer,
plus the unconsumed peers stub/qpnp-lcdb/qti-fixed). 2E batch 2 will
patch them manually. The tool's value is for FUTURE sub-waves where
the cascade is unknown ahead of time — most likely 2G msm
graphics/video (larger dep trees per module) and Wave 5 WLAN
(definitely has deep cascades). Building the tool before 2G prep
is the right pre-flight cost.

**When to revisit:** When 2G prep starts. The pre-2G investment
pays back across 2G + Wave 5 + remaining Phase 7+ waves.

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

---

## Pre-flight verification gate for config-fragment work

**Surfaced:** 2026-05-15 (Phase 6 boot-failure investigation; B''
re-validation discovered the original B'' audit measured a kernel that
hadn't actually been rebuilt with production_profile.config applied).

**Context:**
The original Path B'' "ZERO convergence" verdict (2026-05-12) was
authored from kmi_audit output produced against the May-12 vmlinux,
which IKCONFIG extraction proved still had all 12 B'' flags = y. The
fragment was committed to `arch/arm64/configs/production_profile.config`
but never added to `TARGET_KERNEL_CONFIG` in BoardConfigCommon.mk, so
Kbuild's config-merge step never saw the flips, .config content
matched dev-baseline, and Kbuild correctly reused the existing Image
(content-identical). The audit script ran cleanly, the conclusion was
internally consistent, ninja produced no errors — the failure mode was
invisible from the build output alone.

**Concrete tasks:**

1. New script `tools/jm2/verify_kernel_config.py`. Inputs:
   - `--vmlinux PATH` (required)
   - `--expected CONFIG=value` (repeatable; e.g., `CONFIG_KASAN=n`)
   - `--reference-mtime SECONDS` (optional; assert vmlinux mtime > this)
   - `--ikconfig-extract PATH` (optional; defaults to in-tree
     `kernel/oneplus/sm8850/scripts/extract-ikconfig`)

   Outputs: exit 0 if all expectations match the IKCONFIG embedded in
   vmlinux; exit non-zero with a per-flag diff table on mismatch.

2. Wire into `tools/jm2/wave_gate.py`'s pre-audit step. Any wave/phase
   that flips kernel CONFIGs must pass this gate before its kmi_audit
   result is treated as load-bearing.

3. Documentation: append a "Pre-flight gate" section to WIRE_UP_RECIPE.md
   that recommends this check before any new audit invocation.

4. Retroactive: re-run B'' audit through the gate (already done
   informally on 2026-05-15; codify the gate so the next config-flip
   work doesn't slip).

**Rationale for deferring:**
None — high priority. Cheap to implement (~50 LOC Python) and
immediately prevents the entire class of unmeasured-config-flip
failures. Schedule alongside the next wave that touches kernel config.

**When to revisit:** Immediately. Should land before any further
config-fragment work (next likely trigger: post-Phase-6 source-build
attempts that flip CONFIG_CFI_CLANG or other CRC-affecting flags).

---

## Source-build vendor_ramdisk first-stage module staging gap

**Surfaced:** 2026-05-15 (investigation of why source-build boot stack
fails before display init; classified the 53 missing first-stage
modules into A/B/C buckets).

**Context:**
`device/oneplus/sm8850-common/modules.list.msm.canoe` lists 97
first-stage modules. Only 44 actually end up in
`out/.../obj/PACKAGING/depmod_vendor_ramdisk_intermediates/lib/modules/`.
The 53 missing classified as:

- **Bucket A (load-list naming mismatch)**: 0. No quick rename fixes.
- **Bucket B (built but not staged)**: 40. ALL of these `.ko` files
  exist in `out/.../vendor_dlkm/lib/modules/` (built and shipping to
  vendor_dlkm partition), they just don't get staged into the
  first-stage vendor_ramdisk. Critical members: `ufs_qcom.ko` (storage
  host controller — without it kernel can't mount any partition),
  `iommu-logger`, `qcom_iommu_util`, `msm_dma_iommu_mapping`,
  `gic_intr_routing`, `memory_dump_v2`, `minidump`, `qcom_dma_heaps`,
  `sched-walt`, `qcom-reboot-reason`, `qcom-dload-mode`, `pmic-pon-log`,
  `bcl_pmic5`, `cpu_hotplug`. Root cause: `BOARD_VENDOR_RAMDISK_KERNEL_MODULES`
  (the AOSP staging variable) is **never assigned** in BoardConfigCommon.mk.
  Without it, only modules from `_LOAD` that happen to be in default
  staging end up there.
- **Bucket C (genuinely not built)**: 13. `oplusboot.ko`,
  `buildvariant.ko`, `boot_mode.ko`, `bootloader_log.ko`,
  `oplus_ftm_mode.ko`, `oplus_charger_present.ko`, `olc.ko`,
  `kernel_fb.ko`, `gunyah_loader.ko`, `gh_virt_wdt.ko`,
  `qcom-cpufreq-{hw,thermal}.ko`, `cpu_phys_log_map.ko`. These are
  wave wire-up gaps — some intentionally deferred (oplus boot stack
  was supposed to be Wave 1 but appears regressed), some not yet
  scoped (cpufreq, gunyah loader).

**Concrete tasks:**

1. Add to BoardConfigCommon.mk:177-189 area:
   ```
   BOARD_VENDOR_RAMDISK_KERNEL_MODULES := $(BOARD_VENDOR_KERNEL_MODULES)
   ```
   (or a curated subset that exactly matches modules.list.msm.canoe).
   This unlocks all 40 Bucket-B modules in one line.

2. Bucket C: cross-reference each against waves/wave_01_status.md and
   the source tree. For each module, decide: (a) genuinely missing
   wire-up (file a wave-3 sub-task), (b) intentionally deferred
   (document in noop_modules.md), (c) replaced by an OEM-prebuilt
   under a different name (document as resolved).

3. Verify post-fix: re-run the staging classification script (in
   project_phase6_boot_failure_state memory or recreate). Expect
   PRESENT count to jump from 44/97 to 84/97 after Bucket B fix.

**Rationale for deferring:**
Highest-leverage source-build improvement available. Without this,
the source-build path can't boot regardless of any other fix
(no UFS at first stage = no rootfs mount). Schedule before the next
source-build hardware test attempt.

**When to revisit:** Before next source-build hardware test. Strictly
required for source-build path; orthogonal to OEM-prebuilt path.

---

## BOARD_BOOTCONFIG missing androidboot.hypervisor.version=gunyah

**Surfaced:** 2026-05-15 (cross-reference vs upstream
OnePlus-SM8850-Development sm8850-common authoritative set + stock
vendor_boot bootconfig dump).

**Context:**
Stock vendor_boot bootconfig has 8 keys; ours
(`device/oneplus/sm8850-common/BoardConfigCommon.mk:94-101`) has 7.
Missing: `androidboot.hypervisor.version=gunyah`. Confirmed by:
(a) `unpack_bootimg` of stock vendor_boot.img bootconfig section,
(b) upstream OnePlus-SM8850-Development sm8850-common BoardConfigCommon.mk
authoritative set, (c) our build is missing `gunyah_loader.ko` which
is the producer of this property.

**Concrete tasks:**
1. Append `androidboot.hypervisor.version=gunyah \` to BOARD_BOOTCONFIG
   between `protected_vm.supported=true` and `load_modules_parallel=true`
   (alpha-sort order matches stock).
2. Verify post-build: `unpack_bootimg --boot_img out/.../vendor_boot.img`
   should show 8 bootconfig keys matching stock.

**Rationale for deferring:**
One-line fix. Note: kernel may not honor this property if
`gunyah_loader.ko` (Bucket C) isn't present in vendor_ramdisk first-stage
— but bootconfig parity removes one variable from the boot-failure
investigation regardless.

**When to revisit:** Schedule alongside the BOARD_VENDOR_RAMDISK_KERNEL_MODULES
staging fix (above) so the bootconfig property has a producer.

---

## Refresh device/oneplus/infiniti-kernel/ from current stock dump

**Surfaced:** 2026-05-15 (Phase 6 prebuilt-path retest preparation).

**RESOLVED 2026-05-15 (after a regression-and-recover cycle).** The
"refresh" was needed (Apr 24 blobs were stale from a different OEM
OTA: kernel `615f5dd9...` vs the device's actual installed
`2609ff52...` since Mar 25 at minimum). The first refresh attempt
introduced its own bug: I dumped modules from THREE source partitions
(vendor_dlkm + system_dlkm + vendor_ramdisk = 669 modules) into the
flat `infiniti-kernel/*.ko` dir, and the build's wildcard glob shoveled
all 669 into vendor_dlkm.img — wrong partition for 237 of them,
producing bootloops + dead recovery on hardware.

The community's Apr 13 LineageOS build (downloaded for diff comparison)
provided ground truth: their vendor_dlkm.img has **432 modules**
(matches what's in OEM stock vendor_dlkm.img — they extract from the
same OTA stream). So the corrected procedure is: **only modules from
vendor_dlkm.img belong in `infiniti-kernel/`; system_dlkm and
vendor_ramdisk modules ship via their respective partitions.**

Final corrected state (committed 2026-05-15):
- `Image` from May 8 stock boot.img (matches device kernel)
- `dtbo.img` from May 8 stock dtbo.img (passthrough via `INFINITI_DTBO_SOURCE := oem`)
- `vendor_boot.img` from May 8 stock vendor_boot.img verbatim (passthrough via `BOARD_PREBUILT_VENDORBOOTIMAGE`)
- 14 board_*.dtb from May 8 stock vendor_boot dtb section
- 432 *.ko from May 8 stock vendor_dlkm.img ONLY (no system_dlkm or vendor_ramdisk mixing)

Provenance pinned in `device/oneplus/infiniti-kernel/MANIFEST.txt`.
Path-consistency invariants in `BoardConfigCommon.mk:537-`
`$(error ...)` if any companion blob is missing — refusing to build
a hybrid OEM-prebuilt+source-built boot stack (which is the regression
mode that bit us).

**Recovery target for `device/oneplus/infiniti-kernel/`**: the
device's own firmware dump at `dump/stock_images/`. The
`MANIFEST.txt` inside `device/oneplus/infiniti-kernel/` documents
the per-blob extraction procedure (which partition each blob comes
from, which tool extracts each — note that vendor_dlkm.img is ext2
and needs 7z not fsck.erofs). Per-blob SHA256s are pinned in the
manifest. Git history at the jm2 fork
(https://github.com/jm2/android_device_oneplus_infiniti-kernel)
preserves every refresh as a commit.

**On older / scratch dirs that previously existed under `dump/`**:
- `infiniti-kernel-apr24-backup/`, `infiniti-kernel-may8-source/`,
  `infiniti-kernel-may8-mixed-pre-trim/`, `hybrid-super-experiments/`
  were stripped 2026-05-16 after this entry was resolved. Their
  content is either preserved in git history (apr24 baseline is in
  the jm2 fork's commit log as `f8a6b24 Initial prebuilts from
  CPH2745_16.0.3.503(EX01)` lineage), or no longer needed (mixed-pre-trim
  was forensic; hybrid-super was a won't-do experiment).

**Still kept** under `dump/`:
- `stock_images/` — the device's May 8 firmware dump, source of truth
  for any future infiniti-kernel/ refresh.
- `community_apr13/` — community ground-truth ROM extract, retained
  as VIEW-ONLY reference for future diff comparisons.

**Procedure (for future refreshes):**
```bash
SI=/path/to/stock_images_dump
IK=device/oneplus/infiniti-kernel
UB=$OUT_HOST/bin/unpack_bootimg

# 1. Kernel + dtbo (direct copy)
$UB --boot_img $SI/boot.img --out /tmp/k && cp /tmp/k/kernel $IK/Image
cp $SI/dtbo.img $IK/dtbo.img

# 2. DTBs (split concatenated FDT blob from vendor_boot)
$UB --boot_img $SI/vendor_boot.img --out /tmp/vb
python3 device/oneplus/sm8850-common/tools/dtb/split_dtb.py /tmp/vb/dtb /tmp/dtbs
n=0; for f in /tmp/dtbs/oem-*.dtb; do cp "$f" "$IK/board_${n}.dtb"; n=$((n+1)); done

# 3. Modules (vendor_dlkm: ext2 → 7z; system_dlkm: EROFS → fsck.erofs;
#    vendor_ramdisk: lz4 cpio)
mkdir -p /tmp/vdlkm; (cd /tmp/vdlkm && 7z x $SI/vendor_dlkm.img)
fsck.erofs --extract=/tmp/sysdlkm $SI/system_dlkm.img
mkdir -p /tmp/vramdisk; (cd /tmp/vramdisk && lz4 -dc /tmp/vb/vendor_ramdisk00 | cpio -idmv)
rm $IK/*.ko
cp /tmp/vdlkm/lib/modules/*.ko $IK/
find /tmp/sysdlkm -name "*.ko" -exec cp {} $IK/ \;
for f in /tmp/vramdisk/lib/modules/*.ko; do [ ! -f "$IK/$(basename $f)" ] && cp "$f" $IK/; done
```

---

## Hybrid super.img assembly (build_super_image.py + lpmake direct)

**Surfaced:** 2026-05-15 (Phase 6 hardware bisection;
"stock-via-our-infra" rabbit hole).

**WON'T-DO 2026-05-15.** Two attempts (`build_super_image.py` with
`:none:` attrs, then direct `lpmake` with `:readonly:` attrs) both
produced devices that boot to the AOSP-fallback "android" text
animation then reboot via Android rescue-party. Stock super assembly
appears to require additional partition layout details (sizing, group
layout, slot init) that are hard to reverse-engineer without an
actual byte-for-byte stock super.img to compare against. User pivoted
away: "I don't even care if we get stock working through our infra at
this point."

**OEM-prebuilt path bypasses super assembly entirely** (uses the
device's existing super partition contents) and is the recommended
working path. If we ever need to revisit, the LP metadata investigation
should pick up from: `/tmp/hybrid_v1/super_v2_raw.img` had correct
`virtual_ab_device` flag, 3 metadata slots, A/B groups, and `readonly`
attributes — but something about the partition layout still didn't
match what the bootloader expects. Likely candidates: extents not
aligned to power-of-2 block boundaries; missing `default` group sizing;
auto-slot-suffixing layout differences from explicit-suffix layout.

**When to revisit:** Only if a specific need arises (e.g., shipping a
LineageOS-branded full ROM that includes a custom super.img). Don't
revisit for diagnostic purposes — use OEM-prebuilt path instead.

---

## Evaluate dtbo construction swap (granular overlays vs merge_dtbs)

**Surfaced:** 2026-05-15 (cross-reference vs OnePlus-SM8850-Development
upstream sm8850-common; corroborates source-build dtbo rank-1
suspect from Phase 6 diagnostic).

**Context:**
Our source-build path produces dtbo.img via `dtboimg.mk` +
`tools/dtb/select_techpack_dtbos.sh`, packing 11 granular per-techpack
overlays (~1 MB total). Upstream OnePlus-SM8850-Development
sm8850-common's source-build path uses
`BOARD_USES_QCOM_MERGE_DTBS_SCRIPT := true` with
`TARGET_NEEDS_DTBOIMAGE := true` (whole-tree merge_dtbs script,
closer to monolithic). Their `android_vendor_lineage` fork has
relevant patches: "merge_dtbs: Add support for
TARGET_MERGE_DTBOS_WILDCARD" (Apr 10) and "merge_dtbs: Widen techpack
search path" (Mar 31). Stock OEM dtbo is 8 monolithic overlays
(~10 MB).

If our 11 granular overlays fail to apply against canoe-fat at
bootloader-overlay-apply stage (fdt_overlay), the bootloader proceeds
with a broken DT and boot fails. This was rank-1 in the May-15
diagnostic summary but not validated against hardware (Phase 6 is
currently using OEM-prebuilt path which uses OEM dtbo.img directly).

**Concrete tasks:**

1. Run static `fdtoverlay`-apply test: each of our 11 overlays × 4
   canoe-fat bases. Any FAIL is a candidate root cause.
   Script staged at `/tmp/bootdiag/test2_dtbo_apply.sh` (move to
   `tools/jm2/dtbo_apply_test.sh` if useful).

2. If overlay-apply passes for all 11 × 4: rank-1 hypothesis is
   refuted, problem is downstream. If any overlay FAILs: fix or
   exclude it, then test again.

3. If overlay-apply test reveals systematic incompatibility: evaluate
   swap to upstream merge_dtbs approach. Pull their
   `android_vendor_lineage` merge_dtbs patches into our `vendor/lineage`
   fork, configure `BOARD_USES_QCOM_MERGE_DTBS_SCRIPT := true`, build,
   compare resulting dtbo.img to stock and to our current granular
   dtbo.img.

**Rationale for deferring:**
Source-build path concern only. OEM-prebuilt path uses the OEM dtbo
directly and isn't affected. Schedule when source-build path returns
to active work.

**When to revisit:** When source-build hardware test resumes (likely
post-Bucket-B-staging-fix and post-Bucket-C-investigation).

---

## [Task A] Audit proprietary_vendor_oneplus_infiniti for IMEI/RIL completeness

**Surfaced:** 2026-05-15 (community report; preventive).

**Context:**
Community LineageOS builds for infiniti show generic Qualcomm placeholder
IMEI, likely from missing RIL config blobs (qcril.db,
oplus_carrier_pack/, modem firmware) in their vendor blob set. Their
flash sequence or super.img reconstruction may also touch modem-NV
partitions (modemst1, modemst2, fsg). Our per-partition flash approach
doesn't touch these, so we should be safe — but vendor blob completeness
deserves a check.

**Concrete tasks:**

1. Diff `proprietary_vendor_oneplus_infiniti` from the
   OnePlus-SM8850-Development org against our vendor blob set.
   Specifically look for `qcril.db`, `oplus_carrier_pack/`, modem
   firmware blobs they have that we don't. If theirs is more complete,
   include the missing blobs in our build.

2. Capture device IMEI before next first-flash:
   - `fastboot getvar imei` (and `imei1`/`imei2`)
   - Or pre-flash if device boots: `*#06#` on dialer, or
     `getprop persist.radio.imei`

   Verify it's the real device IMEI, not generic Qualcomm placeholder.
   If already a placeholder, IMEI was lost in prior flash attempts and
   restoration becomes a separate task.

3. Document our flash sequence's modem-NV preservation: ensure
   `modemst1`, `modemst2`, `fsg` are not in any flash list.

**Rationale for deferring:**
Preventive, not blocking the boot-failure investigation. Schedule
before next first-flash on a known-good IMEI device.

**When to revisit:** Before next first-flash sequence on a device
whose IMEI we want to preserve.

---

## [Task B] Scope DT2W / touch-gesture support in tp_hbp_syna_s3910

**Surfaced:** 2026-05-15 (community report; preventive).

**Context:**
Community framing: "DT2W requires kernel side change which will be
implemented once we move to OSS source." We're already source-building
the kernel + tp_hbp_syna_s3910 (Wave 2D). DT2W enablement may be a
matter of identifying the right CONFIG flag or sysfs entry, not a
multi-week implementation.

**Concrete tasks:**

1. In `kernel/oneplus/sm8850-modules/.../oplus_touchscreen_v2/` and
   the hbp tree: grep for `double_tap`, `dt2w`, `wake_gesture`,
   `touch_gesture`. Identify the code paths.

2. Check Kconfig for `CONFIG_*_DT2W`-style flags. If present and we
   haven't set them, add to our config fragment.

3. Look for sysfs entries the driver exposes for gesture enable
   (typically `/sys/class/touchscreen/.../gesture_enable` or similar).

4. Check device tree for `wakeup-gestures` or similar properties in
   the touch panel node.

5. Defer actual hardware testing to post-Phase-6. Preparation work
   (identifying code paths and config flags) can land as a
   Wave-2-closeout-adjacent item.

**Rationale for deferring:**
Preventive, not blocking. Worth scoping early since source-build path
makes it tractable to fix; community framing suggests they consider it
non-trivial.

**When to revisit:** When source-build path is booting and userspace
gesture settings work; this is a power-user feature that follows MVB.

---

## Phase-5 wave-2 `BOARD_VENDOR_KERNEL_MODULES` collision class

**Surfaced:** 2026-05-16 (Phase-6 OEM-prebuilt v9/v10 builds; clean
rebuild after layout-adapt + repo sync).

**Context:**
`BOARD_PREBUILT_KERNEL=true` is structurally weaker than its name
implies. The toggle gates the kernel binary build (via
`TARGET_FORCE_PREBUILT_KERNEL := true` flipping kernel.mk:248's
`FULL_KERNEL_BUILD := false`) — but Phase-5 wave-2 modules under
`vendor/qcom/opensource/*/Android.mk` still get processed by kati and
unconditionally contribute to `BOARD_VENDOR_KERNEL_MODULES`:

```makefile
LOCAL_MODULE_PATH := $(KERNEL_MODULES_OUT)
BOARD_VENDOR_KERNEL_MODULES += $(LOCAL_MODULE_PATH)/$(LOCAL_MODULE)
```

Under the prebuilt path, `KERNEL_MODULES_OUT` is empty (no
source-kernel build → no install dir computed), so the appended path
becomes `/<module>.ko`. AOSP's `build/make/core/Makefile`
`depmod_vendor_stripped_intermediates` rule registers the install
target by basename, producing the same `vendor_dlkm/lib/modules/<mod>.ko`
target as the OEM-prebuilt copy already added by the
`infiniti-kernel/modules/vendor_dlkm/*.ko` wildcard in
`sm8850-common/BoardConfigCommon.mk`. Result:

- **v9 (default):** `ninja: out/build-lineage_infiniti.ninja: multiple
  rules generate out/target/product/infiniti/vendor_dlkm/lib/modules/msm_kgsl.ko`
  (ninja dupbuild=err)
- **v10 (option C — `KERNEL_MODULES_OUT := infiniti-kernel/modules/vendor_dlkm`):**
  `build/make/core/Makefile:713: error: overriding commands for target
  out/.../depmod_vendor_stripped_intermediates/msm_kgsl.ko` (kati layer)
  — same root cause, moved one layer up because both rules now resolve
  to the *same* path string

A defensive `BOARD_VENDOR_KERNEL_MODULES := $(filter-out /%,$(...))` in
BoardConfigCommon.mk runs at BoardConfig parse time, but the Android.mk
appends happen *later* during kati processing — the filter has no effect.

**Scope of the class (2026-05-16 grep):**
Across all of `kernel/oneplus/sm8850-modules`, exactly **one** Android.mk
has an uncommented `BOARD_VENDOR_KERNEL_MODULES +=` line:
`vendor/qcom/opensource/graphics-kernel/Android.mk`. Two others
(`mmrm-driver`, `synx-kernel`) have the line *commented out* by
upstream, and the rest of the 50+ Android.mk files don't contribute at
all (they rely on the `infiniti-kernel/` wildcard for vendor_dlkm
inclusion).

**RESOLVED (minimal-B, 2026-05-16):** wrapped the single uncommented
contribution in `ifneq ($(BOARD_PREBUILT_KERNEL),true) ... endif`.
This preserves source-build behavior (where `KERNEL_MODULES_OUT` is
populated and the entry is a real install path) while skipping the
contribution under the prebuilt-kernel path.

**Concrete tasks (full-B follow-up, not yet landed):**

1. **Defensive in-place pattern**: When future wave-2 modules
   uncomment or add `BOARD_VENDOR_KERNEL_MODULES += ...` lines (e.g.,
   if mmrm-driver or synx-kernel are uncommented as part of further
   wave work), they must adopt the same `ifneq` wrap. WIRE_UP_RECIPE
   should call this out as a checklist item under "Phase-5 module
   Android.mk authoring".

2. **Compile-time enforcement** (preferred over checklist): teach
   `tools/jm2/wave_gate.py` to flag any Android.mk under
   `kernel/oneplus/sm8850-modules/vendor/**` that has an
   `^[^#]*BOARD_VENDOR_KERNEL_MODULES.*\+=` line *not* preceded by an
   `ifneq ($(BOARD_PREBUILT_KERNEL),true)` block. Reject the wave's
   close-out gate until the wrap is in place.

3. **Upstream consideration**: this is also an upstream graphics-kernel
   bug (the line is unconditional in OEM Kleaf trees because Kleaf
   doesn't have a `BOARD_PREBUILT_KERNEL` concept; AOSP-side adapters
   need it). Worth a PR to OnePlus-SM8850-Development eventually so
   future kernel.opensource pulls inherit the fix.

4. **Discipline lesson worth surfacing in WIRE_UP_RECIPE**: the
   `BOARD_PREBUILT_KERNEL` toggle does NOT gate Phase-5 module
   contributions. The toggle name is misleading; the correct mental
   model is "kernel binary toggle" not "kernel + modules toggle". Any
   future toggle that claims to disable a build path should be
   audited against actual contribution mechanisms.

**Rationale for deferring (full-B):**
Minimal-B unblocks the Phase-6 hardware test. The full-B work
(checklist + gate enforcement + upstream PR) is preventive against
recurrence, not blocking. The collision class is now named and
understood; the gate work can land in the next discipline-tooling
wave alongside the pre-flight verification gate.

**When to revisit:** Before the next wave-2 module Android.mk addition
(specifically: if mmrm-driver or synx-kernel get their currently-commented
lines uncommented, OR if new external Qualcomm module trees are added
to `vendor/qcom/opensource/`).

---

## Evaluate Option B: switch audio HAL to source-built (drop OEM audio prebuilts)

**SUPERSEDED 2026-05-30 by the sm8850-devs convergence.** `audio/primary-hal` now
tracks the org `jm2/android_hardware_qcom_audio-ar` fork, which is **configs-only**
(`configs/canoe`, no `hal/` source). There is no source-built audio HAL to switch to,
so Option B is off the table; audio is supplied by the OEM v3 prebuilts via
`proprietary-files.txt`, and the Option-A `audio-vintf-disable.patch` is **dropped**
(nothing to patch). See `device/oneplus/sm8850-common/README.md` "Audio". The
historical context below is kept for the record.

**Surfaced:** 2026-05-17 (Phase 4 `extract_v1` build hit Soong namespace
collision on `audioeffectservice_qti.xml` + `manifest_audiocorehal_default.xml`
because `hardware/qcom-caf/sm8850/audio/primary-hal/hal/` source-builds the
same module names that our extracted OEM prebuilts ship).

**Context:**
The immediate fix (Option A, landed 2026-05-17) was to disable the
`hardware/qcom-caf/sm8850` source-built VINTF manifest prebuilts so our
extracted v3 OEM manifests win, matching our `extract-files.py`
`replace_needed audio.common-V1-ndk → V3-ndk` HAL fixups. This preserves
the OEM audio HAL stack (libaudiocorehal.qti.so + patched NDK deps) at the
cost of making source-built `libaudiocorehal.default.so` dead code in
vendor.img. Replay-patch at
`device/oneplus/sm8850-common/patches/hardware-qcom-caf-sm8850-audio-vintf-disable.patch`.

Option B is the more principled alternative — use the source-built audio
HAL throughout, drop OEM audio prebuilts. Symmetric with Action A from
the 2026-05-17 extract.py-driven rebuild (drop OEM camera AIDL NDK
prebuilts, use AOSP source-build).

**Concrete tasks:**

1. Drop `vendor/etc/vintf/manifest/audioeffectservice_qti.xml` and
   `manifest_audiocorehal_default.xml` from
   `device/oneplus/sm8850-common/proprietary-files.txt` (revert Action B
   of the 2026-05-17 extract.py-driven rebuild — commit `efc1581`).

2. Re-enable the two `prebuilt_etc` entries in
   `hardware/qcom-caf/sm8850/audio/primary-hal/hal/{default,effects}/Android.bp`
   (remove `enabled: false`). Use `patch -R` on the replay-patch.

3. Revert audio-related blob_fixups in
   `device/oneplus/sm8850-common/extract-files.py`:
   - `vendor/lib64/hw/libaudiocorehal.qti.so` `replace_needed` entries
     (sounddose V1→V2, common V1→V3, libaudio_aidl_conversion → _prebuilt)
   - `vendor/lib64/hw/android.hardware.bluetooth.audio_sw.so` +
     `libaudioserviceexampleimpl.so` shared `replace_needed`
   - `vendor/lib64/android.hardware.bluetooth.audio-impl_prebuilt.so`
   - `vendor/lib64/libaudio_aidl_conversion_common_ndk_prebuilt.so`
   - 6 `soundfx/lib*aidl.so` entries
   - `vendor/lib64/libwfdmmsrc_proprietary.so` (audio.common V2→V3)

4. Audit and remove OEM audio HAL .so blobs from `proprietary-files.txt`
   that are redundant with source-built equivalents (`libaudiocorehal.qti.so`
   etc.). Determine which OEM-specific audio behaviors live in OEM blobs
   that would be lost — e.g., OPlus-specific audio policy hooks, tuning.
   Likely require keeping some OEM blobs and only dropping the core HAL.

5. Test on hardware: build, flash, validate audio works (incoming/outgoing
   calls, music playback, notifications, ringer, mic recording, BT audio).
   Source-built HAL may not cover all OEM-specific audio features.

6. If validation passes, this is the more durable choice — removes
   un-tracked `hardware/qcom-caf` edits and aligns with the "preserve
   source-built efforts" principle.

**Rationale for deferring:**
Option A unblocks Phase 4 build in minutes. Option B requires substantial
analysis (which OEM blobs encode policy vs which are pure HAL glue),
fixup unwinding, and on-device validation of source-built audio against
OEM expectations. Risk of audio regressions is non-trivial. Schedule
when we have a known-bootable Option-A baseline to A/B against.

**When to revisit:** After a bootable Option-A baseline lands and is
flash-validated. The known-good baseline enables clean A/B testing of
audio quality between OEM-prebuilt and source-built variants.

---

## extract-utils write_mk_firmware_ab_partitions iterates ALL firmware files, not just AB ones

**Surfaced:** 2026-05-18 (Phase 4 extract_v25 target_files packaging step
asserted "Failed to find GloveDetect.img" — GloveDetect.tflite is a
touchscreen firmware config file, not a partition image).

**Context:**
`tools/extract-utils/extract_utils/makefiles.py` `write_mk_firmware_ab_partitions`:

    def write_mk_firmware_ab_partitions(files: Iterable[File], out: TextIO):
        has_ab = False
        for file in files:
            if FileArgs.AB in file.args:
                has_ab = True
                break
        if not has_ab:
            return
        out.write('\nAB_OTA_PARTITIONS +=')
        for file in files:          # bug: iterates ALL files, not filtered to AB-flagged
            line = f' \\\n    {file.root}'
            out.write(line)

Once any single file in the firmware proprietary file list has the `;AB`
flag, every other file in the list gets added to AB_OTA_PARTITIONS —
regardless of its own flags. For infiniti, our `proprietary-firmware.txt`
has real AB partitions (abl.img;AB, aop.img;AB, etc.) which trips
`has_ab = True`, then extract-utils adds 17 touchscreen firmware files
(GloveDetect.tflite, libafe_s3910.so, model.tflite, vnd_*.xml, etc.) as
false-positive AB partitions. The build then dies in target_files
packaging when it tries to find `GloveDetect.img` (and the others).

**Workaround in place (2026-05-18):**
`~/android/dump/extract_safely.sh` post-extract step strips the 19 known
false-positive entries from
`vendor/oneplus/infiniti/BoardConfigVendor.mk`. Durable as long as the
wrapper is always used (memory note `reference_extract_workflow.md`
already enforces this).

**Concrete tasks:**

1. Confirm the bug upstream by reading current LineageOS HEAD of
   `tools/extract-utils/extract_utils/makefiles.py` — verify the loop
   isn't filtered.

2. Submit upstream patch: filter the loop to AB-flagged files only:
   ```python
   for file in files:
       if FileArgs.AB not in file.args:
           continue
       line = f' \\\n    {file.root}'
       out.write(line)
   ```

3. Confirm fix doesn't regress on other LineageOS devices (some may
   rely on the current behavior — though that would be a separate bug).

4. After upstream lands and we sync, remove the post-extract workaround
   from `extract_safely.sh`.

**Rationale for deferring:**
Workaround unblocks Phase 4 build today. Upstream fix is preventive and
benefits all LineageOS devices, but doesn't materially change our
flash-readiness timeline.

**When to revisit:** Next time we sync repo (would lose our local
extract-utils edit if we patched in-tree; better to upstream).

---

## Manually-injected vintf manifests will be wiped on next `extract.py` re-run

**Surfaced:** 2026-05-18 (Tier 1 v5 VINTF fix — commit `4f73446` in
`device/oneplus/sm8850-common`).

**Context:**
Tier 1 v5 fixed the IPAL/IAGM "Conflicting FqInstance" runtime VINTF
error by removing `manifest_audio_qti_services.xml` from
`DEVICE_MANIFEST_FILE` in `common.mk` and shipping the 4 contained HAL
declarations as 4 separate extracted vintf manifest fragments.

Our stock dump only contained 2 of the 4 fragments
(`Manifest_IPAL.xml`, `Manifest_IAGM.xml`). The other two
(`Manifest_IPALEventNotifier.xml`, `Manifest_IListenSoundModel.xml`) were
**copied from the community Apr 13 ROM scratch dir** at
`~/scratch/userspace_diff/community/vendor/etc/vintf/manifest/` directly
into the generated tree at
`vendor/oneplus/sm8850-common/proprietary/vendor/etc/vintf/manifest/`,
and corresponding `prebuilt_etc_xml { … }` entries + `PRODUCT_PACKAGES`
entries were hand-added to the generated `Android.bp` and
`sm8850-common-vendor.mk`.

`vendor/oneplus/sm8850-common/` is regenerated by `extract.py`. The next
run will:

1. Re-create `proprietary/` from the dump — overwriting the two manually
   copied XML files (gone).
2. Re-generate `Android.bp` + `sm8850-common-vendor.mk` from
   `proprietary-files.txt`. Since both manifest filenames ARE listed in
   `proprietary-files.txt` (committed in `4f73446`), extract.py will
   either WARN about the missing source files and skip them, or fail
   outright. Either way the entries in `Android.bp` /
   `sm8850-common-vendor.mk` may be missing.

The IPAL/IAGM conflict will return on the very next build after a
re-extract.

**Concrete tasks:**

1. Decide on a canonical location for "manual vendor overlay" files
   (proposal: `~/android/dump/manual_vendor_overlay/proprietary/...` with
   the same subtree shape as the proprietary/ tree).

2. Save the canonical copies of `Manifest_IPALEventNotifier.xml` and
   `Manifest_IListenSoundModel.xml` there.

3. Extend `~/android/dump/extract_safely.sh` post-extract step to:
   - rsync the overlay tree into `vendor/oneplus/sm8850-common/proprietary/`
   - re-run a snippet to ensure the entries exist in `Android.bp` and
     `sm8850-common-vendor.mk` (or, simpler: have extract.py succeed on
     those entries by overlaying the dump BEFORE extraction — but the
     dump is .img files, not mounted directories, so this requires
     mounting / overlay logic too).

4. Alternative: convert `vendor/oneplus/sm8850-common/` into a git
   repository and stop treating extract.py output as ephemeral. Heavier
   lift but eliminates the entire class of "extract.py wiped my edits"
   problems and gives us proper diffs / reverts.

**Rationale for deferring:**
No re-extract is planned in the immediate critical path; current build
state is correct and tier1_v5 zip is produced. Risk is only realized on
the next extract.py invocation.

**When to revisit:** Before the next `extract_safely.sh` invocation,
OR sooner if other vendor proprietary churn (Tier 3 .so additions, etc.)
triggers a re-extract.

---

## WiFi: byte-reversed WLAN MAC — fix needs a source-built cnss2 (2026-06-04)

The converged canoe build BOOTS; WiFi is the one remaining break. Root-caused
on-device (rooted adb, driver reload + dmesg):

**Root cause:** the WLAN DMS MAC arrives **byte-reversed**. Device WLAN MAC =
`c3:bb:04:bc:ed:78` = reverse of the real `78:ED:BC:04:BB:C3` (= Bluetooth MAC +1,
the standard WLAN=BT+1). Reversed, first octet `0xC3` has the **multicast bit set**, so
`qcacld-3.0` `__wlan_hdd_validate_mac_address()` (core/hdd/src/wlan_hdd_main.c:1673)
rejects it -> cnss `Failed to probe host driver, err = -1` (platform/cnss2/pci.c:3492) ->
no `wlan0`. OnePlus's `OPLUS_FEATURE_WIFI_MAC` reverses the MAC back only on the FW path
(`cnss_wlfw_wlan_mac_req_send_sync`, qmi.c:1648-1650), leaving the qcacld-facing
`dms.mac` reversed. Only bites units whose real MAC ends in an odd octet (ours: C3);
even-ending units pass validation -- the "works on some devices, not ours" split.
RULED OUT (with evidence): orange/unlocked state (community works unlocked); soft-SKU
`cnss_softsku_peach.pfm` (stand-in loaded + sent to FW -> probe still failed identically);
TME err 83 benign (tmel_peach_*.elf present).

**Fix (cnss2 source patch):** make the MAC byte-order consistent so qcacld gets the valid
unicast MAC -- e.g. in `cnss_qmi_get_dms_mac` (platform/cnss2/qmi.c:4150) de-reverse
`plat_priv->dms.mac` when its first octet has the multicast bit set, reconciled with the
OPLUS WLFW-path reversal so the FW still gets the correct MAC. Finalize spot/condition
with build+test.

**Blocked on the source-kernel build** (prebuilt stock-OOS kernel can't load a patched
module: vermagic + CONFIG_MODVERSIONS CRC mismatch; prebuilt SHA b065695cf38 not in our
source). Source-build scoping (USE_PREBUILT_KERNEL=false):
- canoe config wiring DONE (sm8850-common BoardConfig: TARGET_KERNEL_CONFIG ->
  vendor/canoe_perf.config; module-list refs -> .msm/.oplus.canoe). Build now reaches the
  real kernel compile.
CORRECTION (2026-06-04, after reading all sm8850/sm8850-modules MDs in full): my first pass
mis-scoped this. This build IS `mka kernel`/Kbuild (the whole fork translates the OEM Bazel
specs to Kbuild for `mka kernel` — README.lineage.md, README.md, IMPLEMENTATION_PLAN §2,
WIRE_UP_RECIPE). It is NOT a Kleaf-direct or from-scratch project; the kernel @ 49797ea already
compiles clean via `mka kernel` + system clang 22 (Phase-5 Wave-2, ~69.7% boot prediction,
0 depmod errors, DTBs composed in-tree Phase G). My scoping build hit RAW failures only because:
  (a) the May-30 convergence overwrote the canoe BoardConfig wiring with the org's `pineapple`
      config (device tree) — fixed by the pineapple->canoe edit (dc40ce1);
  (b) I built WITHOUT the known `-Werror` suppression. `-Wdefault-const-init-field-unsafe` is a
      clang-21+ diagnostic (clang 22 stricter than OEM clang) — a routine class the project
      already demotes with `-Wno-error=default-const-init-field-unsafe` (WIRE_UP_RECIPE Step 7.7);
      mainline disables it kernel-wide in KBUILD_CFLAGS. My asm-offsets hit just needs the same
      one-line suppression in the kernel, NOT a different toolchain.
REAL remaining blockers for a BOOTABLE source kernel (per the docs, NOT toolchain/Kleaf):
  (1) KMI-strict CRC parity — OEM prebuilts fail module_layout CRC vs our kernel (557/557, ACK
      patch-level skew r8 vs OEM o) → source-build the modules.load tail (Path B).
  (2) one-line BOARD_VENDOR_RAMDISK_KERNEL_MODULES fix to stage ufs_qcom.ko first-stage (never
      landed → can't mount rootfs); see phase_6_session_2026_05_15.md.
  (3) per-partition module-load-list wiring — canoe ships the combined modules-lists/
      modules.list.msm.canoe (133 mods) + blocklists, NOT the per-partition .list.{msm,oplus}.canoe
      that BoardConfig reads (those are genuinely absent in the kernel root; my rename left them
      empty — compiles, won't boot until rewired).
  (4) DT-bindings: my scope build failed on `bindings/qcom,audio-ext-clk.h` for canoe-audio.dtsi
      despite Phase-G fat.dts present — to reconcile with the Phase-G include-path setup (likely a
      sync/invocation gap in my attempt, not a missing repo).
The source kernel has never been confirmed BOOTING (Phase 6 hw tests used the PREBUILT kernel).

**Rationale for deferring:** device is a usable daily-driver minus WiFi; finishing the source
kernel (KMI tail + first-stage staging) is a multi-phase continuation. Full context in agent
memory `project_jun03_wifi_softsku_rootcause`.

**When to revisit:** SUPERSEDED 2026-06-05 — the source-kernel route pivoted from hand-Kbuild to
the OEM **Kleaf** `canoe_perf_dist` path (builds the OEM's exact kernel → fixes the KMI skew that
blocked the Kbuild route, and uses the OEM's pinned clang 19 → no `-Werror` friction). The cnss2
MAC patch will be applied on the OEM Kleaf tree. See `KLEAF_PIVOT.md` (this dir). The Kbuild waves
(KMI Path B + ufs_qcom staging) are parked, not deleted.

---

## Generalize the Kleaf source-build path into per-device tooling (2026-06-05)

The OEM-Kleaf route (`KLEAF_PIVOT.md`) is mostly upstream already (`kernel.mk` Kleaf path). To make
future-device kernel bring-up "import + pin snapshot + 4 BoardConfig vars" instead of a build-system
rewrite, build: (1) a kernel_platform importer (OEM superproject → sibling `kernel-<ver>` `repo`
layout + manifest; platform codename = ONE guarded parameter — cf. the `klsplit.py` sketch from the
Opus-Web session); (2) a wiring generator (parse `build.config.msm.<plat>` + `target_variants.bzl`
→ BoardConfig block + `device.bazelrc` + manifest); (3) a snapshot pinner (deployed kernel
SHA/build-date/OOS tag → OEM "Synchronize code for…" snapshot commit); (4) a defconfig-fragment
shim (LOS data → Starlark `pre/post_defconfig_fragments`). Full notes in `KLEAF_PIVOT.md`
§generalization. **BASE PROVEN 2026-06-08** — `canoe perf` builds RC=0 from the OEM Kleaf drop (see
`KLEAF_PIVOT.md` §"STEP (c) RESULT"), so this generalization can now be built against a known-good
reference. Still deferred (it's tooling, not blocking the canoe bring-up). The concrete adapter design
this generalization derives from — OEM-wrapper build driver + WLAN-as-Kleaf-DDK, with the per-device
surface reduced to ~8 BoardConfig vars — is fully specified in `KLEAF_WIREUP_PLAN.md` (the canoe
instance validates the tooling).

---

## eSIM provisioning fails at ES10b.LoadBoundProfilePackage (eUICC SW=6A88)

**Surfaced:** 2026-06-07 (OpenEUICC LPA bring-up; two attempts with a standard data-only **Google Fi**
eSIM, byte-identical failure). **REWRITTEN 2026-06-09 after a full multi-agent investigation** —
several of the Jun-07 working theories were disproven; do not trust earlier copies of this entry.

**Corrected failure narrative (2026-06-09):** Both attempts completed the entire network phase
(ES9+ initiateAuthentication → authenticateClient → getBoundProfilePackage, all HTTP 200, full
8166-byte BPP delivered) AND all on-chip ES10b steps through PrepareDownload (41 APDUs, all
success). The LoadBoundProfilePackage phase then issued exactly **two APDUs** and died: at
OpenEUICC's es10x MSS default of 63, BPP slice 1 (BF36 header + complete InitialiseSecureChannel,
191 B) is a 4-block STORE DATA chain; block P2=00 was **accepted by the card** (170 ms — longest
round-trip of the session), and the 2nd APDU drew bare **SW=6A88**. NOT a "~60-APDU large write"
failure — that figure was the whole session. Per SGP.22 (§5.7.6, §3.1.5, §5.7.2) a bare 6A88 here
is **transport/stream-level** ("no RSP session" / "TLV not expected next"); all compliant
content/crypto rejections (bad signature, txid, remoteOpId, keyset) must return an ErrorResult TLV
with SW **9000**, which lpac would map to a specific reason — `reason 255` means bare SW, no TLV.
Clean rollback is explained by OpenEUICC explicitly calling cancelSessions after failures
(`LocalProfileAssistantImpl.kt:239-242`), proving nothing about the card.

**The app stack is exonerated by direct execution:** the deployed lpac (submodule d214738, zero
local patches) was compiled into a host harness and fed the REAL failing BPP at mss=63 and 120 —
output byte-identical to an independently computed SGP.22 §2.5.5 reference segmentation. Reference
artifacts (expected APDU streams, BPP binary, harness): **`~/android/esim_6a88_reference/`**.

**DISPROVEN (do not re-litigate):** (H1-as-stated) generic `procedure_bytes=SKIP` chain re-framing —
byte-structurally identical chains (AuthenticateServer 15 APDUs, PrepareDownload 13) succeeded
seconds earlier under the same SKIP; (H2) modem/Oplus LPA BPP policing; (H3) `isEs10=false`
asymmetry (constant across success+failure; MEP=NONE makes it vacuous); (H4) RSP session loss in
the HTTP gap (the failing gap was the SHORTEST of three; longer ones survived twice); (H5) lpac
chunking bug (refuted by direct execution); (H6) card content/state/orange-state rejection (the
card accepted the block containing txid/remoteOpId/CRT; spec requires TLV+9000 for those).
**ALSO DISPROVEN — the Jun-07 "OMAPI is broken" diagnosis:** OMAPI was never attempted against the
eUICC. The "OMAPI APDU interface unavailable" lines were OpenEUICC's removable-eSIM scan of the
EMPTY pSIM slot 0 (CARDSTATE_ABSENT, eSTK.me vendor AIDs). The privileged flavor routes embedded
eUICCs straight to TelephonyManager BY DESIGN (`PrivilegedEuiccChannelFactory.kt:21-27`). The SE
stack is healthy: QTI SE HAL up, `ISecureElement/SIM2` (the eUICC) mIsConnected=true, OpenEUICC
holds SECURE_ELEMENT_PRIVILEGED_OPERATION (bypasses ARA/ARF).

**Surviving hypotheses (ranked):**
- **S1 (lead):** qcril/modem mishandling of the load-phase chain correlated with
  `persist.vendor.radio.procedure_bytes=SKIP` (verified set; consumed by `/vendor/lib64/libqcrilNr.so`)
  — SKIP masking block-1's true response (61xx?) desyncing the card's STORE DATA block counter →
  "not expected next" → 6A88. The 170 ms block-1 anomaly is the tell.
- **S2:** other qcril/modem chain mangling (re-segmentation, Lc rewrite, block-counter corruption)
  below TelephonyManager. Closest public analogue: lpac issue #185 (Xperia 10 IV, Qualcomm SD695,
  LineageOS + OpenEUICC, same first-segment transport-SW class).
- **S3 (last resort):** eUICC-OS quirk rejecting a well-formed chain.

**Concrete tasks (B1 resolves the whole space — ~5 min, NO rebuild needed):**
1. **B1 — instrumented retry:** OpenEUICC developer options → enable **verbose logging** (full APDU
   hex+SW per block ships in the deployed binary, `TelephonyManagerApduInterface.kt:56-64`, bypasses
   RILJ redaction); `adb shell setprop persist.vendor.radio.procedure_bytes RETURN`; capture logcat;
   retry the same Fi QR once. Success ⇒ S1 confirmed, keep RETURN. Failure ⇒ diff the captured chain
   vs `~/android/esim_6a88_reference/apdus_mss63.txt` (structure only) — readout: block-1's true SW,
   whether APDU-2 was P2=01 or GET RESPONSE, which block draws 6A88.
2. **B2 — if B1 failed:** developer options → es10x **MSS=250** (slice 1 becomes a single
   un-chained block), retry once. Success ⇒ chain-handling fault below the app (S2). Failure ⇒ S3.
3. **B3 — restore:** procedure_bytes back to SKIP (unless B1 proved RETURN), verbose off, MSS 63.
4. **B4 — escalations (only with traces in hand):** (a) one-line `UiccPort.java:258` isEs10→true +
   frameworks rebuild; (b) optional OMAPI-for-embedded transport in OpenEUICC
   (`PrivilegedEuiccChannelFactory.kt:27` try OMAPI before TelephonyManager + fix the JNI
   exception-swallowing at `lpac-jni/interface-wrapper.h:13-17`) — a DIFFERENTIAL (bypasses
   qcril/framework framing), not a repair of something broken.
   CAUTION: each retry re-calls ES9+ getBoundProfilePackage and may decrement the SM-DP+ retry
   counter for this matchingId; Fi support can reissue the QR if exhausted.

**Device constants:** EID 89043051202509096225006453705212; eUICC = slot 1 port 0, ISD-R channel 1
(standard AID), MEP NONE. Artifacts: `~/android/{esim_diag.txt,esim_diag2.txt,esim_retry_logcat.txt}`
+ `~/android/esim_6a88_reference/`. Key code coords: `PreferenceUtils.kt:90,103`,
`TelephonyManagerApduInterface.kt:56-64`, `PrivilegedEuiccChannelFactory.kt:21-27`,
`UiccPort.java:241,258`, `es10b.c:288-398`, `euicc.c:18-110`.

**When to revisit:** **HIGH PRIORITY — B1 is user-runnable NOW** (works on the current prebuilt-kernel
build; no dependency on the source kernel landing). Full investigation record in agent memory
`project_jun09_esim_6a88_investigation`.

---

## Fork + commit the OEM WLAN modules repo to jm2 (cnss2 byte-reversed-MAC fix)

**Surfaced:** 2026-06-09 (Kleaf step-d implementation — Part C WLAN-DDK).

**Context:** The OEM Kleaf build compiles WLAN from the OEM tree at
`kernel-6.12/vendor/qcom/opensource/wlan/{platform,qcacld-3.0}` (NOT from the LineageOS
`sm8850-modules` tree — that's the parked Kbuild source). The WiFi fix (byte-reversed WLAN
MAC, in `platform/cnss2/qmi.c`, guarded by `OPLUS_FEATURE_WIFI_MAC`) was applied to the
**local** OEM tree to make the source-built `cnss2.ko` carry the fix (validated: builds against
`//soc-repo:canoe_perf_base_kernel`, vermagic matches, fix compiles). That patch is byte-identical
to the jm2 `sm8850-modules` copy at commit `21fae367` — but it currently lives ONLY in the local
synced OEM checkout, version-controlled nowhere. The OEM WLAN source belongs to the OnePlusOSS
`android_kernel_modules_and_devicetree_oneplus_sm8850` repo (branch
`oneplus/sm8850_b_16.0.0_oneplus_15`), synced read-only.

**Concrete tasks:**
1. Fork `OnePlus-SM8850-Development`/`android_kernel_modules_and_devicetree_oneplus_sm8850` (or the
   OnePlusOSS source) to `jm2`, push over SSH (`reference_jm2_forks_use_ssh`).
2. Point the OEM tree's `vendor/qcom/opensource/wlan` at the jm2 fork (local_manifest or remote swap),
   or just commit + push the single `cnss2/qmi.c` patch on the fork.
3. Commit the de-reverse fix (mirror jm2 `sm8850-modules` 21fae367; record the cross-link in
   `KLEAF_PIVOT.md`). Confirm a clean WLAN rebuild from the fork still yields matching vermagic.

**Rationale for deferring:** the fix is applied + validated locally; the source-built ROM (Part E)
can be produced and flashed from the current local state. Forking a large OEM repo + reworking the
manifest is reproducibility/hygiene work, best done once Part E confirms the fix works on hardware
(no point forking around a fix that hasn't booted yet).

**When to revisit:** right after Part E hardware verification confirms `wlan0` comes up with a
unicast MAC. Until then the local patch suffices for building. See
`KLEAF_WIREUP_PLAN.md` §"IMPLEMENTATION RESULTS — 2026-06-09".
