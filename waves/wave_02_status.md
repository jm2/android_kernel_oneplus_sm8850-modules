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
30 → 34. Next: sub-wave 2D (oplus_bsp_*, 28 modules) per the
recalibrated wave plan. Decision on signature-mismatch checker
deferred until after 2D.

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
