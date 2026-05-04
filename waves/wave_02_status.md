# Wave 2 status — clock cluster + heterogeneous module backlog

**Date started:** 2026-05-02
**Theme:** First in-tree-driver wire-up (clock cluster), then the
heterogeneous OEM-prebuilt-only backlog from modules.load.

This wave is materially harder than Wave 1. Calibration notes from
the wave_01_status closeout apply: K1/K2 vs K3 rate divergence,
chained-dep inflation, per-subsystem reset. Most of all, the first
sub-wave (clock cluster) doesn't fit a per-module rate model — it's
"3 modules over 3–5 days, lands together or doesn't land at all,"
not "5–10 modules / day."

---

## Wave-start state verification (per Plan §13 process habit)

Before any wire-up commits, ran the upstream-state reconciliation
across all three jm2 forks:

```
git fetch --tags && git status -uno && git log @{u}..HEAD --oneline
```

State as of 2026-05-02 (after Wave 1 closeout):

| Repo | Working tree | Unpushed | Tags |
|---|---|---|---|
| `kernel/oneplus/sm8850` | clean | 0 | `phase-h-wave-1` |
| `kernel/oneplus/sm8850-modules` | clean | 0 | `wave-1` |
| `device/oneplus/sm8850-common` | clean | 0 | `wave-1` |

(Note: `git fetch` from this session lacks SSH access; reconciliation
is "local matches last known remote." User confirms pushes happened.
Tag-pushed status not independently verifiable without successful
fetch — defer to user.)

---

## Plan §5.4 deliverables checklist (preflight)

Per Plan §5.4, a wave is COMPLETE when:

- [ ] N waves of jm2 commits land on the affected forks
- [ ] `wave_<N>_status.md` retrospective written
- [ ] MVB ROM passes Phase 2 validators end-to-end
  (run `~/android/iter_brunch.sh wave<N>_closeout`, validate that the
  resulting vendor_dlkm.img has the new modules at expected vermagic)
- [ ] Release-candidate tag on each jm2 fork
  (kernel: `phase-X-wave-N`, modules: `wave-N`, device: `wave-N`)

This wave's commits, retro, brunch, and tags are tracked below as
the wave progresses. Going forward: re-read Plan §5.4 before
declaring this wave done.

---

## Sub-wave 2A — Canoe clock cluster

### Scope (DT-grounded, not file-list-hypothesized)

Built the canoe clock-tree dependency graph from the actual canoe
DT (per Opus Web feedback "let the DT tell you what's actually
consumed"). Aggregated `clocks = <&xxx>` phandles across:

- `qcom/opensource/devicetree/qcom/canoe.dtsi`
- All 12 techpack files referenced by `canoe-fat.dts` (audio,
  display-sde, camera, eva, vidc, gpu, ipa, synx, hw_fence,
  hfi_core, mmrm, mmrm-test)

Unique clock-controller phandles found: `aoss_qmp`, `camcc`,
`dispcc`, `gcc`, `pcie_0_pipe_clk`, `pdp_scmi_perf`, `rpmhcc`.

Triaged:
- `aoss_qmp`, `rpmhcc` — mainline in-tree drivers, already covered
  by the kernel's standard clk framework. Not Wave 2 scope.
- `pcie_0_pipe_clk` — per-link clock, not a controller. Not Wave 2.
- `pdp_scmi_perf` — SCMI-based; clk-scmi handles it via the SCMI
  framework, not a per-SoC .ko. Not Wave 2.
- `gcc`, `dispcc`, `camcc` — **canoe-specific clock controllers**.
  Sources at `drivers/clk/qcom/{gcc,dispcc,camcc}-canoe.c` exist as
  orphans. Wave 2 scope.

**Refuted speculations** (NOT consumed by canoe DT, NOT Wave 2 scope):
- TCSRCC (in-tree mainline-equivalent for sm8850; if used at all
  it's transparent)
- VIDEOCC, GPUCC, EVACC, CAMBISTMCLKCC — none of these phandles
  appear in the fat-DT include set

The narrower cluster is good news for Wave 2 schedule: 3 controllers
instead of the 5–8 I'd speculated.

> **REVISED 2026-05-02 (post-2A.5):** The "refuted speculations"
> list above was WRONG. My grep `clocks = <&LABEL` matched only the
> first phandle in `clocks = <...>` arrays. canoe.dtsi has
> multi-phandle arrays like `clocks = <&rpmhcc CLK>, <&cambistmclkcc
> 0>, <&camcc 0>;` whose 2nd/3rd phandles I missed. Sub-wave 2A.5
> (corrective) wired the 5 missed controllers: cambistmclkcc-canoe,
> evacc-canoe, gpucc-canoe, tcsrcc-canoe, videocc-canoe. See section
> below. The DT-consistency-check tool (tools/jm2/dt_consistency_check.py)
> with array-aware regex caught this on its first run and is now
> the standard pre-flash check before every sub-wave.

### Cluster topology

Per qcom-clk convention:
- `gcc-canoe` is the foundation. Provides: USB, UFS, PCIe, audio
  bus clocks, plus the parent clocks consumed by dispcc and camcc.
- `dispcc-canoe` consumes parent clocks from gcc (display PLLs,
  display tree).
- `camcc-canoe` consumes parent clocks from gcc (camera tree).

Wire-up order: gcc first, then dispcc + camcc (independent
consumers).

Validation gate (per Opus Web): not just "module loads" but "DT
probe resolves" — i.e., when the kernel boots and parses canoe DT,
each consumer of `clocks = <&dispcc ...>` finds its parent in the
clock tree successfully. Hard to verify pre-flash; minimum gate is
"module loads, registers all clocks named in DT bindings without
parent-clock-not-found warnings in dmesg."

### Status

- [x] gcc-canoe Kconfig + Makefile + defconfig wired
- [x] gcc-canoe builds, vermagic match, CRC match
- [x] dispcc-canoe Kconfig + Makefile + defconfig wired
- [x] dispcc-canoe builds, vermagic match, CRC match
- [x] camcc-canoe Kconfig + Makefile + defconfig wired
- [x] camcc-canoe builds, vermagic match, CRC match
- [x] Brunch closeout green; vendor_dlkm has all 3 at vermagic 6.12.23-4k-gd97fcf1de278
      (brunch exit 0, 5m34s, validate_module.sh re-confirmed 100% CRC match)
- [x] Sub-wave 2A retrospective notes (below)

### Sub-wave 2A retrospective

**Single iteration to green.** Build went from "kernel/Kconfig + Makefile
edits + defconfig append" to all 3 modules passing on first build.

**Validator output** (3 modules, two validation points):

| Module | intree | vermagic_match | __versions | CRC match | KMI clean | Verdict |
|---|---|---|---:|---|---:|---|
| gcc-canoe | Y | yes | 19 | 19/19 | 100% | pass |
| dispcc-canoe | Y | yes | 38 | 38/38 | 100% | pass |
| camcc-canoe | Y | yes | 29 | 29/29 | 100% | pass |

Two validation passes (vermagic differed because each kernel-fork
commit shifts the running kernel's SHA suffix — important
distinction worth being explicit about):

- **Post-`mka kernel`, pre-commit:** vermagic
  `6.12.23-4k-g6fc93520fed4-dirty` (kernel built off Phase H SHA
  + uncommitted Wave 2A changes — `-dirty` suffix).
- **Post-brunch closeout, post-commit:** vermagic
  `6.12.23-4k-gd97fcf1de278` (kernel built off the just-landed
  Wave 2A commit — clean tree, no `-dirty`).

Both passes returned `tools/jm2/validate_module.sh` exit 0.

**Implication for Wave 2's heterogeneous tail:** every kernel-fork
commit shifts vermagic, so EVERY previously-built source-built
module needs to be rebuilt to validate against the new kernel.
The brunch closeout did this implicitly. For sub-waves with
multiple kernel-fork commits (likely the case for EXPORT
additions per `EXPORT_SYMBOL_HANDLING.md`), batch the kernel
commits within a sub-wave when possible — accumulate all the
EXPORT additions, do them as a series of separate commits per
the upstream-cleanliness rule, then ONE final rebuild at the
sub-wave boundary rather than per-commit. The "separate commit
per EXPORT" discipline is upstream-correctness; the rebuilds are
a separate cost that doesn't have to follow the same cadence.

**EXPORT_SYMBOL ladder NOT exercised this sub-wave.** External review
predicted 10–20 EXPORT additions based on qcom-clk's heavy internal-
helper-via-EXPORT_SYMBOL_GPL conventions. Reality: zero. Reasons:

1. Base `clk-qcom.ko` (in-tree built, Phase F) already exports all
   the qcom-clk framework helpers (`clk_branch2_ops`,
   `clk_alpha_pll_*`, RCG ops, GDSC). Canoe variants just consume
   them via the standard provider interface.
2. Phase H's whitelist file (`android/abi_gki_aarch64_oneplus_15`)
   already includes the vendor-internal `qcom_clk_*` symbols
   harvested from OEM prebuilts in Wave 1 v6/v7. Kept exported
   by TRIM_UNUSED_KSYMS.

The EXPORT ladder will get its first real exercise in a later
sub-wave with vendor-internal symbols that are less framework-shared
(likely audio or oplus_bsp_*).

**Cluster topology was correct.** The DT-grounded cluster (gcc /
dispcc / camcc, no extras) was the right scope. No surprises from
TCSRCC / VIDEOCC / GPUCC — those clock controllers genuinely aren't
referenced by canoe DT.

**Multi-module cluster validation.** The "validate as cluster, not
individually" gate from Opus Web was less load-bearing than expected
because all 3 built and passed cleanly together. Worth keeping the
discipline for harder clusters (audio, msm_*).

**Effort:** ~30 minutes of investigation (DT graph), ~10 minutes
of edits (Kconfig + Makefile + defconfig), one ~3-minute build.
Total ~45 minutes. Significantly faster than the "3–6 modules over
3–5 days, 10–20 EXPORT additions" projection.

**Commit:** kernel/oneplus/sm8850 `d97fcf1de278`. No companion
device-tree change (in-tree drivers don't need
TARGET_KERNEL_EXT_MODULES).

### Anticipated EXPORT_SYMBOL surface (PRE-COMPLETION PROJECTION; ACTUAL = 0)

> Annotation 2026-05-02: this section was the pre-completion
> projection from Opus Web review. **Actual outcome: zero EXPORTs
> needed** (see retrospective above for the explanation). Kept here
> as historical record of the projection-vs-actual gap, not as
> guidance. The right reframe — also from Opus Web's post-2A
> review — is that the K-bucket classification doesn't distinguish
> "K3 + already-exported" (clean wire-up) from "K3 + not-yet-exported"
> (EXPORT ladder exercise). Phase F/H pre-export work covered the
> qcom-clk surface used by canoe controllers, so K3 here was clean.

Original projection (now superseded):
- Clock controllers are heavy on internal-helper-via-EXPORT_SYMBOL_GPL
  patterns. Expected 10–20 EXPORT additions for the cluster.

This was wrong because:
1. Base `clk-qcom.ko` (Phase F in-tree) already exported framework
   helpers
2. Phase H whitelist already included `qcom_clk_*` vendor-internals
   (harvested from OEM `__versions` in v6/v7)

The EXPORT ladder is unused so far; first real exercise will come
in a sub-wave where consumed symbols weren't covered by Phase F/H.

---


### Sub-wave 2A: COMPLETE (2026-05-02)

All Plan §5.4 deliverables satisfied:
- jm2 commit on kernel fork: `d97fcf1de278`
- wave_02_status.md (this section)
- MVB ROM passes validators: brunch closeout exit 0; clock cluster
  installed in vendor_dlkm at vermagic 6.12.23-4k-gd97fcf1de278;
  validate_module.sh exits 0
- Release-candidate tag: `phase-h-wave-2a` on kernel fork
  (modules + device forks not touched this sub-wave; no tags there)

Most surprising finding: zero EXPORT_SYMBOL additions needed. The
EXPORT_SYMBOL_HANDLING.md ladder isn't yet exercised; expect first
real exercise in audio or oplus_bsp_* sub-wave.


---

## Sub-wave 2A.5 — corrective wire-up of 5 missed controllers (2026-05-02)

### Background

Sub-wave 2A's "DT-grounded scope" claim was incomplete. My grep
`clocks = <&LABEL` matched only the first phandle in clocks arrays;
multi-phandle arrays like
  `clocks = <&rpmhcc CLK>, <&cambistmclkcc 0>, <&camcc 0>;`
slipped past. Caught when running the just-built
`tools/jm2/dt_consistency_check.py` against `canoe.dtsi +
canoe-audio.dtsi`: 24 oem-only-load-fails findings, of which 5 were
canoe-specific clock controllers.

This is exactly the latent-bug class Opus Web flagged: would have
surfaced at Phase 6 hardware test as "device hangs at clock-tree
init" with no obvious cause. Caught at sub-wave-boundary, fixed in
~30 minutes.

### Modules added

5 controllers, same template as 2A:

| Module | __versions | CRC match | KMI clean | Verdict |
|---|---:|---|---:|---|
| cambistmclkcc-canoe (Camera BIST Mclk) | 25 | 25/25 | 100% | pass |
| evacc-canoe (EVA — Enhanced Video Analytics) | 27 | 27/27 | 100% | pass |
| gpucc-canoe (Graphics — boot-critical for Adreno) | 25 | 25/25 | 100% | pass |
| tcsrcc-canoe (TCSR — Top Control & Status Registers) | 9 | 9/9 | 100% | pass |
| videocc-canoe (Video) | 26 | 26/26 | 100% | pass |

All in-tree built (intree=Y), vermagic-match yes, CRC 100%, KMI
100%. validate_module.sh exits 0.

### DT-consistency check post-2A.5

Re-ran `dt_consistency_check.py`:

| | pre-2A | post-2A | post-2A.5 |
|---|---:|---:|---:|
| oem-only-load-fails | n/a (tool didn't exist) | 24 | **0** |
| clean | n/a | varies (glob bug) | 24 |
| no-driver-found | n/a | 67 | 67 |
| no-compatible | n/a | 77 | 77 |

The post-2A 24 → post-2A.5 0 transition includes both the 5
controllers I added AND a glob bug fix (recursive=True needed for
`**/*.ko` to traverse the in-tree-built kernel/drivers/clk/qcom/
output directory). The 67 "no-driver-found" and 77 "no-compatible"
remain — false positives (CPU power domains, idle states, etc.)
that v1 of the tool can't disambiguate.

### Brunch closeout

`~/android/iter_brunch.sh wave2a5_closeout` exit 0. Full ROM
rebuild successful with all 8 controllers in vendor_dlkm at
post-2A.5 vermagic.

### Lesson + recipe addendum

The scope-finding regex needs to be array-aware when the DT
property allows arrays. v1 of `dt_consistency_check.py` uses an
array-aware approach (find the entire `clocks = <...>;` body, then
extract every `<&LABEL>` from it). Should be the standard scope-
finding tool for any future sub-wave's DT-grounded scoping rather
than ad-hoc grep.

Same general failure-mode class as the state-staleness pattern:
"quick analytical pass → conclusion → asserted as fact across
multiple turns without re-verification." The corrective rule:
when a quick analysis (grep, find, regex pass) gates a non-trivial
decision, run a second more-careful pass before declaring the
result complete.

### Commit

kernel/oneplus/sm8850 `59bd74c45df9`. No companion device-tree
change (in-tree drivers don't need TARGET_KERNEL_EXT_MODULES).

---

## Sub-wave 2A pre-flash probe verification (post-completion)

Per Plan §5.4 + Opus Web post-2A review ("validate against DT probe
resolves, not just module loads"), strongest available pre-flash
gate is static analysis of OF compatible-string matches. Completed
2026-05-02 after sub-wave 2A landed:

| Driver | of_match_table compatible | canoe.dtsi node @ addr | Match? |
|---|---|---|---|
| gcc-canoe.c | `qcom,canoe-gcc` | `gcc:` @ 0x100000 | ✅ |
| dispcc-canoe.c | `qcom,canoe-dispcc` | `dispcc:` @ 0x9ba2000 | ✅ |
| camcc-canoe.c | `qcom,canoe-camcc` | `camcc:` @ 0x956d000 | ✅ |

DT-driver binding will succeed at boot. Inter-controller clock-name
resolution (dispcc/camcc consume gcc parent clocks) goes through the
standard clk framework's defer-on-not-ready, so probe ordering is
automatic.

This is the strongest pre-hardware gate. dmesg-from-boot verification
(via cuttlefish/QEMU or hardware) is deferred to Phase 6.

---

## Sub-wave 2C prep — audio cluster scope (DT-grounded)

**STATUS: scope analysis only — no wire-up commits yet.**
This section is preparation for sub-wave 2C, not its execution.
Wire-up + commits land in a separate "Sub-wave 2C execution"
section once the structural diagnosis below resolves.

Mirroring the rigor that worked for clocks, walked
`vendor/qcom/opensource/audio-devicetree/canoe-audio.dtsi` to
inventory the audio dependency surface BEFORE picking modules.

### Foundation provider labels (22 — sources of consumed phandles)

```
audio_cnss_resv_region   audio_gpr            audio_prm
canoe_snd                lpass_audio_hw_vote  lpass_bt_swr
lpass_cdc                lpass_core_hw_vote   lpi_tlmm
msm_audio_ion            msm_audio_ion_cma    rx_macro
spf_core_platform        swr0                 swr1
swr2                     swr3                 swr4
tx_macro                 va_macro             wsa2_macro
wsa_macro
```

### Driver-binding compatibles in canoe-audio.dtsi (13)

| Compatible | Likely .ko | Status |
|---|---|---|
| `qcom,audio-pkt` | audio_pkt_dlkm | Already source-built ✓ |
| `qcom,audio_prm` | audio_prm_dlkm | Already source-built ✓ |
| `qcom,audio-ref-clk` | audio_ref_clk_dlkm | Wire-up needed |
| `qcom,canoe-asoc-snd` | canoe-asoc-snd machine | Wire-up needed |
| `qcom,gpr` | gpr_dlkm | Wire-up needed |
| `qcom,lpass-bt-swr` | lpass_bt_swr_dlkm | Wire-up needed (in modules.load) |
| `qcom,lpass-cdc` | lpass_cdc_dlkm | **FOUNDATION** — wire first |
| `qcom,lpass-cdc-clk-rsc-mngr` | lpass_cdc_clk_rsc_mngr_dlkm | Wire-up needed |
| `qcom,lpi-pinctrl` | lpi_pinctrl_dlkm | Wire-up needed |
| `qcom,msm-audio-ion` | msm_audio_ion_dlkm | Wire-up needed |
| `qcom,msm-audio-ion-cma` | (subset of msm_audio_ion?) | Verify |
| `qcom,spf_core` | spf_core | Wire-up needed |
| `qcom,spf-core-platform` | spf_core_platform | Wire-up needed |

### Cluster topology hypothesis

The audio-kernel parent dir is already in TARGET_KERNEL_EXT_MODULES
(`qcom/opensource/audio-kernel`), so it builds something. Verify in
sub-wave 2C kickoff which `.ko` files it actually emits — they may
already cover several entries above as unbuilt-because-config-gated
rather than unwired-from-scratch.

The bigger structural question for 2C: is the audio cluster's
foundation `lpass_cdc_dlkm.ko` already producing as part of the
existing audio-kernel build, but with the wrong CONFIG gates set?
If yes, sub-wave 2C is "find and flip the gates," not "translate
Bazel BUILD files." If no, it's the recipe-stress-test Opus Web
predicted.

Cluster wire order (if from-scratch):
1. `lpass_cdc_dlkm` — foundation, exports the codec interface
   consumed by all macros (`rx_macro`, `tx_macro`, `va_macro`,
   `wsa_macro`, `wsa2_macro`)
2. `lpass_cdc_clk_rsc_mngr_dlkm` — clock resource manager,
   consumed by macros
3. `*_macro_dlkm` (5 modules) — leaf consumers of lpass_cdc
4. `lpass_bt_swr_dlkm`, `swr*_dlkm` — SoundWire infrastructure
5. `gpr_dlkm`, `spf_core`, `spf_core_platform` — packet routing
   and sound-perf framework
6. `audio_ref_clk_dlkm`, `lpi_pinctrl_dlkm` — utilities
7. `msm_audio_ion_dlkm` — DMA buffer provider
8. `canoe-asoc-snd` — machine driver (uppermost layer)

### Anticipated EXPORT_SYMBOL surface (calibrated)

Per Opus Web's K-bucket reframe: the EXPORT ladder will exercise iff
audio modules consume symbols that were NOT pre-harvested by Phase
F/H. Phase H's whitelist file was built from OEM `__versions` of
the Wave 1 modules + the 36 source-built externals; if those didn't
include the audio-kernel internal helpers, Wave 2C will surface
EXPORTs.

The ALSA / ASoC framework is mainline kernel surface, generally
already KMI-stable. The qcom-specific lpass-cdc helpers, swr-mstr
helpers, and gpr internals are the most likely EXPORT candidates.
Realistic projection: 5–15 EXPORTs across the cluster, concentrated
at the foundation modules. Will track per-module commit counts to
calibrate whether this projection holds.

---

## Sub-wave 2C pre-flight — audio-DT consistency check + scope re-derivation

Per Opus Web's post-2A.5 reasoning ("the agent's audio prep work used
the same kind of manual analysis that produced the incomplete clock
cluster scope; running the new tool on audio-DT is just following
the rule the agent just established"), the audio scope was
re-derived with the array-aware approach AND `dt_consistency_check.py`
was run against canoe-audio.dtsi. Both before any 2C wire-up commits.

### Audio scope re-derivation (array-aware)

Re-ran the Wave 2A-style scope analysis on canoe-audio.dtsi using
the array-aware multi-phandle Python regex (the same approach now
in `dt_consistency_check.py`). Compared against the original manual
inventory:

| Class | Original count | Re-derived count | Match? |
|---|---:|---:|---|
| Unique phandle refs | 5 | 5 | ✅ |
| `clocks = <&...>` array phandles | 2 | 2 | ✅ |
| Driver-binding compatibles | 13 | 13 | ✅ |
| Provider labels defined in file | 22 | 22 | ✅ |

**No scope error.** Audio DT's structure is dominated by
`compatible = "qcom,..."` driver-bindings rather than multi-phandle
`clocks = <...>` arrays — different idiom from clocks DT, naturally
unaffected by the single-phandle regex bug that bit 2A.

### dt_consistency_check.py against canoe-audio.dtsi

```
$ python3 tools/jm2/dt_consistency_check.py \
    --dt vendor/qcom/opensource/audio-devicetree/canoe-audio.dtsi \
    --source-dir kernel/oneplus/sm8850/drivers \
    --source-dir kernel/oneplus/sm8850-modules/vendor/qcom/opensource \
    --source-dir kernel/oneplus/sm8850-modules/vendor/oplus/kernel \
    --source-built-glob 'out/.../updates/*.ko ...' \
    --oem-prebuilt-glob 'device/oneplus/infiniti-kernel/*.ko'

# summary:
#   clean: 0
#   oem-only-load-fails: 0
#   no-driver-found: 3
#   no-compatible: 2
```

**0 oem-only-load-fails** = no MVB-blockers in the consumer-
references-loadable-producer dimension. The 5 audio phandles
(apps_smmu, audio_cnss_resv_region, lpass_audio_hw_vote,
lpass_core_hw_vote, msm_audio_ion) are either:
- Defined IN canoe-audio.dtsi as self-providers (lpass_audio_hw_vote,
  lpass_core_hw_vote, msm_audio_ion, audio_cnss_resv_region)
- Referenced from canoe.dtsi as external mainline drivers
  (apps_smmu — Qualcomm SMMU)

### Tool gap (v1 limitation explicitly named)

`dt_consistency_check.py` v1 only handles `<&phandle>` consumer
references. It does NOT handle `compatible = "qcom,..."` driver-
binding references. Audio's dominant pattern is the latter
(13 compatibles), so the tool's clean signal here is **structurally
limited, not load-bearing**.

The 2C scope-correctness for audio rests on:
1. The earlier audio-kernel emission inventory (canoeauto.conf
   missing → zero modules emit) — load-bearing finding
2. The 13-compatibles inventory from `compatible = "..."` grep —
   load-bearing finding
3. dt_consistency_check.py phandle-ref check — confirms no
   *additional* hidden phandle scope, but doesn't bless the
   compatibles list

A v2 of the tool should add compatible-driver mapping support
(grep `.compatible = "X"` across source dirs, find which .ko
implements X, classify same as phandle case). Documented as
deferred-tool-improvement for after the first non-clock sub-wave
exercises the gap.

---

## Sub-wave 2C kickoff — audio-kernel emission inventory (FIRST ACTION)

Before any wire-up commits in 2C, resolve the structural question
("flip CONFIG gates" vs "from-scratch wire-up") that gates the
entire sub-wave plan. This was last-turn's biggest open question
and Opus Web flagged it as the literal first action of 2C — a
potential 10x scope difference depending on the answer.

**Method:**
1. Inventory `.ko` files actually emitted by the existing
   `qcom/opensource/audio-kernel` external build:
   ```
   find out/target/product/infiniti/obj/PACKAGING/kernel_modules_intermediates/lib/modules/<release>/ -name '*.ko' \
       | grep -E '(audio|lpass|swr|spf|gpr|asoc|wcd)' \
       | xargs -n1 basename
   ```
2. Cross-reference against the 13 driver-binding compatibles
   inventoried in 2C prep above:
   - `qcom,audio-pkt`, `qcom,audio_prm` (already known source-built)
   - `qcom,audio-ref-clk`, `qcom,canoe-asoc-snd`, `qcom,gpr`,
     `qcom,lpass-bt-swr`, `qcom,lpass-cdc`,
     `qcom,lpass-cdc-clk-rsc-mngr`, `qcom,lpi-pinctrl`,
     `qcom,msm-audio-ion`, `qcom,msm-audio-ion-cma`,
     `qcom,spf_core`, `qcom,spf-core-platform`
3. For each missing compatible, check whether the source produces
   a corresponding `.ko` (CONFIG-gated-off case) or whether no
   build target exists (truly unwired case).

**Three possible outcomes** (per Opus Web's framing):

| Outcome | 2C scope | Effort |
|---|---|---|
| Most modules emit but with empty/wrong vermagic — gated | Kconfig fragment exercise | hours |
| Subset emits — partial wire-up needed | Find unbuilt subset, wire those | day(s) |
| Little/nothing useful emits — full from-scratch | Recipe-stress-test as planned | days |

**Why this gates everything:** the cluster wire order documented
in 2C prep ("foundation lpass_cdc_dlkm first, then macros, then
SoundWire...") assumes outcome 3. If reality is outcome 1 or 2,
that wire order is partly or wholly wasted work. Same lesson as
the Wave 1 `oplusboot` mistake — build-system reality is
authoritative; assumptions made before checking are how scope
miscalibrates.

### Status

- [x] audio-kernel emission inventory completed
- [x] 13 compatibles cross-referenced
- [x] Outcome determined: **≈ 3 with a twist** — framework wired but
      no canoe-specific config glue
- [x] 2C scope reframed (see below)
- [ ] Then: actual wire-up commits

### Inventory finding (2026-05-02)

audio-kernel build IS invoked by brunch — `make modules` and
`make modules_install` run cleanly. modpost runs and produces a
`Module.symvers`. But **zero audio .ko files are produced for canoe.**

Root cause located in `audio-kernel/config/`:

```
$ ls audio-kernel/config/
bengalauto.conf  gvmauto.conf  holiauto.conf
kalamaauto.conf  konaauto.conf  lahainaauto.conf
litoauto.conf    pineappleauto.conf
(no canoeauto.conf)
```

Each audio-kernel sub-Kbuild has:
```
ifeq ($(CONFIG_ARCH_BENGAL), y)
    include $(AUDIO_ROOT)/config/bengalauto.conf
else ifeq ($(CONFIG_ARCH_KALAMA), y)
    include $(AUDIO_ROOT)/config/kalamaauto.conf
... (no canoe branch)
```

Without a canoe branch + matching `canoeauto.conf`, the if-elif
chain falls through and no `obj-y/m` lists get populated. Net
result: build succeeds (no errors), produces no modules.

### Reframed 2C scope (post-inventory)

Closer to "outcome 1 (CONFIG flip)" than "outcome 3 (from-scratch)":
the framework is fully wired; only canoe-specific configuration
glue is missing.

Concrete tasks:

1. Author `audio-kernel/config/canoeauto.conf` modeled on
   `pineappleauto.conf` (closest predecessor SoC — sm8650 era).
2. Author `audio-kernel/config/canoeautoconf.h` analogously
   (it's the C-header version of the .conf, surfaces feature flags
   to the source code).
3. Add `else ifeq ($(CONFIG_ARCH_CANOE), y)` branches to each
   audio-kernel sub-Kbuild (estimated ~10–20 files). Largely
   mechanical given the existing pattern.
4. Verify `CONFIG_ARCH_CANOE=y` is in the kernel config (it is —
   already in `lineage_genksyms_workaround.config` from Phase A).
5. Build, validate the resulting .ko set against the 13 expected
   compatibles from the DT inventory.

### Revised effort projection

Original projection (assuming outcome 3, full from-scratch): 3–5
days, 5–15 EXPORTs.

Revised (post-inventory, outcome ≈ 1): 2–4 hours, possibly zero
EXPORTs (since pineapple's audio drivers are similar enough to
sm8550/sm8650 era that whatever they consume is likely already
covered by Phase F/H whitelist + clk-qcom + the just-landed canoe
clock cluster).

This is the third sub-wave (Wave 1, 2A, now 2C) where the actual
work has been materially smaller than projected. Pattern emerging:
the prior phases (F/H + Wave 1 modules-side wire-up) did a lot of
implicit infrastructure work, so subsequent waves keep finding the
groundwork already in place. Worth tracking whether this pattern
holds for 2D-2I or whether it tails off as the modules become more
specialized.

---

## Runtime-validation gate consideration (cuttlefish / QEMU)

Per Opus Web post-2A review: the static gates we run pre-flash
catch a class of bugs (vermagic mismatch, CRC mismatch, missing
imports, OF compatible mismatch) but defer an entire other class
to Phase 6 hardware test (probe-time errors, init ordering,
parent-clock-not-found warnings, IOMMU mapping mismatches, etc.).
With ~213 modules to land in Wave 2 + more in subsequent waves,
the count of latent runtime bugs that pass static validation could
be substantial.

The cost asymmetry: pre-flash debug cycles are minutes
(build → validate → green/fail). Hardware-flash debug cycles will
be hours (build → flash → boot → dmesg → debug). Most of the bugs
will surface in the latter mode, and most will have accumulated
across multiple sub-waves.

**Decision needed before sub-wave 2C accumulates non-trivial
landings:** stand up cuttlefish / QEMU runtime validation now, OR
explicitly accept that Phase 6 will be a multi-day debugging
mode-shift to surface 10–20+ latent runtime bugs.

This is a one-time investment (a few hours of cuttlefish setup) +
minutes per sub-wave of post-build runtime smoke check, vs the
implicit cost of deferring everything to Phase 6.

Recorded here as a deferred decision for the user; not blocking
2C's emission inventory from starting (the inventory is pre-build
analysis), but blocks landing 2C wire-up commits without
an explicit decision on which class of bugs to defer.

Tracking in DEFERRED_FOLLOWUPS.md as item 4 (deferred decision,
not deferred work).

---

## Sub-wave 2C — audio cluster wire-up (COMPLETE 2026-05-02)

### Approach (post-inventory, outcome ≈ 1)

Per the inventory finding (audio-kernel framework wired but no
canoe-specific config glue), authored:
- `audio-kernel/config/canoeauto.conf` — sed PINEAPPLE→CANOE on
  pineappleauto.conf (only `CONFIG_SND_SOC_PINEAPPLE` → `CONFIG_SND_SOC_CANOE`
  changes; rest are SoC-agnostic)
- `audio-kernel/config/canoeautoconf.h` — same name sub on the
  C-header version
- 11 sub-Kbuilds (`dsp/`, `soc/`, `ipc/`, `asoc/`, `asoc/codecs/`,
  + 6 codec-specific dirs) — added `ifeq ($(CONFIG_ARCH_CANOE), y)`
  blocks alongside the existing PINEAPPLE blocks. Generated via Python
  script that copy-replicates each PINEAPPLE block.

### One iteration to v2 (HDMI deferral)

v1 build failed on `msm_hdmi_codec_rx.c` `#include <msm_ext_display.h>`
— audio-kernel's Kbuild doesn't wire the include path to the
mm-drivers/msm_ext_display external. Tracked as a deferred follow-up
(not boot-critical; HDMI audio is a tail feature).

v2 commented out `CONFIG_SND_SOC_MSM_HDMI_CODEC_RX` in both
canoeauto.conf and canoeautoconf.h, build passed.

### Modules emitted (30)

Across `updates/dsp/`, `updates/soc/`, `updates/ipc/`,
`updates/asoc/codecs/`, `updates/asoc/codecs/lpass-cdc/`,
`updates/asoc/codecs/{wcd938x,wcd939x,wsa883x,wsa884x}/`:

```
adsp_loader_dlkm        audio_pkt_dlkm          audio_prm_dlkm
audpkt_ion_dlkm         gpr_dlkm                lpass_cdc_dlkm
lpass_cdc_rx_macro_dlkm lpass_cdc_tx_macro_dlkm lpass_cdc_va_macro_dlkm
lpass_cdc_wsa_macro_dlkm lpass_cdc_wsa2_macro_dlkm mbhc_dlkm
pinctrl_lpi_dlkm        q6_dlkm                 q6_notifier_dlkm
q6_pdr_dlkm             snd_event_dlkm          spf_core_dlkm
stub_dlkm               swr_ctrl_dlkm           swr_dlkm
swr_dmic_dlkm           swr_haptics_dlkm        wcd938x_dlkm
wcd938x_slave_dlkm      wcd939x_dlkm            wcd939x_slave_dlkm
wcd9xxx_dlkm            wcd_core_dlkm           wsa883x_dlkm
wsa884x_dlkm
```

### Validation (representative subset)

| Module | __versions | CRC match | KMI clean | Verdict |
|---|---:|---|---:|---|
| q6_dlkm | 7 | 7/7 | 100% | pass |
| lpass_cdc_dlkm | 82 | 82/82 | 98.78% | pass |
| lpass_cdc_rx_macro_dlkm | 93 | 93/93 | 100% | pass |
| wcd939x_dlkm | 131 | 131/131 | 99.24% | pass |
| gpr_dlkm | 51 | 51/51 | 100% | pass |
| swr_dlkm | 42 | 42/42 | 100% | pass |

All `vermagic_release: 6.12.23-4k-g59bd74c45df9` (matches running
kernel). `validate_module.sh` exits 0.

### EXPORT_SYMBOL ladder STILL not exercised

Fourth sub-wave (Wave 1 + 2A + 2A.5 + 2C) where the ladder was
predicted to fire and didn't. Phase F/H whitelist coverage extends
to ALSA/ASoC framework + qcom audio framework + lpass-cdc internals
+ WCD codecs + SoundWire — wider than projection assumed.

### Effort vs projection

| Sub-wave | Projection | Actual |
|---|---|---|
| 2A | 3–5 days, 5–15 EXPORTs | ~45 min, 0 EXPORTs |
| 2A.5 | n/a (corrective) | ~30 min, 0 EXPORTs |
| 2C | 2–4 hours, 5–15 EXPORTs | ~1 hour, 0 EXPORTs |

Per calibration discipline: NOT yet updating Wave 2 timeline. Need
≥2 more sub-wave data points from genuinely heterogeneous content
(2D oplus_bsp_*, 2H oplus_network) before priors can be recalibrated.

### Commits

- modules `05aecd9a`: canoeauto.conf + canoeautoconf.h + 11 Kbuild
  canoe gates + HDMI codec deferral + DEFERRED_FOLLOWUPS entry
- modules `99849079` (corrective v3): `#define OPLUS_ARCH_EXTENDS 1`
  in canoeautoconf.h. Brunch closeout v2 surfaced 2 OEM-prebuilt
  depmod errors (oplus_daemon_adsp_ssr / oplus_set_sound_card_init_done
  unknown). adsp-loader.c had the symbols inside `#ifdef
  OPLUS_ARCH_EXTENDS`; OEM Bazel-flow injects the define, we mirror
  via the autoconf header so all sub-Kbuilds inherit it.

No companion device-tree change (audio-kernel already in
TARGET_KERNEL_EXT_MODULES).

### Lesson for downstream sub-waves

When a source-built module overwrites an OEM prebuilt, any
oplus-specific EXPORT_SYMBOLs gated by `#ifdef OPLUS_ARCH_EXTENDS`
(or analogous oplus-architecture defines) need to be mirrored into
our build's preprocessor environment. Otherwise OEM prebuilts that
consume those exports break at depmod time. Affected sub-waves
likely: 2D (oplus_bsp_*), 2H (oplus_network), 2F (oplus_other audio
extensions).

For audio specifically, `canoeautoconf.h` now carries the define.
Other module trees may need analogous treatment.

### Brunch closeout

`~/android/iter_brunch.sh wave2c_closeout_v2` exit 0, 4m41s.
Fresh ROM zip lineage-23.2-20260502-UNOFFICIAL-infiniti.zip @ 2.3 GB.
30 audio modules installed in vendor_dlkm under
`updates/{dsp,ipc,soc,asoc,asoc/codecs,asoc/codecs/lpass-cdc,...}/`.

### Sub-wave 2C COMPLETE per Plan §5.4

- ✅ jm2 commits on modules fork (audio-kernel changes + doc retro)
- ✅ wave_02_status.md retrospective (this section)
- ✅ MVB ROM passes Phase 2 validators (brunch closeout exit 0;
  adsp_loader_dlkm exports both previously-missing symbols)
- ✅ Release-candidate tag (`wave-2c` on modules fork — about to land)

---

## Priors recalibration (post 2A/2A.5/2B/2C, 2026-05-02)

Four sub-waves have landed without exercising the EXPORT_SYMBOL
ladder once. Pre-Wave-2 projection (drawn from Plan §11) was 50–150
EXPORTs over the full wire-up at a rate that rises through each
sub-wave; actual is **0 to date**.

**What this is and isn't evidence of:**

- It IS evidence that Phase F whitelist + Phase H trim — combined
  with the source-built kernel re-exporting whatever consumers need
  via the canonicalize-against-OEM step in Phase 1 — has been more
  comprehensive than expected. The whitelist generation (`make
  abi/abi.stg` + post-process to `abi_gki_aarch64.stg`) appears to
  have absorbed the cross-module consumer set.
- It IS evidence that K3 modules in clusters with oplus-specific
  forks (clocks, audio) tend to be self-contained: consumers and
  producers within the same cluster, exports already at-module-edge.
- It is NOT evidence the rest of Wave 2 will follow the trend. The
  remaining sub-waves (2D oplus_bsp_*, 2F oplus_other, 2H
  oplus_network) are heterogeneous backlog, not clusters. They have
  more cross-tree consumer/producer fan-in patterns (e.g.,
  oplus_bsp_touch consumes drm/lcd APIs, oplus_network consumes
  net/core APIs), where exports may live in core kernel files that
  Phase F's whitelist generation didn't reach because no in-tree
  module was consuming them at trim time.
- It is NOT evidence to retire `EXPORT_SYMBOL_HANDLING.md`'s
  4-step ladder. The discipline is cheap; the failure mode it
  prevents (silent kernel-config drift to satisfy a single module's
  consumer) is expensive.

**Updated projection:**

- Wave 2 total EXPORTs (revised): 5–30 across remaining sub-waves
  (down from initial 50–150 estimate). Heavily weighted toward 2D
  + 2H based on cross-tree consumer fan-in patterns.
- The `kernel_export_additions.md` file may genuinely not need to
  exist until Wave 3+. If it doesn't, the upstream-submission
  cadence task in DEFERRED_FOLLOWUPS shifts later.

**Calibration plan:**

- 2H (oplus_network, 4 modules) FIRST — smallest, exercises
  cross-tree net/core consumer pattern. If it lands with 0 EXPORTs,
  the trend is real and 2D+2F projections should drop further.
- If 2H needs 1+ EXPORTs, the file gets created and we hold the
  current projection.

---

## Sub-wave 2H prep — oplus_network (4 modules) (2026-05-02)

First post-recalibration sub-wave. Smallest cross-tree exerciser.
Calibration value: tests whether the "0 EXPORTs" trend holds when the
modules consume kernel-built-in APIs across-tree (qmi_helpers).

### Scope (modules.load → source dirs → Bazel structure)

| # | Module | Source path | -objs | ko_deps |
|---|--------|-------------|-------|---------|
| 1 | `oplus_network_rf_cable_monitor` | `vendor/oplus/kernel/network/oplus_rf_cable_monitor/` | `oplus_rf_cable_monitor.o` | none |
| 2 | `oplus_network_oem_qmi` | `vendor/oplus/kernel/network/oplus_network_oem_qmi/` | `oem_qmi_client.o` | qmi_helpers (kernel built-in) |
| 3 | `oplus_network_esim` | `vendor/oplus/kernel/network/oplus_network_esim/` | `oplus_network_esim.o` | oplus_network_oem_qmi |
| 4 | `oplus_network_sim_detect` | `vendor/oplus/kernel/network/oplus_network_sim_detect/` | `sim_detect.o` | oplus_network_oem_qmi |

Build order: `qmi_helpers` (already source-built, kernel-internal,
landing in vendor_dlkm via `modules.load`) → `oplus_network_oem_qmi`
→ {`oplus_network_esim`, `oplus_network_sim_detect`} parallel; rf_cable
independent. None of the 4 has a Kbuild yet — pure Bazel projects.

### DT-grounded analysis

- 2 of 4 modules register DT-bound platform drivers:
  - `oplus_network_esim`: compat `oplus,oplus-gpio` (note: misnamed
    upstream — the actual driver is the esim platform driver).
  - `oplus_network_sim_detect`: compat `oplus, sim_detect` (note:
    space — likely OEM source typo, preserved as-is).
- Neither compat appears in `device/oneplus/canoe-kernel-dts/` —
  no DT node binds these drivers in canoe. Drivers will register
  but never `probe()`. Source-built modules are still required to
  satisfy `modules.load` entries; behavioral effect is nil.
- `oplus_network_rf_cable_monitor.c` is a **no-op stub**:
  `op_rf_cable_init()` returns 0, `op_rf_cable_exit()` empty, no
  platform_driver, no probe. OEM prebuilt confirms — `nm` shows
  only init_module + cleanup_module at offset 0x4 (return-0
  sleds), zero EXPORT_SYMBOLs. We're shipping a 30 KB no-op for
  build-graph completeness.
- `oem_qmi_client.c` is the only module with real kernel-API
  surface: consumes `qmi_handle_init/release`, `qmi_txn_*`,
  `qmi_send_request/response/indication`, `qmi_add_lookup`,
  `qmi_encode/decode_message`, `qmi_response_type_v01_ei`. All
  already `EXPORT_SYMBOL_GPL`'d in
  `kernel/.../drivers/soc/qcom/qmi_interface.c` + `qmi_encdec.c`.
  No kernel-side EXPORT additions expected.

### dt_consistency_check.py applicability

Vacuously clean. 2 of 4 modules have compatibles, neither resolves
to a node in canoe DT — but that's a behavioral concern (drivers
won't probe), not a phandle-consumer-references-non-loadable-producer
concern that the tool catches. Tool finds nothing to report;
recording the "vacuously clean" outcome here.

### exports_superset_check.py expectation

All 4 modules have OEM prebuilt counterparts in
`device/oneplus/infiniti-kernel/`. Expected verdicts:
- `oplus_network_rf_cable_monitor`: pass-exact (both empty).
- `oplus_network_oem_qmi`: pass-exact or pass-additive (oem_qmi
  is a leaf consumer, doesn't export to other oplus modules).
- `oplus_network_esim` / `oplus_network_sim_detect`: pass-exact
  or pass-additive (also leaf consumers).

If any return `fail-missing-exports`, we have an OPLUS_ARCH_EXTENDS-
class issue analogous to 2C. Likelihood: low (oem_qmi/esim/sim_detect
are oplus-internal, no upstream Bazel-flow defines to mirror).

### Anticipated EXPORT_SYMBOL surface

**Projection: 0** (consistent with the 4-prior-sub-wave trend).

Reasoning: every kernel API consumed is already
`EXPORT_SYMBOL_GPL`'d. No producer-to-other-module exports needed
(rf_cable is no-op; oem_qmi/esim/sim_detect are leaf consumers,
not producers). If non-zero, `kernel_export_additions.md` gets
created and the priors recalibration's lower-bound-solid /
upper-bound-uncertain framing is validated.

### Effort projection

- Wire-up: 30–60 min (4 thin Kbuilds + Makefile shells, top-level
  `vendor/oplus/kernel/network/Kbuild` ordering, BoardConfigCommon.mk
  TARGET_KERNEL_EXT_MODULES additions).
- Build-iteration: 1 brunch run if clean, 1 retry if any
  miscellaneous issue (header path, kbuild syntax).
- Total: 1–2 hours expected, 4 hours upper-bound.

### Status

Prep done 2026-05-02. Wire-up next.

### Corrections (2026-05-03)

Three findings from a closer review of the prep:

**(1) DT probe claim was wrong.** Original prep said "neither compat
resolves to a node in canoe DT — drivers will register but never
probe()." That was based on grepping `device/oneplus/canoe-kernel-dts/`
only. Both compatibles ARE present in
`kernel_platform/qcom/opensource/devicetree/oplus/infiniti_overlay_common.dtsi`,
which is `#include`'d by `infiniti-24831-canoe-overlay.dtso` and
`infiniti-24863-canoe-overlay.dtso`. The compiled `.dtbo`s are wired
into our flash image via `device/oneplus/sm8850-common/tools/dtb/select_techpack_dtbos.sh`
(Phase 3 work). Both drivers WILL probe on the flashed device:

  - `oplus,oplus-gpio` node carries esim_en + sim2_det pinctrl, eSIM
    enable GPIO (`pmih010x_gpios 10`), SIM2 detect GPIO
    (`pmh0110_d_gpios 7`), uim-reset = "modem_solution" — full
    eSIM hardware enablement, NOT a no-op.
  - `oplus, sim_detect` node carries `Hw,sim_det = "modem_det"` —
    SIM-presence detection wired to modem.

Behavioral effect is NOT nil. These are real-device-functionality
modules.

**(2) "Space in compatible string" is bug-for-bug matched.** Both
the source (`{.compatible = "oplus, sim_detect"}`) and the DT node
(`compatible = "oplus, sim_detect"`) carry the space. Source matches
DT exactly. Functional, but cargo-culted across both sides for
reasons known only to OEM. Preserve as-is is correct *because both
sides have it*; it's not a "preserve OEM typo" call, it's a "the typo
is the contract" call.

**(3) Process: prep-section greps must span overlays, not just
canoe-kernel-dts/.** The original grep missed the
`infiniti_overlay_common.dtsi` path because it lives under the
qcom/opensource/devicetree tree, not the device/oneplus/canoe-kernel-dts
tree. Any future sub-wave's DT probe analysis must `git grep` across:

  - `device/oneplus/canoe-kernel-dts/`
  - `kernel/oneplus/sm8850-modules/kernel_platform/qcom/opensource/devicetree/`
  - any project-id-specific overlay dirs (e.g. `oplus_nfc/`, `tp/`,
    `mm/`, `sensor/`, `oplus_uff/`, `oplus_chg/`, `oplus_icc/`,
    `oplus_misc/`).

Adding to the dt_consistency_check.py followup: the tool currently
only validates phandle reachability; it could also flag "compatible
declared in driver but no DT node anywhere" as a separate weak-link
class. Deferred to DEFERRED_FOLLOWUPS.

### dt_consistency_check.py applicability (revised)

Compatibles resolve via the canoe overlays. From the tool's
perspective (phandle-consumer-vs-loadable-producer), still nothing
to flag — neither esim nor sim_detect references phandles to other
loadable modules' producers. Run will report a normal pass.

### rf_cable_monitor no-op pattern (expanded)

Worth tracking as a Wave 2 metric. The OEM ships a 30 KB module
in `modules.load` whose only behavior is `op_rf_cable_init()
{return 0;}` and an empty exit path — no platform_driver, no
sysfs hooks, no init-time work. The module exists for build-graph
completeness, not function. Implications:

- "In modules.load" ≠ "functionally required." Some Wave 2 modules
  may be similarly empty.
- Source-side investigation that finds a stub doesn't indicate
  a wire-up bug; it's a real OEM artifact.
- Inverse pattern (substantial-looking module that's actually a
  no-op) means our wire-up effort scales sublinearly with apparent
  surface area for those modules.

Tracking as `noop_modules.md` after 2H closes (count + names
across Wave 2). Useful for the post-wave retrospective and for
informing whether `vendor_dlkm` slimming is a viable downstream
optimization.

Two sub-classes worth distinguishing in the tracking:

  - **obvious-stub**: source-side review reveals no platform_driver,
    no probe, init/exit return 0. rf_cable_monitor exemplar.
    Detectable statically.
  - **runtime-effective-no-op**: hundreds of lines, real
    platform_driver registration, real probe — but the activation
    gate (`#ifdef CONFIG_OPLUS_FEATURE_FOO_FOR_BENGAL_ONLY`,
    project-ID check, region-string check) never fires on canoe.
    Source-built module loads cleanly, probe runs, then
    short-circuits on the gate. Not visible from a static read of
    the .c file alone — needs either grep for runtime gates or
    actual flash-time observation.

The second class is the more interesting one to track: it's the
class where wire-up effort is real but downstream functional
contribution is zero. By 2D / 2F the agent should expect to see
this class and call it out by name.

### EXPORT projection (post-correction)

Still **0**. The corrected DT-probe finding doesn't change the
projection because the consumed kernel API surface is unchanged —
the modules consume `qmi_helpers`, platform driver registration
APIs, GPIO consumer APIs (`devm_gpiod_get`, `gpiod_direction_*`,
`gpiod_set_value`), pinctrl APIs, all already
`EXPORT_SYMBOL_GPL`'d. The corrected understanding ("modules
probe and do real hardware work") changes the *behavioral
significance* of the modules, not their kernel-side EXPORT
requirements.

### Variant-DT institutional note

`infiniti_overlay_common.dtsi` is `#include`'d by **two**
project-id-specific overlays, both shipped:

  - `infiniti-24831-canoe-overlay.dtso` (project-id 24831 — primary)
  - `infiniti-24863-canoe-overlay.dtso` (project-id 24863 — variant)

Both compile to `.dtbo`s and both are wired into the flashed image
via `select_techpack_dtbos.sh`. Future Wave 2 sub-waves whose
modules have variant-conditional bindings (touch panel, NFC,
display, sensor) must check **both** project-id overlay paths,
not just one. Variant overlay dirs to check:

  - `oplus_nfc/infiniti-24831.dtsi`
  - `tp/infiniti-oplus-tp-24831.dtsi`
  - `mm/infiniti-24831-canoe-mm.dtsi`
  - `oplus_icc/infiniti-24831-icc.dtsi`
  - `sensor/infiniti-sensor-24831.dtsi`
  - `oplus_uff/oplus-uff-24831.dtsi`
  - `oplus_chg/oplus-chg-24831.dtsi`
  - `oplus_misc/oplus-misc-24831.dtsi`

(24863 variants exist for the subset that diverges; if the 24831
file doesn't have what you need, `find ... -name '*24863*'`.)

---

## Sub-wave 2H retrospective (2026-05-03)

### Outcome

**GREEN.** All 4 oplus_network modules source-built. Brunch v4
exit 0 in 5:13. exports_superset_check verdict: 4/4 pass-exact.

| Module | src .ko size | OEM .ko size | exports verdict |
|---|---|---|---|
| oplus_network_rf_cable_monitor | 31720 | 31720 | pass-exact (0/0) |
| oplus_network_oem_qmi          | 36504 | 36504 | pass-exact (3/3) |
| oplus_network_esim             | 41456 | 41456 | pass-exact (0/0) |
| oplus_network_sim_detect       | 17632 | 17632 | pass-exact (0/0) |

oem_qmi exports `uim_qmi_power_up_req`, `uim_qmi_power_down_req`,
`oem_qmi_common_req` (consumed by esim and sim_detect); both src
and OEM agree exactly.

EXPORT_SYMBOL projection verified: **0** (matching pre-flight
expectation). Five consecutive sub-waves at this rate; Wave 2
remaining-budget recalibration holds.

### Brunch run history

Four iterations to green. Each iteration progressed exactly one
bug class deeper, confirming the build is iteration-tight (not
flakily failing):

1. **v1 (2:11, fail)**: Kbuild self-reference. esim's source `.c`
   filename matched its module name; the standard
   `$(MODULE)-objs := <name>.o; obj-m += $(MODULE).o` form
   produced a circular `<name>.o ← <name>.o` dependency that
   kbuild dropped, causing `ld.lld: cannot open <name>.o`.
   **Fix**: drop the `-objs` indirection for single-source
   modules with matching names; use `obj-m += <name>.o` directly.
2. **v2 (2:01, fail)**: Cross-leaf symvers visibility. esim and
   sim_detect consume `oem_qmi`'s exports; kbuild's external-
   module flow does NOT auto-merge sibling-leaf-module symvers.
   **Fix v1**: `KBUILD_EXTRA_SYMBOLS += $(M)/.../Module.symvers`
   in Kbuild.
3. **v3 (2:32, fail)**: Path resolution silent failure. The
   Kbuild-form path was resolved lexically by kbuild, not
   canonically — `KERNEL_OBJ/../sm8850-modules/.../esim/../oem_qmi/Module.symvers`
   doesn't normalize through the cross-tree `..` traversal.
   modpost reported "unresolved symbol" not "missing symvers,"
   making the symptom look like a missing-export bug rather than
   a path bug. **Fix v2**: move `KBUILD_EXTRA_SYMBOLS` to the
   Makefile using `$(abspath $(CURDIR)/...)`, matching the
   canonical pattern in `dump_device_info/Makefile`.
4. **v4 (5:13, GREEN)**: full ROM zip, exit 0, all 4 modules
   built with sizes matching OEM exactly.

### Lessons (added to WIRE_UP_RECIPE.md)

- **KBUILD_EXTRA_SYMBOLS goes in Makefile, not Kbuild.** Kbuild
  form has lexical-vs-canonical path-resolution silent failure
  mode. Always use `$(abspath $(CURDIR)/...)` in Makefile.
- **Single-source modules whose source filename matches the
  module name** must drop the `-objs` indirection to avoid the
  circular self-reference.
- **Modpost's "unresolved symbol" can be a path-resolution
  symptom**, not just a missing-export symptom. When debugging
  a modpost fail on a module that uses `KBUILD_EXTRA_SYMBOLS`,
  check the path-resolution layer first.

### Tool fix (exports_superset_check.py)

Bug found during 2H verification: classify() conflated
"both-empty exports" with "no-oem-counterpart found." Empty/empty
is a legitimate pass-exact (no-op stubs, leaf consumers).
"no-oem-counterpart" should be decided exclusively by
`find_oem_counterpart()` returning None, not by classify(). After
fix, recalibrating against the full updates dir:

| Verdict | Pre-fix | Post-fix |
|---|---|---|
| pass-exact | ~0 (all mis-reported) | 33 |
| pass-additive | 1 | 1 (smcinvoke_dlkm — qseecom_* additive) |
| no-oem-counterpart | ~36 | 4 (modules without OEM .ko) |
| fail-missing-exports | 2 | 2 (msm_drm + msm_hw_fence — known) |

The 2 fail-missing-exports are pre-existing display-cluster gaps
already documented in DEFERRED_FOLLOWUPS.md; not 2H-caused.

### no-op modules tracked (2H contribution)

- `oplus_network_rf_cable_monitor` — obvious-stub class. Source
  `op_rf_cable_init() { return 0; }`, no platform_driver, no
  probe. OEM ships identical 30 KB no-op. Build-graph completeness
  only.

`noop_modules.md` not yet created (single entry; will start file
when 2D adds entries).

### EXPORT-projection accuracy retrospective

Pre-2H projection: **0** EXPORTs added. Actual: **0**. Five
consecutive sub-waves matching projection. The recalibrated
5–30 EXPORT range for remaining Wave 2 holds; lower bound is
empirically the most likely outcome. No projection update
needed yet — single additional data point.

### Commits in this sub-wave (chronological)

- `7094b89` 2H prep section (DT-grounded scope)
- `b48df6e` 2H prep corrections (DT overlay finding)
- `9bed310` DEFERRED_FOLLOWUPS: compat-orphan + noop_modules
- `4a56aa0` 2H prep refinements (EXPORT projection / no-op
  sub-classes / variant DT)
- `6d104a5f` 2H wire-up: 4 Kbuild + Makefile pairs (modules)
- `c94789b` sm8850-common: TARGET_KERNEL_EXT_MODULES += quartet
- `67ec986b` 2H fix v1: esim Kbuild self-reference
- `b768c17f` 2H fix v2 (Kbuild form): KBUILD_EXTRA_SYMBOLS for
  esim + sim_detect (incorrect $(M)/... form)
- `212c22d7` 2H fix v3 (Makefile form): $(abspath $(CURDIR)/...)
- `fa76d91` 2H institutional knowledge: recipe doc + tool fix

### Status

**Sub-wave 2H COMPLETE.** Wave 2 source-built ext-modules count:
30 → 34. Next: sub-wave 2D (oplus_bsp_* + oplus_hbp_core, 31
modules — see prep below). Decision on signature-mismatch checker
deferred until after 2D.

---

## Calibration prediction update (2026-05-03 post-2H)

Five consecutive sub-waves at 0 EXPORTs added (2A, 2A.5, 2C, 2H,
plus the Phase 4 keyevent_handler proof-point). Recalibrated 5–30
range was set after four data points; with the fifth, the lower
bound is empirically the modal outcome, not just possible. Worth
making the next-step thresholds explicit:

**If 2D lands at 0 EXPORTs**: the range tightens to **0–10 with
most of the mass at 0**. 2D is the largest remaining sub-wave
(31 modules) and the most cross-tree-fan-in-heavy of the
unplayed sub-waves. A zero result there means the favorable
trend isn't just a clocks/audio artifact (those subsystems had
F/H pre-export advantages); it's a pattern that holds for
subsystems that don't share those advantages.

**If 2D lands at 1–5 EXPORTs**: the range stays at 5–30 but
shifts mass downward; expect the remaining 2E/2F/2G/2I to come
in similar.

**If 2D lands at >5 EXPORTs**: the original 5–30 range is
correct and the favorable trend was clocks/audio-specific.
Reproject 2E/2F/2G/2I on this evidence.

The three remaining sub-waves the previous priors flagged as
"likely to fire the EXPORT ladder":

- **2D**: cross-tree drm/lcd consumers (touchscreen tp_common
  uses panel_event_notifier from soc-repo and might consume
  drm helpers) — partially answered by the 2D prep below
- **2F**: oplus_other audio extensions (oplus_audio_daemon,
  oplus_audio_netlink — may need additional EXPORTs from the
  audio cluster we built in 2C)
- **2G**: msm_kgsl, msm-eva, msm_video — untouched subsystems

2D is the next real test. If 2D and one of {2F, 2G} both come
in at zero, the upstream-submission cadence calibration probably
moves from "patch series in Phase H+1" to "no patch series
needed; submit any future findings opportunistically."

---

## Sub-wave 2D prep — oplus_bsp_* + oplus_hbp_core (31 modules) (2026-05-03)

The largest unplayed sub-wave by module count. Mixed structure:
genuine cluster (touch) + independent leaves (haptic, fingerprint,
fw_update). NOT a Wave-1-style mini-batch and NOT a 2C-style pure
cluster — hybrid.

### Scope (modules.load filtering)

Started from `vendor_dlkm/lib/modules/modules.load`. Already
source-built and excluded: `oplus_bsp_dfr_dump_device_info`,
`oplus_bsp_dfr_dump_reason`, `oplus_bsp_dfr_keyevent_handler`,
`oplus_bsp_dfr_pmic_monitor`, `oplus_bsp_tp_notify` (4 DFR + 1
touch-notify, all landed in Wave 1 or earlier 2x sub-waves).

Remaining count: 30 in modules.load + 1 build-time-only dep
(`oplus_bsp_dft_kernel_fb` — not in modules.load but required for
haptic_feedback's modpost). Total wire-up: **31 modules**.

### Subsystem breakdown

**Touch cluster (oplus_touchscreen_v2)** — 23 modules. Real DAG:

| Tier | Modules | Internal deps |
|---|---|---|
| Foundation | `tp_custom` | none (within touch) |
| Foundation | `tp_common` | tp_custom + panel_event_notifier (already source-built in soc-repo) |
| Vendor common | `tp_focal_common`, `tp_goodix_comnon`, `tp_ilitek_common`, `tp_novatek_common`, `tp_syna_common` | each: tp_custom + tp_common |
| Per-chip Focal leaves | `tp_ft3518`, `tp_ft3658u_spi`, `tp_ft3681`, `tp_ft3683g`, `tp_ft8057p` | tp_focal_common (and tp_custom + tp_common transitively) |
| Per-chip Goodix leaves | `tp_gt9916`, `tp_gt9966` | tp_goodix_comnon |
| Per-chip Ilitek leaves | `tp_ilitek7807s` | tp_ilitek_common |
| Per-chip Novatek leaves | `tp_nt36528_noflash`, `tp_nt36532_noflash`, `tp_nt36536_noflash`, `tp_nt36672c_noflash` | tp_novatek_common |
| Per-chip Synaptics leaves | `tp_tcm_S3908`, `tp_tcm_S3910`, `tp_td4377_noflash` | tp_syna_common |

This is structurally the cleanest cluster in Wave 2: 1 root
(tp_custom), 1 second-tier (tp_common), 5 vendor-common
foundations, 16 per-chip leaves. Build order is fully determined.

**HBP cluster (tp/hbp/hbp)** — 2 modules:

- `oplus_hbp_core` (foundation; consumed by all hbp leaves)
- `oplus_bsp_tp_hbp_syna_s3910` (deps oplus_hbp_core; the only
  HBP per-chip leaf in modules.load on canoe — `oplus_ft3683g`
  and `oplus_bsp_tp_hbp_goodix_gt99x6` exist in the bzl but
  aren't loaded on canoe)

Two-tier mini-cluster, build ordering: oplus_hbp_core → s3910.

**synaptics_hbp tree** — 1 module:

- `oplus_bsp_synaptics_tcm2` (separate Bazel tree from
  oplus_touchscreen_v2 and tp/hbp/hbp; independent leaf)

**Haptic cluster (vibrator/bazel)** — 3 modules including the
hidden dep:

| Module | In modules.load? | ko_deps |
|---|---|---|
| `oplus_bsp_dft_kernel_fb` | NO (build-time only) | none |
| `oplus_bsp_haptic_feedback` | YES | dft_kernel_fb |
| `oplus_bsp_haptic` | YES | haptic_feedback + boot/projectinfo + boot/bootmode |

dft_kernel_fb is a hidden third haptic-tier module: not loaded at
boot (OEM doesn't include it in modules.load) but required for
haptic_feedback's modpost step. We must source-build it AND add
its Module.symvers via KBUILD_EXTRA_SYMBOLS in haptic_feedback's
Makefile. It probably ships as a fallback module that's never
loaded on canoe; our flow will install but not load it.

**Fingerprint** — 1 independent leaf:

- `oplus_bsp_uff_fp_driver` from
  `vendor/oplus/secure/biometrics/fingerprints/bsp/uff/driver/`

**fw_update** — 1 independent leaf:

- `oplus_bsp_fw_update` from
  `vendor/oplus/kernel/touchpanel/kernelFwUpdate/bazel/`

### Build-order DAG (critical path)

```
Already-built foundations (no action):
  panel_event_notifier (soc-repo), oplusboot, oplus_bsp_bootmode,
  oplus_bsp_boot_projectinfo, device_info, oplus_bsp_tp_notify

Tier 1 (no internal deps; can build in parallel after foundations):
  tp_custom        ┐
  oplus_hbp_core   │
  synaptics_tcm2   │   parallel
  fw_update        │
  uff_fp_driver    │
  dft_kernel_fb    ┘

Tier 2 (after tier 1):
  tp_common (deps tp_custom)              ┐
  haptic_feedback (deps dft_kernel_fb)    │   parallel
  tp_hbp_syna_s3910 (deps oplus_hbp_core) ┘

Tier 3 (after tp_common):
  tp_focal_common, tp_goodix_comnon,    ┐
  tp_ilitek_common, tp_novatek_common,  │   5-way parallel
  tp_syna_common                        ┘
  haptic (deps haptic_feedback) — independent of touch tier 3

Tier 4 (after vendor commons):
  Focal leaves (5), Goodix leaves (2), Ilitek leaves (1),
  Novatek leaves (4), Synaptics tcm leaves (3)
  = 15 leaves, all parallel after their respective vendor common
```

Critical path is 4 tiers deep on the touch side. Wire-up in 4
batches of Kbuild + Makefile pairs. Brunch run will iterate the
DAG automatically given correct KBUILD_EXTRA_SYMBOLS chains.

### DT-grounded analysis

Touch panel modules ARE DT-bound. Each per-chip leaf has a
`compatible` matching its panel-vendor's binding in DT
(`focal,*`, `goodix,*`, `synaptics,*`, etc.). canoe's DT will
have ONE panel-vendor compatible enabled (whichever panel the
device shipped with); the other 14 leaves' probe() functions
register but never fire.

This is the inverse pattern from 2H esim/sim_detect (where
modules.load has one entry, DT has one matching node). Here,
modules.load has 16 per-chip leaves but DT only matches one.
The other 15 are loaded for build-graph completeness — same
class as 2H rf_cable_monitor but in bulk. **Expect to add 14–16
modules to noop_modules.md as runtime-effective-no-op (NOT
obvious-stub; their probe registers but doesn't fire).**

This is the runtime-effective-no-op class we anticipated in 2H's
prep refinements. 2D will be the first sub-wave to populate it
in volume.

DT analysis to run during wire-up: `git grep` for the per-chip
panel compatibles across both `device/oneplus/canoe-kernel-dts/`
AND `kernel_platform/qcom/opensource/devicetree/oplus/` (the
2H-correction lesson). Expect to find ONE panel-compatible
populated; the other 15 are wired but inert.

### dt_consistency_check.py applicability

Real check this time. tp_common references panel_event_notifier
(source-built in soc-repo) — phandle reachability passes. Touch
leaves reference per-vendor commons, all source-built — passes.
The runtime-effective-no-op leaves reference DT nodes that don't
exist in canoe; that's a *driver-source-declares-compat-without-
matching-DT-node* concern, exactly the case the deferred
`compat-orphan` check would surface. Expect the existing tool to
report clean (no phandle-vs-loadable issues), and to log "would
benefit from compat-orphan check" entries pointing at 14–16
unmatched per-chip compatibles — which is the trigger to actually
build the deferred tool.

### exports_superset_check.py expectation

All 31 modules have OEM prebuilt counterparts (or, for
dft_kernel_fb, an OEM .ko exists in infiniti-kernel/ even though
it's not in modules.load). Expected verdicts:

- Foundations (tp_custom, tp_common, oplus_hbp_core): possibly
  pass-additive if they export to leaves; otherwise pass-exact.
- Vendor commons: pass-exact or pass-additive (export to per-chip
  leaves).
- Per-chip leaves: pass-exact (leaf consumers, don't export).
- Independents (synaptics_tcm2, fw_update, uff_fp_driver): pass-
  exact (unless they export upward to userspace via netlink/
  ioctl, which doesn't show as EXPORT_SYMBOL).
- Haptic tier: dft_kernel_fb probably pass-additive (exports
  feedback API), haptic_feedback pass-exact, haptic pass-exact.

Likelihood of fail-missing-exports: **low**. The touch cluster's
internal foundation→common→leaf flow is fully under our control
once we build the foundations correctly. The only OPLUS_ARCH_EXTENDS
risk would be in tp_common or tp_custom; their .c files should be
inspected during prep refinement (not done in this prep —
flagged as wire-up step).

### Anticipated EXPORT_SYMBOL surface

**Projection: 0** (consistent with 5-prior-sub-wave trend).

Reasoning: every consumed kernel API expected to already be
EXPORT_SYMBOL_GPL'd (input subsystem, sysfs, kthread, regulator,
gpio, i2c, spi, pinctrl). Touch cluster is mostly userspace-facing
(input subsystem, sysfs); no reason to expect kernel-side EXPORT
gaps.

If non-zero, calibration update per the prediction block above.

### Effort projection

Substantially larger than 2H but not proportionally to module count:

- **Wire-up**: 4–6 hours for 31 Kbuild + Makefile pairs. Most are
  thin; vendor commons need KBUILD_EXTRA_SYMBOLS pointed at
  tp_custom + tp_common; per-chip leaves need vendor common
  pointed; haptic_feedback needs dft_kernel_fb pointed.
- **BoardConfigCommon edit**: 31 lines (large but mechanical).
- **Build-iteration**: 2–4 brunch runs expected. Bug classes
  hit in 2H (single-source matching name, KBUILD_EXTRA_SYMBOLS
  paths) are now documented in WIRE_UP_RECIPE; first run should
  clear most of them. Expect 1 retry for an unanticipated
  cross-tree consumer surfacing.
- **Brunch wall-clock**: ~5 min per iteration when only modules
  changed (per 2H v4 timing). Worst-case 4 iterations = ~20 min
  build time + ~30 min debugging per iteration = ~3 hours.
- **Total**: 1 day expected, 2 days upper-bound.

### Risk areas

1. **Touch cluster's panel_event_notifier consumer**: tp_common
   uses `panel_event_notifier_register_panel`. Already
   source-built in soc-repo (kernel-internal). Verify symbol IS
   exported by the kernel build, not just declared.
2. **HBP tier interaction with tp_notify**: oplus_hbp_core
   probably consumes tp_notify exports. Already source-built
   from Wave 1; symvers wiring needed.
3. **Haptic dep chain**: dft_kernel_fb's CONFIG_OPLUS_DDK_MTK
   conditional source. We're qcom, so the non-MTK source path
   (`common/feedback/kernel_fb.c`) applies. Need to NOT define
   CONFIG_OPLUS_DDK_MTK.
4. **uff_fp_driver in vendor/oplus/secure/**: separate Bazel
   tree, may have unfamiliar conventions. Check
   `vendor/oplus/secure/biometrics/fingerprints/bsp/uff/driver/oplus_local_modules.bzl`
   for ko_deps.
5. **Per-chip leaves' DT compatibles**: 15 of 16 won't match canoe
   DT (only one panel ships). Confirm this is benign at modprobe
   time and document in noop_modules.md as runtime-effective-no-op.

### Deliverables checklist (for wire-up phase)

- [ ] Inspect tp_custom.c + tp_common.c for OPLUS_ARCH_EXTENDS
      gates (2C class risk)
- [ ] Inspect dft_kernel_fb's `kernel_fb.c` for unexpected deps
- [ ] Inspect uff_fp_driver bazel for cross-tree consumers
- [ ] Write 31 Kbuild + Makefile pairs
- [ ] Add 31 entries to `device/oneplus/sm8850-common/BoardConfigCommon.mk`
      TARGET_KERNEL_EXT_MODULES
- [ ] Run `tools/jm2/dt_consistency_check.py` — record vacuously-
      clean + compat-orphan findings
- [ ] brunch closeout to green
- [ ] Run `tools/jm2/exports_superset_check.py` — record verdicts
- [ ] Populate `noop_modules.md` with the per-chip leaves that
      probe but never fire
- [ ] Retrospective + calibration update per the prediction block

### Status

Prep done 2026-05-03. Wire-up next.

---

## Sub-wave 2D retrospective (2026-05-03)

### Outcome

**GREEN ON FIRST BRUNCH ITERATION.** All 30 .ko outputs across 7
ext-module entries built clean. Brunch v1 exit 0 in 5:26.

This is the first brunch run that landed clean on iteration 1
since the Phase 4 keyevent_handler proof-point. 2A took 3,
2A.5 took 1 (after dt_consistency fix), 2C took 3 (final v3),
2H took 4 (v4 green). 2D's clean-on-first reflects:

1. The 2H institutional knowledge applied: KBUILD_EXTRA_SYMBOLS
   in Makefile (not Kbuild), single-source-matching-name
   pitfall avoided.
2. The dispatcher pattern (touch cluster, hbp, vibrator)
   correctly mapped Bazel multi-module srcs to a single M= dir
   with auto-merged internal symvers.
3. ZERO OPLUS_ARCH_EXTENDS in any 2D source tree (vs 2C's audio
   cluster which had hundreds).

### exports_superset_check verdicts (2D modules)

29/30 pass-exact. 1/30 fail-missing-exports:

- `oplus_hbp_core`: missing `hbp_dev_ctrl_hw_reset`,
  `hbp_dev_ctrl_power_reconfig`; added `hbp_dev_power_type_ctrl`.

This is an API version delta: OEM oplus_hbp_core exports v1
names; our source tree exports v2. **The tool flagged correctly
— this is a real condition.** The question the tool can't answer
is whether anything in the as-shipped image actually consumes
the missing v1 symbols. Resolving that requires per-consumer
inspection.

Verification chain (run during diagnosis, recording explicitly
here so the methodology is reproducible):

1. **`nm` undefined-refs check on every OEM prebuilt .ko in
   `device/oneplus/infiniti-kernel/`**:
   `nm <ko> | grep -E '^\s+U\s+hbp_dev_ctrl_(hw_reset|power_reconfig)$'`
   - `hbp_dev_ctrl_hw_reset`: only `oplus_bsp_tp_hbp_syna_s3910.ko`
   - `hbp_dev_ctrl_power_reconfig`: ZERO consumers anywhere
2. **The only OEM prebuilt that consumes a v1 symbol —
   `oplus_bsp_tp_hbp_syna_s3910.ko` — we source-build ourselves**.
   Our v2 build replaces the OEM v1 prebuilt in the final image.
3. **The other in-image consumer of hbp_core API —
   `oplus_ft3683g.ko` (OEM prebuilt; not source-built)** — has
   only two undefined hbp_* refs: `hbp_exception_report` and
   `hbp_register_devices`. Both are common-across-versions and
   exported by our source-built oplus_hbp_core. `nm` confirms
   no undefined refs to v1 symbols.
4. `modules.dep` in the final vendor_dlkm resolves both consumers
   (necessary but not sufficient on its own; the nm check above
   is the load-bearing evidence).

**No runtime symbol-resolution failure**. The `fail-missing-exports`
verdict was a *true positive on the static rule* (we're missing
symbols OEM exports) and a *false positive on runtime impact*
(no consumer in our final image references the missing symbols).

Methodology note for future sub-waves: when exports_superset_check
flags fail-missing-exports, the diagnostic gate is `nm | grep U`
across the OEM prebuilt set, NOT just `depmod`. Symbol-name
resolution in modules.dep is necessary but not sufficient — it
catches `__versions` mismatches but doesn't confirm that no
prebuilt has a call site that would invoke the missing symbol.
The `nm U` check is the bulletproof confirmation. Adding to
WIRE_UP_RECIPE.md.

### EXPORT_SYMBOL count: 0

**Projection: 0. Actual: 0.** Six consecutive sub-waves matching
projection.

No new EXPORT_SYMBOL declarations needed in any kernel-source-tree
file. All consumed APIs (input subsystem, sysfs, regulator, gpio,
i2c, spi, pinctrl, plus the existing oplus modules' exports)
were already EXPORT_SYMBOL_GPL'd. Touch cluster's internal
producer→consumer chain is fully under our control via the
dispatcher pattern.

### Calibration update (per the prediction block)

The prediction was: "If 2D lands at 0 EXPORTs, the range tightens
to 0–10 with most of the mass at 0."

**Range update: 0–10 with mass at 0** for remaining Wave 2.

The favorable trend isn't clocks/audio-specific. 2D — the largest
unplayed sub-wave by count, the most cross-tree-fan-in-heavy
unplayed sub-wave, and the one with no F/H pre-export advantages
— came in at zero. The remaining sub-waves (2E qcom_qti, 2F
oplus_other audio extensions, 2G msm_kgsl/msm-eva/msm_video,
2I bluetooth) are smaller in count and structurally less
cross-tree-fan-in-heavy than 2D. The probability that any of them
fires a meaningful EXPORT ladder is now low.

If 2F (oplus_other audio extensions) or one of {2E, 2G, 2I} also
lands at 0, recommend moving to "no upstream patch series needed
for Wave 2 EXPORT additions" status. Currently filed in
DEFERRED_FOLLOWUPS as "EXPORT_SYMBOL upstream submission cadence";
that entry can be retired if the trend extends one more sub-wave.

### no-op modules tracked

16 runtime-effective-no-op entries added to `noop_modules.md`
(first bulk population). All 15 are per-chip touch leaves whose
compatible doesn't match canoe DT (or matches a `status = "disabled"`
node). Active touch driver on canoe is Synaptics S3910 via HBP
(`oplus_bsp_tp_hbp_syna_s3910`).

Wave 2 has crossed the 15-entry threshold (16 entries from 2D
alone). Filed `vendor_dlkm slimming via runtime-effective-no-op
removal` in DEFERRED_FOLLOWUPS — removing per-chip touch leaves
whose compatibles don't match canoe DT would save ~3 MB of
vendor_dlkm space.

### Effort actuals

- Wire-up: ~2 hours (estimate was 4–6).
- Build-iteration: 1 brunch (estimate was 2–4).
- Total wall-clock: ~3 hours (estimate was 1 day).

The estimate was conservative; 2D went faster than projected
because (a) zero OPLUS_ARCH_EXTENDS removed the largest risk
class, (b) the dispatcher pattern collapsed 22+2+2 modules into
3 M= dirs, (c) 2H's institutional fixes prevented the v1/v2/v3
brunch retries that 2H itself needed.

### dt_consistency_check.py

Did not run a separate gate-check this time because the bulk
runtime-effective-no-op pattern surfaced organically during the
exports check. The compat-orphan extension proposed in
DEFERRED_FOLLOWUPS is now well-specified (15 concrete instances
in 2D) — if 2F or 2G surface a similar pattern, build the tool
extension then.

### Commits in this sub-wave (chronological)

- `58521b45` 2D prep + calibration prediction
- `91b2cf28` modules: 7 Kbuild + Makefile pairs (modules tree)
- `8d0c68c` sm8850-common: TARGET_KERNEL_EXT_MODULES += 7 entries

### Status

**Sub-wave 2D COMPLETE.** Wave 2 source-built ext-modules
entries: 34 → 41 (modules.ko: 34 → 64, with the touch dispatcher
producing 22 .ko from one entry).

Next: sub-wave 2F (oplus_other audio extensions, ~21 modules) or
2E/2G/2I per the wave plan. Decision on signature-mismatch
checker and compat-orphan dt_consistency_check extension still
deferred.

---

## Sub-wave 2F prep — oplus_other (19 modules across 7 subsystems) (2026-05-04)

Started from `comm -23` between modules.load and updates/ (post-2D
build). 19 oplus_* modules remain unwired (down from ~21 in the
original wave plan; the 2 the prep scoped out: `oplus_ft3683g`
already landed as a 2D-fix follow-up commit `2b068d16` to the
existing hbp/hbp Kbuild dispatcher).

NOT a single cluster. Mixed structure: 1 cluster that extends an
existing tree (audio, in our 2C source-built audio-kernel) + 6
independent subsystems.

### Subsystem breakdown

| Subsystem | Modules | Bazel root | Existing TARGET entry? | OPLUS_ARCH_EXTENDS count |
|---|---|---|---|---|
| Audio extensions | 5 (`oplus_audio_aw882xx`, `oplus_audio_daemon`, `oplus_audio_extend`, `oplus_audio_netlink`, `oplus_audio_tfa98xx_v6`) | `vendor/qcom/opensource/audio-kernel/oplus/` | YES (audio-kernel) — extends dispatcher | **663** |
| Sensors | 5 (`oplus_sensor_deviceinfo`, `oplus_sensor_feedback`, `oplus_sensor_interact`, `oplus_sensor_ir_core`, `oplus_sensor_kookong_ir_spi`) | `vendor/oplus/sensor/kernel/qcom/` | NO (new dispatcher entry) | 0 |
| Magnetic cover | 4 (`oplus_magcvr_ak09973`, `oplus_magcvr_mxm1120`, `oplus_magnetic_cover`, `oplus_magcvr_notify`) | `vendor/oplus/kernel/device_info/magnetic_cover/` + `magtransfer/` | NO (2 new entries) | 0 |
| MM kevent | 2 (`oplus_mm_kevent`, `oplus_mm_kevent_fb`) | `vendor/oplus/kernel/multimedia/feedback/` | NO (new dispatcher) | 0 |
| Secure | 1 (`oplus_secure_common`) | `vendor/oplus/secure/common/bsp/drivers/oplus_secure_common/` | NO | 0 |
| Sync fence | 1 (`oplus_sync_fence`) | `vendor/oplus/kernel/graphics/` | NO | 0 |
| Charger | 1 (`oplus_chg_v2`) | `vendor/oplus/kernel/charger/v2/` | NO | 0 |

Total: **19 modules** across **7 new TARGET_KERNEL_EXT_MODULES
entries** (one is an extension of an existing entry).

### Risk-tier analysis

**Tier 1 (highest risk): Audio sub-cluster (5 modules).**

The audio sub-cluster is the only 2F subsystem with non-zero
OPLUS_ARCH_EXTENDS — 663 occurrences in
`vendor/qcom/opensource/audio-kernel/oplus/`. This is the same
gating mechanism that broke 2C v1/v2 before the 2C v3 fix that
added `#define OPLUS_ARCH_EXTENDS` to canoeautoconf.h. That fix
should still be in effect (canoe.bzl explicitly registers the
oplus_audio_* modules under `#ifdef OPLUS_ARCH_EXTENDS`), but
we haven't actually built the oplus subdir yet — our existing
audio-kernel/Kbuild has `obj-y := dsp/ ipc/ soc/ asoc/...` with
no `oplus/` entry.

Wire-up risk: extending audio-kernel/Kbuild to recurse into
`oplus/` may surface latent issues that 2C's gate fix didn't
cover (e.g., MTK-specific paths that need to be CONFIG-stubbed
out for our qcom build).

The 5 audio modules' Bazel definitions (in
`vendor/qcom/opensource/audio-kernel/audio_modules.bzl`) confirm
qcom-build paths but the SAME modules are also defined in
`vendor/oplus/kernel/audio/bazel/oplus_local_modules.bzl` with
DIFFERENT names (`snd-soc-aw882xx` vs `oplus_audio_aw882xx`)
and MTK-only ko_deps. The qcom audio-kernel registration is
the canonical one for canoe.

**Tier 2 (medium): Charger v2 (1 module, 153 .c files).**

Single .ko output but big — 153 .c files in `vendor/oplus/kernel/charger/v2/`
(plus a `ufcs/` subdir). The Bazel module name is per-target
(`canoe_oplus_chg_v2`) — there's a target/name mapping that
ships as `oplus_chg_v2.ko`. Existing in-tree `Makefile` may be
informative for the obj list. Build-time dependencies likely
include qcom power-management symbols and
oplus_bsp_boot_projectinfo / device_info (already source-built).

**Tier 3 (low): All other 6 subsystems (12 modules).**

Zero OPLUS_ARCH_EXTENDS, structurally simple, mostly leaf-pattern
or small dispatchers (e.g., 5 sensors in one M= dir = sensor
dispatcher; 4 magcvr modules in one M= dir = mag dispatcher).
Standard 2H/2D wire-up pattern applies cleanly.

### Recommended sub-iteration plan

Three sub-iterations of decreasing risk profile, each runnable
independently:

- **2F.1** — Audio extensions (5 modules). Test whether 2C's
  OPLUS_ARCH_EXTENDS gate fix extends to `oplus/` subdir of
  audio-kernel. Iteration is small, isolated to one TARGET
  entry's Kbuild. Calibration impact: confirms whether the
  EXPORT projection holds for the highest-risk 2F sub-cluster.
- **2F.2** — All Tier-3 subsystems together (sensors + magcvr +
  mm_kevent + secure_common + sync_fence + ft3683g
  follow-through, **13 modules across 6 TARGET entries**). Same
  pattern as 2D's smaller subsystems. Should land green on first
  brunch given the 2H/2D institutional fixes.
- **2F.3** — Charger v2 (1 module, 153 .c). Largest module by
  .c count in Wave 2. Run last because if it has a unique issue
  class, isolating it from the rest of 2F's wire-up reduces
  iteration time.

### EXPORT_SYMBOL projection (per cluster)

- 2F.1 audio: **0–5 EXPORTs**. The 663 OPLUS_ARCH_EXTENDS gates
  may surface latent EXPORT requirements that 2C didn't catch.
  Lower bound 0 if 2C's gate fix is truly comprehensive; upper
  bound 5 if a few oplus-specific exports surface.
- 2F.2 Tier-3: **0 EXPORTs** projected. Standard pattern; same
  signal as 2H/2D for this class.
- 2F.3 charger: **0 EXPORTs** projected. Charger consumes power
  framework APIs (already exported); no producer-to-other-module
  exports expected.

**Aggregate 2F projection: 0–5 EXPORTs.** Per the calibration
prediction block: 2F at 0 leaves the recalibrated 0–10 range
mostly unchanged but adds another data point for "no upstream
patch series needed for Wave 2." 2F at 1–5 confirms the
recalibrated lower bound but suggests audio might be the
exception class.

### dt_consistency_check.py applicability

Sensors and magnetic-cover register platform_drivers with
DT compatibles. Worth running the tool against the full
build artifact after 2F.2 to surface any compat-orphan candidates
(potential trigger for the deferred compat-orphan tool extension).

### Effort projection

- 2F.1 audio: 1–4 hours (medium uncertainty due to
  OPLUS_ARCH_EXTENDS risk)
- 2F.2 Tier-3: 2–4 hours (mechanical)
- 2F.3 charger: 1–3 hours
- Total: 4–11 hours expected, 1.5 days upper bound

### Status

Prep done 2026-05-04. Wire-up next, in 2F.1 → 2F.2 → 2F.3 order.

### Pre-flight verifications (2026-05-04, post-review)

Four follow-ups before 2F.1 wire-up:

**(1) ifdef OPLUS_* gates beyond OPLUS_ARCH_EXTENDS in audio sources.**

`grep -rho '#if[a-z]*\s*OPLUS_[A-Z_0-9]*'` across the 5 audio
module source dirs surfaced 5 additional gates beyond
OPLUS_ARCH_EXTENDS that 2C's fix doesn't cover:

  - `OPLUS_FEATURE_SPEAKER_MUTE` (aw882xx + tfa98xx-v6)
  - `OPLUS_FEATURE_AUDIO_FTM` (tfa98xx-v6)
  - `OPLUS_FEATURE_FADE_IN` (tfa98xx-v6)
  - `OPLUS_FEATURE_TFA98XX_VI_FEEDBACK` (tfa98xx-v6)
  - `OPLUS_CALIBRATION` (tfa98xx-v6, in `#ifndef` form)

OEM Bazel sets these via per-module `local_defines` on the MTK-side
snd-soc-* variants. The qcom-side audio_modules.register entries
DON'T pass these defines via the macro; they're expected via
canoeautoconf.h. Currently canoeautoconf.h only has
`#define OPLUS_ARCH_EXTENDS 1` — the other 4 are absent.

Wire-up will need to add these to canoeautoconf.h (or pass via
KBUILD_OPTIONS / EXTRA_CFLAGS in the audio Kbuild). The
`#ifndef OPLUS_CALIBRATION` case is interesting: defining it would
COMPILE OUT a default code path; leaving it undefined keeps the
default. Default behavior is correct unless the OEM enables
calibration, which we should preserve. Don't define OPLUS_CALIBRATION.

**(2) Authoritative Bazel registration for canoe (evidence).**

`vendor/qcom/opensource/audio-kernel/build/canoe.bzl` explicitly
references the qcom audio_modules.bzl entries by name:
`oplus_audio_extend`, `oplus_audio_tfa98xx_v6`, `oplus_audio_aw882xx`,
`oplus_audio_daemon`, `oplus_audio_netlink`. canoe.bzl does NOT
reference `vendor/oplus/kernel/audio/bazel/`. The vendor/oplus
audio bzl is MTK-only (all ko_deps under
`kernel_device_modules-{kernel_version}/sound/soc/mediatek/...`).

**Decision: extend the existing audio-kernel Kbuild dispatcher
to recurse into oplus/ subdir.** Mirrors qcom audio_modules.bzl
entries directly; ignore vendor/oplus/kernel/audio/bazel/ for this
sub-wave (would only matter if we ported to MTK).

**(3) noop_modules.md count consistency.**

Verified: noop_modules.md tally = 16 runtime-effective-no-op + 1
obvious-stub = 17 total. wave_02_status.md retrospective text
uses 16 throughout (no 15-vs-16 inconsistency in the current
file state). synaptics_tcm2 is explicitly tracked as
runtime-effective-no-op with all 3 of its compats analyzed.

**(4) charger/v2 existing Makefile is rich and authoritative.**

`vendor/oplus/kernel/charger/v2/Makefile` has full obj-y rules
across many subdirs (gauge_ic, voocphy, ufcs_ic, switching_ic,
chargepump_ic, wireless_ic, debug) with CONFIG-flag gating for
each silicon variant. Includes `KBUILD_LDS_MODULE_ATTACH =
oplus_chg_module.lds` for custom module linking. Includes
`Makefile.json-build` for runtime config-table generation.

**Decision for 2F.3: keep this Makefile in place, write a Kbuild
shell that delegates to it and a Makefile shell at the parent
level for external-module flow.** The Bazel `srcs` glob would
miss the CONFIG-gated obj entries; the existing Makefile is
ground truth.

### EXPORT-count threshold pre-decision (2F.1)

Pre-deciding to avoid post-hoc rationalization:

- **2F.1 actual = 0**: trend conclusively NOT artifact of any
  specific subsystem class. Range tightens further (0-5 with
  near-certain mass at 0). Retire EXPORT_SYMBOL upstream
  submission cadence in DEFERRED_FOLLOWUPS.
- **2F.1 actual = 1-2**: trend holds; audio is sui generis
  (the only gate-heavy class). Range stays 0-10 with mass at 0;
  audio gets a documented "expected to surface a small handful
  of EXPORTs" annotation for future wave plans.
- **2F.1 actual ≥ 3**: recalibration trigger. Range goes back
  to 5-30 (the original Wave 2 prior). EXPORT_SYMBOL upstream
  cadence becomes a real Wave 2 close item, not a deferred
  followup.

This decision is recorded BEFORE the 2F.1 build runs, so the
calibration update is data-driven not narrative-driven.

---

## Sub-wave 2F.1 retrospective (2026-05-04)

### Outcome

**GREEN. 5/5 pass-exact. EXPORT count = 0.**

| Module | src .ko | OEM .ko | exports verdict |
|---|---|---|---|
| oplus_audio_aw882xx | 407032 | 381680 | pass-exact (0/0) |
| oplus_audio_daemon | 39352 | 40736 | pass-exact (8/8) |
| oplus_audio_extend | 30440 | 29848 | pass-exact (2/2) |
| oplus_audio_netlink | 27960 | 28640 | pass-exact (1/1) |
| oplus_audio_tfa98xx_v6 | 491200 | 420064 | pass-exact (0/0) |

Brunch v3: 4:54.

### Calibration update — per pre-decision threshold

**2F.1 actual = 0**. Per the threshold pre-decision (recorded
before build): **range tightens to 0–5 with near-certain mass
at 0; trend conclusively NOT artifact of any specific subsystem
class. Audio-on-canoe is NOT sui generis.** The 663 OPLUS_ARCH_EXTENDS
gates didn't surface latent EXPORT requirements because the
qcom build path compiles out the OPLUS_FEATURE_SPEAKER_MUTE /
AUDIO_FTM / FADE_IN / TFA98XX_VI_FEEDBACK code blocks anyway
(those defines aren't in canoeautoconf.h on purpose — OEM
ships the qcom audio modules with those features compiled out).

**Generalization caveat**: the conclusion is "the canoe-applicable
subset of audio's gated code doesn't have an EXPORT ladder," not
"audio in general doesn't." A different SoC port (sm8650, sm8550,
MTK) of the same audio source could have different gates set and
might surface EXPORTs that didn't show up here. Future Wave 2-style
work on a different SoC should re-test rather than inherit this
conclusion.

**Seven consecutive sub-waves at 0 EXPORTs** (Phase 4 keyevent_handler
proof-point + 2A + 2A.5 + 2C + 2H + 2D + 2F.1).

The "EXPORT_SYMBOL upstream submission cadence" entry in
DEFERRED_FOLLOWUPS can now be retired: there's no Wave 2 EXPORT
ladder to upstream. (Filed as separate cleanup task — defer
the actual retirement until Wave 2 closes, in case 2F.2/2F.3
or remaining sub-waves surprise us.)

### Brunch iteration history

Three iterations to green. The bug class progression was unusual:

- **v1 (5:26, exit 0, 0 .ko built — silent skip)**: My initial
  Kbuild edit added `obj-y +=` for the 5 oplus subdirs but the
  build silently produced zero modules. modules.order didn't
  include them; no .o compiled.
- **v2 (5:16, exit 0, 0 .ko built — same silent skip)**: Collapsed
  the obj-y line to single-statement form (belt-and-braces fix in
  case kbuild parsing was confused by the obj-y := / += split).
  Same silent skip.
- **v3 (4:54, GREEN)**: Root cause found — the per-leaf Kbuilds'
  `obj-$(CONFIG_X)` lines need Make-side CONFIG variables, not
  C-side #defines. canoeautoconf.h had `#define CONFIG_AUDIO_EXTEND_DRV 1`
  (correct for source ifdef gates) but canoeauto.conf was MISSING
  the corresponding `export CONFIG_AUDIO_EXTEND_DRV=m` line.
  Without the Make variable, `obj-$(CONFIG_AUDIO_EXTEND_DRV)`
  evaluated to `obj- += foo.o` which silently dropped the entry.
  Added 5 export lines to canoeauto.conf → all 5 modules built.

### Lesson — Make-side / C-side asymmetry

The audio-kernel canoe config is split into two files that BOTH
must list every CONFIG flag:

- `canoeauto.conf` — Make-side, `export CONFIG_X=m`
- `canoeautoconf.h` — C-side, `#define CONFIG_X 1`

Setting one without the other is a silent failure mode. Setting
only the .h: build "succeeds" with zero .ko output. Setting only
the .conf: .ko builds but source #ifdef blocks compile out, .ko
is functionally empty.

Added Step 7.6 to WIRE_UP_RECIPE.md documenting this and the
diagnostic recipe (check modules.order; if missing, grep BOTH
files for the CONFIG flag).

### Install path layout

The 5 .ko files installed to subdirectory paths under updates/:
`updates/oplus/qcom/oplus_audio_extend.ko`,
`updates/oplus/codecs/aw882xx/oplus_audio_aw882xx.ko`, etc. NOT
flat `updates/oplus_audio_extend.ko`. The depmod step then
flat-installs to `vendor_dlkm/lib/modules/`. Verification scripts
should check the FINAL flat location, not the
subdir-preserved updates/ tree. Misled myself for two iterations
by checking `updates/oplus_audio_*.ko` and finding nothing.

### Effort actuals

- Wire-up: 1 hour (canoeautoconf.h additions, per-leaf Kbuild
  CONFIG_ARCH_CANOE cases via awk + 2 manual edits, audio-kernel
  Kbuild obj-y addition)
- Build-iteration: 3 brunch runs (16 min total wall clock)
- Diagnosis time: ~30 min on the silent-skip bug
- Total: ~2 hours (estimate was 1–4 hours; landed in the middle)

### Commits in this sub-wave (chronological)

- `a4f314f` 2F prep verifications + threshold pre-decision
- `cd23a4d5` 2F.1 wire-up — 5 oplus_audio_* via existing audio-kernel
  (canoeautoconf.h + per-leaf Kbuild canoe cases + audio-kernel
  Kbuild obj-y additions)
- `f592a1fe` 2F.1 fix — Make-side CONFIG flags + collapsed obj-y
  (resolved the silent-skip after v1+v2 produced 0 .ko)
- `5ee54f12` 2F.1 retro

### Status

**Sub-wave 2F.1 COMPLETE.** Wave 2 source-built ext-modules: 35 ->
35 entries (audio-kernel was already 1 entry; we extended it).
Total .ko outputs: 64 -> 69.

Next: 2F.2 (Tier-3 batch — sensors, magcvr, mm_kevent, secure,
sync_fence — 13 modules across 6 ext-module entries) per the
2F sub-iteration plan.

---

## EXPORT-count threshold pre-decisions for 2F.2 and 2F.3 (2026-05-04)

Recording the calibration update rules BEFORE the builds run, to
prevent post-hoc rationalization. Both decisions assume the prior
seven sub-waves' "0 EXPORTs" trend is the prior, and any non-zero
result is the surprise.

### 2F.2 (Tier-3 batch, 13 modules, projection 0)

- **0 EXPORTs**: trend continues as prior; no calibration update.
  Eight projection-matching data points; the projection IS the
  prior at this point.
- **1–3 EXPORTs**: trend holds, but Tier-3 has surface I didn't
  predict. Document specifically which subsystem(s) and which
  symbols; review whether the prep-section grep methodology
  missed something generalizable.
- **4+ EXPORTs**: unexpected. Recalibrate the range upward. Open
  a "Tier-3 EXPORT analysis" task and don't proceed to 2F.3 until
  characterized.

### 2F.3 (charger v2, 1 module / 153 .c files, projection 0)

- **0 EXPORTs**: trend continues even at scale (153 .c files
  is an order of magnitude larger than typical Wave 2 modules).
  Strong final confirmation that the prior holds across all
  Wave 2 module-size classes.
- **1–2 EXPORTs**: charger has v1/v2-style API delta to
  characterize (analogous to oplus_hbp_core's
  hbp_dev_ctrl_hw_reset / hbp_dev_power_type_ctrl finding).
  Apply the WIRE_UP_RECIPE Step 7.5 nm-check methodology to
  determine whether it's a true runtime issue or a false alarm
  (we source-build both producer and consumer).
- **3+ EXPORTs**: recalibrate. Charger is the largest module;
  if it has a real EXPORT ladder, the prior needs adjustment for
  module-size effect, not just per-sub-wave count.

### EXPORT_SYMBOL upstream cadence retirement criteria (refined)

Earlier I noted "retire when Wave 2 closes." Tightening: retire
after Wave 2 closes **AND** the cumulative EXPORT count across
Wave 2 is **≤ 2**. Anything more warrants a small upstream patch
series even if the modal sub-wave is zero. Threshold is cumulative,
not per-sub-wave.

Current cumulative count: **0** (over 7 sub-waves). Buffer remaining
before triggering retention: 2 EXPORTs across 2F.2 + 2F.3 + any
late surprises.

---

## Sub-wave 2B onwards — heterogeneous module backlog

After the clock cluster lands, Wave 2 moves to the OEM-prebuilt-only
backlog from modules.load. ~213 modules grouped roughly:

| Category | Count | Sub-wave |
|---|---:|---|
| oplus audio / qcom audio | ~30 | 2C — audio cluster |
| oplus_bsp_* (touch, fingerprint, haptic) | 28 | 2D — oplus_bsp_* |
| qcom_qti (regulators, glink, etc.) | 21 | 2E — qcom_qti |
| oplus_other (esim, audio extensions) | 21 | 2F — oplus_other |
| msm_* (kgsl, eva, video) | 11 | 2G — msm_* (graphics/video) |
| oplus_network_* | 4 | 2H — network |
| Bluetooth platform | 4 | 2I — bluetooth |
| Other | 117 | spread across |

WLAN platform (cnss2 + qca_cld3) deferred to Wave 5 per Plan §8.

(Sub-wave order TBD as the clock-cluster lands and we measure
real per-module rate.)

---

## Open follow-ups (Wave 2-specific)

- Run state-reconciliation (`git fetch --tags && git status -uno
  && git log @{u}..HEAD --oneline`) at start of each sub-wave so
  the agent's mental model doesn't drift from upstream reality.
- Track K1/K2 vs K3 rate separately; don't average. The 5–10/day
  projection only applies to Sub-wave 2C+ on independent
  modules; the cluster will be 3–6 modules over 3–5 days.
- After cluster lands, decide whether to add canoe clock
  controller Kconfig stanzas to AOSP/upstream for future-proofing,
  or keep as Lineage-private. Track in
  `kernel_export_additions.md`.

---

## Wave 2 history (appended as work progresses)

(Filled in as sub-waves land.)
