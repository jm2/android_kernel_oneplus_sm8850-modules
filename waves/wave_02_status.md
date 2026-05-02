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

**Validator output** (3 modules, post-mka kernel install):

| Module | intree | vermagic_match | __versions | CRC match | KMI clean | Verdict |
|---|---|---|---:|---|---:|---|
| gcc-canoe | Y | yes | 19 | 19/19 | 100% | pass |
| dispcc-canoe | Y | yes | 38 | 38/38 | 100% | pass |
| camcc-canoe | Y | yes | 29 | 29/29 | 100% | pass |

All @ vermagic `6.12.23-4k-g6fc93520fed4-dirty`. `tools/jm2/
validate_module.sh` exits 0.

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
