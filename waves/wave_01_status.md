# Wave 1 status — DFR mini-batch

**Date completed:** 2026-05-02
**Theme:** Foundational utility / first real wave (smaller than the planned
"all foundational utilities" scope; see Scope rationale below).
**Result:** 4 modules wired and passing validation, all 4 DFR entries in
modules.load now source-built rather than OEM-prebuilt.
**Source-built externals total:** 36 → 40 across this wave (incl. the
Phase 4 proof-point).

---

## Modules landed

| Module | Pattern | Sources | KMI clean | __versions | Verdict | Commit |
|---|---|---:|---:|---:|---|---|
| `oplus_bsp_dfr_keyevent_handler` | single-source, no ko_deps | 1 | 100% | 17 | pass | `38ec297d` (Phase 4 proof-point) |
| `oplus_bsp_dfr_dump_device_info` | single-source, 2 cross-subsystem ko_deps (cmdline_parser + projectinfo) | 1 | 84.6% | 26 | pass | `554246b6` |
| `oplus_bsp_dfr_dump_reason` | single-source, 1 within-wave ko_dep + 1 in-tree | 1 | 92.9% | 28 | pass | `554246b6` |
| `oplus_bsp_dfr_pmic_monitor` | multi-source bundle | 5 | 96.2% | 26 | pass | `554246b6` |

All four:
- vermagic match: `6.12.23-4k-g6fc93520fed4` (current Phase H kernel)
- CRC match rate: 100%
- Verdict: `pass` per `tools/jm2/kmod_validate.py`

## Validation evidence

```
$ tools/jm2/validate_module.sh \
    out/.../updates/oplus_bsp_dfr_dump_device_info.ko \
    out/.../updates/oplus_bsp_dfr_dump_reason.ko \
    out/.../updates/oplus_bsp_dfr_pmic_monitor.ko
... all 3 verdict=pass, exit=0
```

(Phase 4 proof-point validation logged separately in commit `38ec297d`.)

---

## Companion changes

- **device tree** (`device/oneplus/sm8850-common/BoardConfigCommon.mk`):
  4 lines appended to `TARGET_KERNEL_EXT_MODULES` (one per new module).
  Two commits: `b532a34` (Phase 4 keyevent_handler) and `047a8dd`
  (Wave 1 DFR three).
- **modules tree** files added: `Kbuild` per module + per-module
  `Makefile` rewritten from in-tree-style to external-module-driver
  style. 7 files total (3 new Kbuild + 3 rewritten Makefile + 1
  WIRE_UP_RECIPE.md update).

---

## What was harder than expected

### 1. Cross-module name mapping is non-trivial

`oplus_bsp_dfr_dump_device_info` declared `//vendor/oplus/kernel/boot:oplusboot`
as a ko_dep in BUILD.bazel. Naive interpretation: there's an
`oplusboot.ko` to depend on. Reality: `oplusboot.c` is one of seven
.c files bundled into `oplus_bsp_cmdline_parser.ko`. The right
KBUILD_EXTRA_SYMBOLS path was `boot/cmdline_parser/Module.symvers`,
not `boot/oplusboot/Module.symvers`.

**Cost:** one wasted iteration. The first build errored on
`serial_no` undefined (defined in oplusboot.c, exported by
cmdline_parser bundle). Diagnosis took ~5 minutes; the fix was
adding the right path.

**Recipe addition:** Step 1 now explicitly says "the symvers path is
the BUNDLE's, not the original Bazel target's" with lookup steps.

### 2. The "skip a ko_dep based on judgment" anti-pattern

Same module: I dismissed the `oplusboot` ko_dep as "not in
modules.load, no consumed symbols, skip." That was wrong — the
symbols WERE consumed via `<soc/oplus/system/oplus_project.h>`
which transparently surfaces oplusboot.c's `extern char serial_no[]`.

The recipe's existing rule ("extra deps are harmless, missing deps
cause modpost errors") was right; the override was wasteful.

**Recipe addition:** "translate every `ko_deps` entry; trust the
BUILD.bazel" promoted from advisory to imperative.

### 3. Multi-source `$(MODULE)-objs` worked exactly as documented

`pmic_monitor` (5 .c files via Bazel `conditional_srcs`) wired
cleanly with the documented `$(MODULE)-objs := s1.o s2.o ...`
pattern. No surprises. Multi-source pattern is robust.

---

## Phase 4.5 / mid-wave recipe refinements

Wave 1 surfaced gaps that motivated three recipe-side updates,
landed mid-wave (commit `1728f799`):

- **Step 5/6 reordered:** static check (`bazel_kbuild_diff.py`) now
  runs BEFORE the kernel build, not after. Catches missing-source /
  CONFIG-name typos in seconds rather than 1–4 min rebuild cycles.
- **Step 3.5 added** (Kconfig authoring): three patterns
  (module-local Kconfig / defconfig fragment / Bazel-local_defines-only)
  for where Kconfig stanzas should land, vs the original recipe's
  silence on the topic.
- **Step 7 wrapper** (`tools/jm2/validate_module.sh`): replaces the
  hand-typed `find -printf | tr` invocation in the original recipe
  with a single command. Auto-discovers all symvers files.
- **Step 8 added** (OEM-fallback verification): explicit step to
  rebuild with `BOARD_PREBUILT_KERNEL=true` style fallback after each
  wave so we don't silently break the recovery path.

Plus the EXPORT_SYMBOL_HANDLING.md (new file, commit `1728f799`,
refined in `74b0070`) — wasn't actually exercised in Wave 1 (none of
these 4 modules needed kernel-side EXPORT additions), but the doc is
in place for waves that will.

---

## Scope rationale: 4 modules instead of "all foundational utilities"

The plan's wave 1 description was "small utility modules that other
modules link against — some of vendor/oplus/kernel/system/ and the
oplus_cfg-style modules. These have few dependencies and unblock
everything else."

In practice:
- `vendor/oplus/kernel/system/` doesn't exist as a directory in our
  tree (sm8850 layout differs slightly from what the plan author
  remembered).
- The DFR modules in modules.load (4 entries — keyevent_handler,
  dump_device_info, dump_reason, pmic_monitor) are a coherent
  diagnostic-framework mini-batch with internal cross-deps and
  one cross-subsystem dep (cmdline_parser). They make a good
  first wave because they exercise:
  - Single-source case (3 modules)
  - Multi-source bundle case (1 module)
  - Within-wave cross-module dep (dump_reason → dump_device_info)
  - Cross-subsystem dep into already-built externals
    (dump_device_info → cmdline_parser, projectinfo)
  - Bazel `local_defines` → ccflags-y -D translation (dump_reason)

Splitting into "Wave 1 = 4 DFR modules" rather than "Wave 1 =
all foundational utilities = unknown count" gives a defined,
verifiable wave-completion gate without committing to scope we
can't accurately size yet.

The remaining "foundational utility" candidates (oplus_cfg, oplus
inject helpers, etc.) are deferred to a later wave. None block MVB
because they're not in modules.load.

---

## Plan adjustments for Wave 2

### Wave 2 chosen content

Per the plan, Wave 2 was "in-tree drivers from sm8850 source — pinctrl,
clock, regulator drivers from `kernel/oneplus/sm8850/drivers/`." On
inspection, the canoe clock controllers (`gcc-canoe`, `dispcc-canoe`,
`camcc-canoe`) source EXISTS in `drivers/clk/qcom/` but NONE of them
are in `modules.load`. They're loaded via DT compatible match by ABL,
not by our init.rc modprobe sequence. So they're stretch-goal scope
(Phase 7+), not MVB-blocking.

Real Wave 2 content (driven by what's in modules.load, not the plan's
abstract category): 213 OEM-prebuilt-only modules grouped roughly:

| Category | Count | Notes |
|---|---:|---|
| oplus audio / qcom audio | ~30 | Many `_dlkm` suffix; existing audio-kernel external builds the parent dir |
| oplus_bsp_* (touch, fingerprint, haptic) | 28 | Mix of single-source and multi-source |
| oplus_network_* | 4 | Self-contained likely |
| oplus_other (esim, audio extensions) | 21 | |
| qcom_qti (regulators, glink, etc.) | 21 | |
| WLAN platform stack (cnss2 + qca_cld3) | 7 | Hairy, dedicated wave 5 |
| msm_* (kgsl, eva, video) | 11 | Wave 6 / 7 |
| Bluetooth platform | 4 | Wave 7 |
| Other | 117 | Mostly audio_*, adsp_* under qcom audio-kernel |

### First Wave-2 candidate: oplus_bsp_haptic_feedback

- Source: `vendor/oplus/kernel/vibrator/haptic_feedback/haptic_feedback.c`
  (796 lines, single source)
- Bazel ko_deps: 1 entry (`oplus_bsp_dft_kernel_fb` from
  `vendor/oplus/kernel/dft/`)
- Implication: Wave 2 starts with a chained-dep discovery — the
  `dft` subsystem must wire-up first to provide the symvers
  haptic_feedback consumes
- This is genuinely the wave-2-pattern stress test Opus Web warned
  about: each new subsystem touched expands the wire-up tree

### Anticipated Wave 2 effort

- Each subsystem-first module: 30–60 min of investigation + 1 build
  iteration
- Subsequent modules in the same subsystem: 5–15 min each
- Total Wave 2 estimate: ~5–10 modules / day with the recipe in its
  current state
- 213 modules / 5–10 per day = 3–6 weeks for full Phase 5 wire-up,
  consistent with the plan's "1–2 weeks if priors hold, 3–6 weeks if
  K3 is larger than expected" estimate

---

## Wave 1 closeout verification (2026-05-02)

Per IMPLEMENTATION_PLAN.md §5.4, Wave 1 needed an "MVB ROM that
passes Phase 2 validators end-to-end" before being marked complete.
Initially missed; closed out with this section.

### Brunch closeout

`~/android/iter_brunch.sh wave1_closeout` (4m39s, exit 0):
- Fresh ROM zip: `lineage-23.2-20260502-UNOFFICIAL-infiniti.zip` (2.3 GB)
- vendor_dlkm.img: 73 MB
- All 4 wave-1 .ko files installed in `vendor_dlkm/lib/modules/`
  with vermagic `6.12.23-4k-g6fc93520fed4` (source-built, not OEM
  prebuilt — overwrite race won correctly)
- validate_module.sh on all 4 installed modules: verdict=pass

### Release-candidate tags landed

Per plan §5.4 ("release-candidate tag on each jm2 fork"):
- `kernel/oneplus/sm8850` → `phase-h-wave-1`
- `kernel/oneplus/sm8850-modules` → `wave-1`
- `device/oneplus/sm8850-common` → `wave-1`

(Tags placed correctly after one fix-up — initial attempt put both
on kernel repo.)

### Clock-controller MVB-blocker discovered (Opus Web feedback)

External review flagged that the wave_01_status.md "Wave 2 chosen
content" section deferred canoe clock controllers as Phase 7+ stretch
without verifying they're available somewhere in our build. The
verification (Opus Web's recommended "option (a) vs (b)
disambiguation"):

- `.config` for `CONFIG_*GCC*CANOE` / `CONFIG_*DISPCC*CANOE`: NONE.
  No clock-controller for canoe is built into our vmlinux.
- `drivers/clk/qcom/Makefile` `canoe` entries: NONE. Source files
  (`gcc-canoe.c`, `dispcc-canoe.c`, `camcc-canoe.c`) exist as
  orphans — present in tree, never compiled.
- `vendor_dlkm/lib/modules/gcc-canoe.ko` exists but vermagic is
  `6.12.23-android16-5-o-4k` (OEM prebuilt) — won't load against
  our source kernel.
- `modules.list.msm.canoe` (vendor_ramdisk early-init list): NO
  clock-controller references.

**Implication:** our source kernel has zero canoe clock code. Source
not compiled, modules can't load. Phase 6 hardware test would fail
at clock-tree initialization. **MVB-blocking.**

**Action:** promote canoe clock controllers from "Phase 7+ stretch"
to **Wave 2 first priority**. Concretely needed:
- `drivers/clk/qcom/Kconfig` Kconfig stanzas for `SM_GCC_CANOE`,
  `SM_DISPCC_CANOE`, `SM_CAMCC_CANOE` (and possibly TCSRCC, VIDEOCC,
  GPUCC, EVACC, CAMBISTMCLKCC — verify which are required by canoe
  DT)
- `drivers/clk/qcom/Makefile` entries:
  `obj-$(CONFIG_SM_*_CANOE) += *-canoe.o`
- `lineage_genksyms_workaround.config` (or similar fragment):
  `CONFIG_SM_*_CANOE=m` for each
- These will likely surface EXPORT_SYMBOL gaps (clock-controller
  internals reference vendor-internal helper functions). First
  exercise of EXPORT_SYMBOL_HANDLING.md ladder.

This recasting of Wave 2 priorities is what
`waves/wave_02_status.md` will document when that wave starts.

## Wave 2 calibration notes (Opus Web feedback, 2026-05-02)

The original wave_02 estimate ("5–10 modules / day") in this doc
was likely optimistic. Opus Web's calibration:

- **K1/K2 vs K3 rates will diverge.** Wave 1's DFR modules were
  K1/K2 (lowest cleanliness 84.6%). When Wave 2 hits the first K3
  module (anything below 80%), expect 1–3 EXPORT_SYMBOL additions
  per module, each requiring its own commit per
  EXPORT_SYMBOL_HANDLING.md discipline. That drops K3 rate to
  ~2–4 modules / day with EXPORT bookkeeping.
- **Chained-dep discovery inflates per-module count by 30–50%.**
  When haptic_feedback's `dft` ko_dep turns out to depend on
  something in oplus/system that depends on something in
  qcom/securemsm, Wave 2 expanded scope by 3 modules to land 1
  that was originally in modules.load. This is the right work,
  but the per-module-of-original-scope rate inflates.
- **Track K1/K2 vs K3 rates separately.** Don't average; the
  distribution matters for projection.
- **Each subsystem reset.** DFR was internally coherent (one set of
  idioms). Wave 2's spread (audio / oplus_bsp_* / qcom_qti / network)
  means the recipe likely needs subsystem-specific addenda. The
  first audio module will be hard; the second easier; first
  oplus_bsp_touchpanel starts the cycle over.

The 3–6 week estimate from IMPLEMENTATION_PLAN.md §16 still applies
but the work will be lumpy, not uniform. Plan accordingly.

## Open follow-ups

- **Push the 11 unpushed jm2 commits.** Latest per fork:
  - `kernel/oneplus/sm8850`: `6fc93520fed4` (Phase H), tag
    `phase-h-wave-1`
  - `kernel/oneplus/sm8850-modules`: `52fca02` (DEFERRED_FOLLOWUPS),
    tag `wave-1`
  - `device/oneplus/sm8850-common`: `047a8dd` (wave 1 device wiring),
    tag `wave-1`
  - 11 commits + 3 tags awaiting push (Opus Web flagged accumulating
    risk; push after every wave at minimum).
- **EXPORT_SYMBOL ladder hasn't been exercised yet.** Wave 1 needed
  zero kernel-side exports. First Wave-2 K3 module will be the real
  test. Watch for: defaulting to `EXPORT_SYMBOL_GPL` and per-export
  separate commits before the wire-up commit.
- **OEM-kernel `BOARD_PREBUILT_KERNEL=true` switch wiring.**
  Documented in DEFERRED_FOLLOWUPS.md (item 1). User-confirmed
  deferred. Brunch closeout exercised the BOARD_VENDOR_KERNEL_MODULES
  wildcard path (which IS structurally working alongside source-built
  modules), so the structural fallback is intact even without the
  dedicated switch. Revisit before Phase 6.
- **Recipe stress-test still incomplete.** Wave 1 didn't exercise:
  - Kconfig authoring path (Step 3.5)
  - EXPORT_SYMBOL ladder (no missing exports surfaced)
  - In-tree-driver wire-up (different from external-module pattern —
    Wave 2 clock controllers will be the first)
  - Cross-subsystem chained ko_deps
  - WLAN-tier complexity

## Wave 1 marked COMPLETE (2026-05-02)

All Plan §5.4 deliverables now satisfied:
- ✅ jm2 commits across 3 forks
- ✅ wave_01_status.md (this doc)
- ✅ MVB ROM passes Phase 2 validators end-to-end (brunch closeout)
- ✅ Release-candidate tags on each jm2 fork

Per Plan §13 ("Per-wave: write status doc BEFORE the wave is marked
complete"), this discipline lapse is noted. Going forward: re-read
the relevant plan section before claiming any phase/wave done.
