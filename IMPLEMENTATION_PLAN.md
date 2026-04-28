# Implementation plan — full source-build (Path 1)

Goal: produce a flashable LineageOS 23.2 zip for OnePlus 15 (infiniti)
with **all** kernel modules source-built, no OEM prebuilt fallback.
Replaces the hybrid `BOARD_VENDOR_KERNEL_MODULES` wildcard approach
documented in `README.md` § Phase 3.

This plan is the result of reconnaissance documented at the bottom
(audit trail). The headline finding: the oplus extension source we
thought was missing is **already in this repo** under
`vendor/oplus/kernel/` and `vendor/qcom/opensource/*/oplus/SM8850/`,
pulled in by the `c1134b3c` vendor sync commit. The work remaining is
build-system wiring, not source acquisition.

## Status snapshot

**Phase A: ✅ DONE** (commit `f62dc1fcc33c kernel: Phase A — restore
RPMSG/REMOTEPROC/GUNYAH/SCMI/SMEM/ICC framework`). Kernel builds
cleanly. Symbols `rproc_*`, `rpmsg_*`, `gunyah_*`, `scmi_*`,
`qcom_smem_state_*`, `qcom_icc_xlate_extended`, plus their helpers
(qcom_ramdump, qcom_tracepoints, mem-prot, icc-debug,
qcom_glink_memshare) all resolve. Also re-enabled `KASAN_HW_TAGS`
(safe alongside KASAN_GENERIC=n) which resolved 12 prebuilts'
references to `kasan_flag_enabled`.

**Phase B: ✅ DONE** (commits `def93a18 modules: Phase B — wire oplus
boot helpers + standby_netlink`, `24069d6 sm8850-common: Phase B`,
`b178c170b3df kernel: Phase B kernel-side support — gh_arm_drv bundle
+ oplus_project.h shim`, `4e196512 kernel.mk: wipe stale oem/`).
Source-built four oplus extension modules:
- `oplus_bsp_bootmode.ko` — `get_boot_mode`, `op_is_monitorable_boot`
- `oplus_bsp_cmdline_parser.ko` — `verified_bootstate`, `serial_no`,
  `md_buffersize`, plus inter-module helpers
- `oplus_bsp_boot_projectinfo.ko` — `get_project`, `get_PCB_Version`,
  `get_eng_version`, `get_Operator_Version`, `get_Modem_Version`
- `oplus_standby_netlink.ko` — `reset_oplus_smp2p_state`,
  `get_oplus_smp2p_state_list`, `get_suspend_clk_list`

Plus restored `gh_arm_drv.ko` bundle in `arch/arm64/gunyah/Makefile`
(referenced by modules.list.msm.canoe and load.recovery).

**Current state:** kernel + 30 source-built externals. Depmod down
from 110 → 17 unresolved across 4 modules:
- `camera_extension.ko` (~13 cam_* symbols — Phase C)
- `oplus_bsp_zram_opt.ko` (`free_zram_is_ok` — needs hybridswap_zram)
- `oplus_bsp_sched_ext.ko` (`__tracepoint_android_vh_scx_restore_flags`)
- `ufshcd-crypto-qti.ko` (`qcom_ice_program_key_hwkm`)

**Phases C/D** still resolve the camera and display clusters. Phase B+
has small follow-ups (zram_opt's hybridswap producer, sched_ext
tracepoint, ICE crypto helper).

## Symbol-to-task mapping

The 110 missing symbols cluster into 6 buckets, each addressed by one
phase below:

| # | Bucket | Symbols | Resolved by |
|---|--------|---------|-------------|
| 1 | `rproc_*`, `devm_rproc_*` | 19 | Phase A — kernel Kconfig restoration |
| 2 | `rpmsg_*`, `__register_rpmsg_driver` | 8 | Phase A |
| 3 | `gunyah_*` (RM, hypercall) | 9 | Phase A |
| 4 | `scmi_*`, `qcom_smem_state_*`, `qcom_icc_*` | 8 | Phase A |
| 5 | Group A oplus device-info (`get_boot_mode`, `verified_bootstate`, `get_project`, `get_PCB_Version`, `get_eng_version`, `op_is_monitorable_boot`, `serial_no`, `GetFileName`, `get_Modem_Version`, `get_Operator_Version`) | ~10 | Phase B — wire oplus device-info modules |
| 6 | `cam_*`, `camera_io_*`, `oplus_cam_*`, camera tracepoints | 40 | Phase C — wire oplus camera extension into camera-kernel |
| 7 | `oplus_display_ops`, `oplus_ofp_*`, `oplus_adfr_*`, `oplus_apuir_*`, `oplus_display_trace_enable` | ~15 | Phase D — wire oplus display extension into display-drivers/msm |
| 8 | `gunyah_qtvm_*`, `__tracepoint_send_alloc_req`, `__tracepoint_receive_relinquish_resp_msg` | ~5 | Phase E — stub gunyah_qtvm |
| 9 | Misc residual (`reset_oplus_smp2p_state`, `dump_tof_registers`, `kasan_flag_enabled`, etc.) | ~6 | Phase F — triage |

Phase order is dependency-driven: A unblocks every vendor prebuilt that
consumes kernel framework symbols; B–E unblock specific subsystems; F
mops up the residual.

---

## Phase A — kernel Kconfig stanza restoration

**Repo:** `kernel/oneplus/sm8850`
**Estimated complexity:** mechanical, single commit, single rebuild.
**Resolves:** 44 symbols across rpmsg / remoteproc / gunyah / scmi /
qcom_smem_state / qcom_icc.

### What's wrong

Vendor's Kleaf flow forces these subsystems to compile via
`module_outs` in BUILD.bazel and stripped the matching `config X`
entries from Kconfig (a pattern we've already addressed for
`drivers/soc/qcom/`, `drivers/iommu/`, etc.). The Makefiles still
reference `obj-$(CONFIG_X) += foo.o` but `config X` doesn't exist, so
kbuild silently drops these.

Audit confirmed (audit #1 below): the recent OnePlusOSS merge
(`02fca616f1a1`) brought 105 files of Kconfig restorations elsewhere
in the tree but did **not** touch `drivers/rpmsg/Kconfig`,
`drivers/remoteproc/Kconfig`, `drivers/virt/gunyah/Kconfig`,
`drivers/firmware/arm_scmi/Kconfig`, `drivers/soc/qcom/Kconfig`
(smem_state piece), or `drivers/interconnect/qcom/Kconfig`. We do this
manually.

### Tasks

- [x] **A.1** — `drivers/rpmsg/Kconfig`: restore `config RPMSG`,
  `config RPMSG_NS`, `config RPMSG_CHAR`, `config RPMSG_CTRL`,
  `config RPMSG_VIRTIO`, `config RPMSG_QCOM_GLINK_RPM`. Source:
  upstream Linux 6.12 ACK (android-mainline `drivers/rpmsg/Kconfig`).
  Pin the resulting config in `lineage_genksyms_workaround.config`:
  `CONFIG_RPMSG=m`, `CONFIG_RPMSG_CHAR=m`, `CONFIG_RPMSG_CTRL=m`,
  `CONFIG_RPMSG_NS=m`.

- [x] **A.2** — `drivers/remoteproc/Kconfig`: restore `config
  REMOTEPROC` and `config REMOTEPROC_CDEV`. Pin
  `CONFIG_REMOTEPROC=y` (vmlinux export — vendor prebuilts assume
  in-kernel, not modular).

- [x] **A.3** — `drivers/virt/gunyah/Kconfig`: restore `config
  GUNYAH`, `config GUNYAH_DRIVERS`, `config GUNYAH_VCPU`. Pin
  `CONFIG_GUNYAH=y` and dependents.

- [x] **A.4** — `drivers/firmware/arm_scmi/Kconfig`: restore `config
  ARM_SCMI_PROTOCOL`, `config ARM_SCMI_RAW_MODE_SUPPORT` (already
  partial). Pin `CONFIG_ARM_SCMI_PROTOCOL=y`.

- [x] **A.5** — `drivers/soc/qcom/Kconfig`: restore `config
  QCOM_SMEM_STATE` (probably exists — audit suggests the symbol
  *export* is what's missing, may just need `obj-$(CONFIG_QCOM_SMEM)`
  in Makefile to build `smem_state.c`).

- [x] **A.6** — `drivers/interconnect/qcom/Kconfig`: restore `config
  INTERCONNECT_QCOM_RPMH` and the helper that exports
  `qcom_icc_xlate_extended`.

- [x] **A.7** — Build, verify Module.symvers contains
  `rpmsg_send`, `rproc_alloc`, `gunyah_rm_call`,
  `qcom_smem_state_get`, `scmi_driver_register`,
  `qcom_icc_xlate_extended`. Re-run depmod and confirm the 44 symbols
  in buckets 1–4 above are resolved.

**Single commit message format**: `kernel: restore RPMSG/REMOTEPROC/GUNYAH/SCMI/QCOM_SMEM/QCOM_ICC Kconfig stanzas`

---

## Phase B — oplus device-info modules

**Repo:** `kernel/oneplus/sm8850-modules` + `device/oneplus/sm8850-common`
**Resolves:** Group A (10 symbols).

### What's there

Audit #3 confirmed all symbols have producer files in-tree:

```
vendor/oplus/kernel/boot/bootmode/boot_mode.c               → get_boot_mode, op_is_monitorable_boot
vendor/oplus/kernel/boot/cmdline_parser/oplusboot.c         → verified_bootstate
vendor/oplus/kernel/boot/oplus_projectinfo/qcom/oplus_project.c → get_project, get_PCB_Version, get_Modem_Version, get_Operator_Version, get_eng_version
vendor/oplus/kernel/boot/cmdline_parser/{buildvariant,oplus_charger_present,oplus_ftm_mode,saupwk,cdt_integrity,oplus_bootargs}.c → assorted boot helpers
vendor/oplus/kernel/device_info/device_info/device_info.c   → serial_no, GetFileName (likely)
```

Audit #2 found the `boot/` subdirs have **no Kbuild and no Makefile** —
vendor only ships `BUILD.bazel` for these. We write Kbuilds.

### Tasks

- [x] **B.1** — Write `vendor/oplus/kernel/boot/bootmode/Kbuild` +
  `Makefile` (one module, `oplus_bsp_bootmode.ko`, sources `boot_mode.c`).
  Pattern to follow: `vendor/oplus/kernel/hans/Kbuild` (the rare
  oplus subdir that has both today).

- [x] **B.2** — Write `vendor/oplus/kernel/boot/cmdline_parser/Kbuild`
  + `Makefile` (one module `oplus_bsp_cmdline_parser.ko`, includes
  oplusboot.c + buildvariant.c + oplus_bootargs.c + cdt_integrity.c +
  oplus_charger_present.c + oplus_ftm_mode.c + saupwk.c).

- [x] **B.3** — Write `vendor/oplus/kernel/boot/oplus_projectinfo/qcom/Kbuild`
  + `Makefile` (one module `oplus_bsp_boot_projectinfo.ko`,
  source `oplus_project.c`).

- [ ] **B.4** — `vendor/oplus/kernel/device_info/device_info/` already
  has `Makefile` (audit #2). Check whether it builds standalone;
  add to ext-modules list as-is. If symbols don't export, audit the
  Kbuild and add `EXPORT_SYMBOL` directives or a wrapper Kbuild.

- [x] **B.5** — Add to `device/oneplus/sm8850-common/BoardConfigCommon.mk`
  `TARGET_KERNEL_EXT_MODULES` in this order (no cross-module deps
  between them, but they must all be earlier than any consumer):

  ```
  oplus/kernel/boot/bootmode \
  oplus/kernel/boot/cmdline_parser \
  oplus/kernel/boot/oplus_projectinfo/qcom \
  oplus/kernel/device_info/device_info \
  ```

- [x] **B.6** — Build. Confirm `oplus_bsp_bootmode.ko`,
  `oplus_bsp_cmdline_parser.ko`, `oplus_bsp_boot_projectinfo.ko`,
  `oplus_bsp_device_info.ko` appear in updates/. Run depmod, confirm
  Group A symbols resolve.

---

## Phase C — oplus camera extension wired into camera-kernel

**Repo:** `kernel/oneplus/sm8850-modules`
**Resolves:** Group C (~40 symbols, the largest cluster).

### What's there

`vendor/qcom/opensource/camera-kernel/drivers/oplus/cam_sensor_module/`
holds 7 oplus camera extension `.c` files
(`oplus_cam_actuator.c`, `oplus_cam_eeprom.c`, `oplus_cam_ois.c`,
`oplus_cam_sensor.c`, `oplus_cam_insensor_eeprom.c`,
`cam_kevent_fb_custom.c`, `cam_trace_custom.c`).

Audit #3 traced `oplus_cam_actuator_construct_default_power_setting`
to `oplus_cam_actuator.c`. The other ~40 cam_* symbols come from a
mix of these files plus camera-kernel's own files that aren't
currently being built (gated by `OPLUS_FEATURE_CAMERA_COMMON`).

`camera_modules.bzl` shows vendor's Kleaf includes these under the
`OPLUS_FEATURE_CAMERA_COMMON` define plus an explicit source list. Our
Kbuild needs the same.

### Tasks

- [ ] **C.1** — Read `camera_modules.bzl` lines 280–310 to extract the
  full source list under `OPLUS_FEATURE_CAMERA_COMMON`. Add those as
  an `OPLUS_FEATURE_CAMERA_COMMON-y` block in the camera-kernel
  parent Kbuild.

- [ ] **C.2** — Add `-DOPLUS_FEATURE_CAMERA_COMMON
  -DFEATURE_ENABLE=1` to `ccflags-y` (mirrors `local_defines` in
  Bazel).

- [ ] **C.3** — Verify `canoe_defconfig` (camera-kernel's, not the
  arch one) has the right `#ifdef OPLUS_FEATURE_CAMERA_COMMON`
  blocks unbroken — audit found references at line 13.

- [ ] **C.4** — Build. The existing
  `qcom/opensource/camera-kernel` entry in
  `TARGET_KERNEL_EXT_MODULES` doesn't change; just the Kbuild
  expands. Confirm `camera.ko` Module.symvers now exports `cam_*`,
  `camera_io_*`, and oplus camera helpers.

- [ ] **C.5** — Re-run depmod against the OEM prebuilt set; confirm
  Group C cluster resolved.

---

## Phase D — oplus display extension wired into display-drivers/msm

**Repo:** `kernel/oneplus/sm8850-modules` + `device/oneplus/sm8850-common`
**Resolves:** Group B (~15 symbols), unblocks Phase 3 README's
`display-drivers/msm` line item.

### What's there

`vendor/qcom/opensource/display-drivers/oplus/SM8850/` has:
- `oplus_adfr.c` — `oplus_adfr_*` family
- `oplus_apuirdim.c` — `oplus_apuir_*` family
- `oplus_onscreenfingerprint.c` — `oplus_ofp_*` family
- `oplus_display_interface.c` — `oplus_display_ops` global
- `oplus_display_sysfs_attrs.c` — `oplus_display_trace_enable`
- ~20 other `oplus_display_*.c`

Existing `display-drivers/msm/Kbuild` (Phase 3 WIP commit
`4ab15b1d`) already pulls some headers but uses
`lineage_oplus_stub.c` as a placeholder. This phase replaces stubs
with real source.

### Tasks

- [ ] **D.1** — Inventory all `.c` files in
  `vendor/qcom/opensource/display-drivers/oplus/SM8850/`.
  Cross-reference against `display-drivers/msm/Kbuild`'s msm_drm-y
  list — anything mentioned but not added today is the work.

- [ ] **D.2** — Extend `display-drivers/msm/Kbuild`'s `msm_drm-y` to
  include the SM8850 oplus tree's `.c` files. Pattern: each goes in
  with a `$(CONFIG_DRM_MSM)` gate to match upstream.

- [ ] **D.3** — Delete `lineage_oplus_stub.c` (currently linked into
  msm_drm-y). The real symbols replace the stubs.

- [ ] **D.4** — Likely cross-module dep: oplus_display calls into
  oplus device-info (Phase B) for `get_project` etc. If
  display-drivers/msm builds before oplus_bsp_boot_projectinfo, the
  symvers won't be available. Order in TARGET_KERNEL_EXT_MODULES:
  Phase B modules first, then display-drivers/msm.

- [ ] **D.5** — Move `qcom/opensource/display-drivers/msm` from the
  "Phase 2 falls through to OEM prebuilt" set to
  `TARGET_KERNEL_EXT_MODULES` in BoardConfigCommon.mk.

- [ ] **D.6** — Build. Confirm `msm_drm.ko` produced, exports
  `oplus_ofp_*`, `oplus_adfr_*`, `oplus_apuir_*`, `oplus_display_ops`.

---

## Phase E — gunyah_qtvm stubs

**Repo:** `kernel/oneplus/sm8850`
**Resolves:** Group D (5 symbols).

### Why stub

Audit #4 (the GitHub recon agent) and audit #2 (local search)
both confirm: gunyah_qtvm is **not present** anywhere in OnePlusOSS or
locally. It's a vendor-internal blob. Without source, we either drop
the consumers or stub.

The consumers: a small set of OEM prebuilts (one or two `.ko`) that
register/unregister with gunyah_qtvm notifiers. They likely degrade
gracefully when the notifier returns "not registered" — common pattern
for QTVM (Qualcomm Trusted VM) that only matters when a TVM is
running, which it isn't on a normal user device.

### Tasks

- [ ] **E.1** — Create
  `drivers/virt/gunyah/qtvm_stub.c` with no-op
  `gunyah_qtvm_register_notifier`, `gunyah_qtvm_unregister_notifier`,
  plus `DEFINE_TRACE` for `send_alloc_req`,
  `receive_relinquish_resp_msg` (and any other tracepoints surfaced
  by Phase E rebuild).

- [ ] **E.2** — Add `obj-$(CONFIG_GUNYAH) += qtvm_stub.o` to
  `drivers/virt/gunyah/Makefile`.

- [ ] **E.3** — `EXPORT_SYMBOL_GPL` for each stub function /
  tracepoint.

- [ ] **E.4** — Rebuild, confirm Module.symvers contains the
  symbols. If a future contributor finds real qtvm source, replace
  the stub.

---

## Phase F — residual triage

**Resolves:** ~6 leftover symbols.

Run depmod after Phases A–E. Whatever's left is small. Triage each:

- **`reset_oplus_smp2p_state`, `get_oplus_smp2p_state_list`** — likely
  in `vendor/oplus/kernel/ipc/` or `device_info/`. Local grep first;
  if found, add to TARGET_KERNEL_EXT_MODULES.
- **`dump_tof_registers`** — touchpanel ToF sensor; check
  `vendor/oplus/kernel/touchpanel/`. If the consumer module isn't
  needed (peripheral) and the symbol provider isn't easily found,
  drop the consumer from modules.load.
- **`kasan_flag_enabled`** — KASAN compile leftover in some prebuilt;
  we have `# CONFIG_KASAN is not set`. Likely safe to drop the
  consumer module.
- **`md_buffersize`, `delete_request`, `cam_handle_mem_ptr`,
  `free_zram_is_ok`** — case-by-case, mostly small.

---

## Decision points along the way

After each phase rebuild, count remaining unresolved symbols. If a
phase produces materially more failures than it fixes (e.g., Phase A
restoration breaks an existing build), pause and reassess — that's
the signal to consider pivoting back to dodge.

Hard cliff to watch for: Phase D could surface that the SM8850 oplus
display extension code references additional vendor-internal headers
not in our tree. If so, it's the same shape as gunyah_qtvm — drop
display-drivers/msm to OEM prebuilt and accept the lost surface
(though we'd lose oplus display features like ADFR / OFP / APUIR).

---

## What this plan does **not** do

- Wire up audio-kernel-ar (oplus audio path) — not in our 110-symbol
  set, can stay on the existing audio-kernel source-build.
- Wire up wlan/qcacld-3.0 — large, ABI-stable enough to stay on OEM
  prebuilt, not blocking depmod.
- Phase 3 README's mention of "wlan/platform" / "bt-kernel" — these
  are stable from prebuilt; not in the 110.
- Touchpanel / charger oplus subsystems — these have local Makefiles
  per audit #2, and if they're not in our 110 symbols it's because
  they're either built today or covered by prebuilts.

---

## Estimated wallclock

Each phase = read source, write Kbuild, add to ext-modules list,
rebuild (~3 min per `mka kernel` iteration once warm), verify
depmod. Phase A is one rebuild; Phases B–E are 1–2 rebuilds each.

Best case (everything wires cleanly first try): ~4–6 hours.
Realistic (one false start per phase): 1–2 days.
Worst case (Phase D hits hidden vendor headers): pivot to dodge for
display only, accept the loss.

---

## Audit trail

Findings that produced this plan, kept here so a future contributor
can re-run them after a manifest sync:

### Audit #1 — Kconfig restoration scope (kernel side)

Run from `kernel/oneplus/sm8850`:

```bash
git log --oneline 24c3c52e4f95..02fca616f1a1 -- \
  drivers/rpmsg/Kconfig drivers/remoteproc/Kconfig \
  drivers/virt/gunyah/Kconfig drivers/firmware/arm_scmi/Kconfig \
  drivers/soc/qcom/Kconfig drivers/interconnect/qcom/Kconfig
```

Result: empty (the 105-file OnePlusOSS merge skipped these).

```bash
grep -n "^config RPMSG$\|^config REMOTEPROC$\|^config GUNYAH$" \
  drivers/rpmsg/Kconfig drivers/remoteproc/Kconfig \
  drivers/virt/gunyah/Kconfig
```

Result: empty (config stanzas still stripped → Phase A is real work).

### Audit #2 — oplus subdir build wiring

Run from `kernel/oneplus/sm8850-modules`:

```bash
for d in $(find vendor/oplus/kernel -maxdepth 4 -type d); do
  has_kbuild=$([ -f "$d/Kbuild" ] && echo Kb || echo "  ")
  has_makefile=$([ -f "$d/Makefile" ] && echo Mf || echo "  ")
  has_bazel=$([ -f "$d/BUILD.bazel" ] && echo Bz || echo "  ")
  has_c=$(ls "$d"/*.c 2>/dev/null | wc -l)
  [ "$has_c" -gt 0 ] || [ -f "$d/Kbuild" ] || [ -f "$d/BUILD.bazel" ] && \
    echo "$has_kbuild $has_makefile $has_bazel ${has_c}c $d"
done
```

Key result: `vendor/oplus/kernel/boot/bootmode/`,
`boot/cmdline_parser/`, `boot/oplus_projectinfo/qcom/` all have
**only `.c` files, no Kbuild and no BUILD.bazel.** Phase B writes
those Kbuilds.

### Audit #3 — symbol-to-producer mapping

Group A producers (10 symbols → 4 candidate modules) all confirmed.
Group B producers (15 symbols) all in `display-drivers/oplus/SM8850/`.
Group C producer (40 symbols, including base camera ABI) confirmed in
`camera-kernel/drivers/oplus/cam_sensor_module/`.

### Audit #4 — GitHub reconnaissance for missing symbol producers

Performed by general-purpose agent. Finding:
`OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8850@oneplus/sm8850_b_16.0.0_oneplus_15`
is the upstream repo for everything in our `vendor/oplus/kernel/`. The
`c1134b3c` "Synchronize code for OnePlus CPH2745…" commit pulled the
full subtree into our local tree already. Group D (gunyah_qtvm) not
found anywhere → Phase E stub strategy.

---

## Companion files

- `README.md` (this directory) — overview, Phase 2 source-built list,
  Phase 3 hybrid procedure (now superseded for the "find oplus
  source" portion by this plan).
- `../sm8850/README.lineage.md` — kernel source-build patches.
- `../../device/oneplus/sm8850-common/README.md` — device tree
  build wiring.
- `../../vendor/lineage/README.lineage-jm2.md` — vendor/lineage local
  patch (mka external module wrapper fix).
