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

## Open follow-ups

- **Push the unpushed jm2 commits.** Latest commits per fork:
  - `kernel/oneplus/sm8850`: `6fc93520fed4` (Phase H — KMI-strict)
  - `kernel/oneplus/sm8850-modules`: `554246b6` (Phase 5 wave 1 DFR)
  - `device/oneplus/sm8850-common`: `047a8dd` (wave 1 device wiring)
  - 9 commits total across these three forks awaiting push.
- **Recipe stress-test still incomplete.** Wave 1 didn't exercise:
  - Kconfig authoring path (Step 3.5)
  - EXPORT_SYMBOL ladder (no missing exports surfaced)
  - Cross-subsystem chained ko_deps (dft → haptic_feedback → haptic)
  - WLAN-tier complexity
  These will surface in Wave 2+. Recipe will likely need further
  refinement once they do.
- **OEM-fallback verification step (Step 8) NOT yet exercised.** No
  rebuild of the OEM-kernel-prebuilt fallback path was run after this
  wave. Should be done before Wave 2 starts to confirm Phase H +
  Wave 1 didn't regress the fallback.
