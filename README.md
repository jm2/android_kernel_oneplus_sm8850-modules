# jm2/android_kernel_oneplus_sm8850-modules — Lineage source-build notes

External vendor module tree (`vendor/qcom/opensource/...`,
`vendor/oplus/...`, `vendor/nxp/...`) for OnePlus 15 (infiniti, SM8850)
under LineageOS 23.2. This fork carries the build-system fixes and the
oplus-extension wiring needed to compile each module via vendor/lineage's
`kernel.mk` per-module `make -C $kernel M=$module` flow, which is shaped
differently from vendor's Kleaf/Bazel pipeline.

## Quick start

Built as part of the LineageOS build via `mka kernel` (see the kernel
fork's `README.lineage.md`). To verify just this tree builds:

```bash
cd /home/jmulesa/android/lineage
source build/envsetup.sh
lunch lineage_infiniti-bp4a-userdebug
mka kernel
```

The 30 modules listed below are produced as `.ko` and installed under
`out/target/product/infiniti/obj/PACKAGING/kernel_modules_intermediates/lib/modules/<release>/updates/`.

## Status — 0 depmod symbol errors

Final state on `lineage-23.2`: kernel + 30 source-built external `.ko`
+ full 568 OEM prebuilts in `vendor_dlkm` flow into a depmod-clean
image. The six-phase plan that took the unresolved-symbol count from
110 → 0 is summarized below; commit messages on this branch hold the
detail.

## Source-built external modules

Order matters: vendor/lineage's `kernel.mk` builds `TARGET_KERNEL_EXT_MODULES`
sequentially and consumers reference earlier modules' `Module.symvers`
via `KBUILD_EXTRA_SYMBOLS`. The current ordering in
`device/oneplus/sm8850-common/BoardConfigCommon.mk` is:

```
oplus/kernel/device_info/oplus_fpga/fpga_monitor   → fpga_monitor.ko (kbuild)
oplus/kernel/boot/cmdline_parser                   → oplus_bsp_cmdline_parser.ko
oplus/kernel/boot/bootmode                         → oplus_bsp_bootmode.ko
oplus/kernel/boot/oplus_projectinfo/qcom           → oplus_bsp_boot_projectinfo.ko
oplus/kernel/power/standby_netlink                 → oplus_standby_netlink.ko
oplus/kernel/device_info/device_info               → device_info.ko
oplus/kernel/touchpanel/touchpanel_notify          → oplus_bsp_tp_notify.ko
qcom/opensource/mm-drivers/hfi_core                → msm_hfi_core.ko
qcom/opensource/mmrm-driver                        → msm-mmrm.ko
qcom/opensource/mm-drivers/hw_fence                → msm_hw_fence.ko
qcom/opensource/mm-drivers/msm_ext_display         → msm_ext_display.ko
qcom/opensource/mm-drivers/sync_fence              → sync_fence.ko
qcom/opensource/audio-kernel                       → audio_kernel suite
qcom/opensource/securemsm-kernel                   → 9 .ko (smcinvoke,
                                                     qseecom, tz_log,
                                                     qcrypto-msm, qce50,
                                                     hdcp_qseecom,
                                                     qcedev-mod, qrng,
                                                     smmu_proxy)
qcom/opensource/synx-kernel                        → synx-driver.ko,
                                                     ipclite.ko,
                                                     ipclite_test.ko
qcom/opensource/camera-kernel                      → camera.ko (with
                                                     full SPECTRA_OPLUS
                                                     extension surface)
qcom/opensource/data-kernel/drivers/smem-mailbox   → smem_mailbox.ko
qcom/opensource/datarmnet-ext/mem                  → rmnet_mem.ko
qcom/opensource/dataipa/drivers/platform/msm       → ipa.ko (suite)
qcom/opensource/datarmnet/core                     → rmnet_core.ko, rmnet_ctl.ko
qcom/opensource/datarmnet-ext/aps                  → rmnet_aps.ko
qcom/opensource/datarmnet-ext/offload              → rmnet_offload.ko
qcom/opensource/datarmnet-ext/shs                  → rmnet_shs.ko
qcom/opensource/datarmnet-ext/perf                 → rmnet_perf.ko
qcom/opensource/datarmnet-ext/perf_tether          → rmnet_perf_tether.ko
qcom/opensource/datarmnet-ext/sch                  → rmnet_sch.ko
qcom/opensource/datarmnet-ext/wlan                 → rmnet_wlan.ko
qcom/opensource/display-drivers/msm                → msm_drm.ko (with
                                                     full OPLUS_FEATURE_DISPLAY*
                                                     extension surface)
nxp/opensource/driver                              → nfc nci/secure_element
```

Specifically: `datarmnet-ext/shs` must come before `perf` and
`perf_tether`; the seven oplus boot/device-info entries must come
before `display-drivers/msm` (which links against
`get_project`, `get_PCB_Version`, `get_eng_version`, etc.).

## Falling through to OEM prebuilt

The OEM extract at `device/oneplus/infiniti-kernel/` (568 `.ko`)
flows in via `BOARD_VENDOR_KERNEL_MODULES` in the device repo. Where a
prebuilt has the same name as a source-built module, vendor/lineage's
`kernel.mk` runs the source-built install AFTER the prebuilt copy, so
the source-built version wins.

The remaining vendor subsystems still come from prebuilt for now:

```
qcom/opensource/dsp-kernel            → spf_core, audio_q6, etc.
qcom/opensource/eva-kernel            → msm-eva.ko
qcom/opensource/graphics-kernel       → msm.ko (KGSL)
qcom/opensource/spu-kernel            → spcom, spss_utils, etc.
qcom/opensource/video-driver          → msm_video.ko
qcom/opensource/wlan/platform         → cnss2, cnss_nl, wlan_firmware_service
qcom/opensource/wlan/qcacld-3.0       → qca_cld3_wlan.ko
qcom/opensource/bt-kernel             → bt-fm-driver.ko
oplus/* (everything not listed above)
```

These are stable-from-prebuilt today; the same six-phase pattern
(restore Kbuild + Makefile, bundle the right oplus extension sources,
add `KBUILD_EXTRA_SYMBOLS`, surface any in-tree dependencies) would
extend source-build to them if needed.

## Phase G — DTB source-compose for canoe SoC bases

vendor's Bazel build composes per-SoC fat .dtbs at DTC source time
(canoe[-v2|-tp|-tp-v2].dtsi + audio/sde/camera/eva/vidc/gpu/[dsp]/ipa/
synx/hw_fence/hfi_core/mmrm techpack .dtsi files all #included into
one /dts-v1/ wrapper). Kleaf wires this implicitly via the `kernel_dts`
rule. To match under plain make, this fork carries:

- **`subdir-y += qcom`** restored in
  `kernel_platform/qcom/opensource/devicetree/Makefile`
  (was disabled by an OPLUS_DTS_OVERLAY block).
- **14 symlinks** under `kernel_platform/qcom/opensource/devicetree/`
  pointing at the corresponding `vendor/qcom/opensource/<X>-devicetree`
  subprojects (audio / bt / camera / data / display / dsp / eSE / eva /
  graphics / mm / mmrm / nfc / synx / video). With these, a single
  in-tree `make dtbs` traverses qcom/, oplus/, and all 14 techpacks
  in one shot — no `M=` external-module invocations needed.
  The `subdir-y += $(foreach ...)` line in the same Makefile uses
  `$(wildcard $(d)/Kbuild)` guards so missing trees silently skip.
- **`canoe-{,v2,tp,tp-v2}-fat.dts`** in
  `kernel_platform/qcom/opensource/devicetree/qcom/`. Each is a
  /dts-v1/ wrapper that #includes its SoC .dtsi plus the SoC-level
  techpack .dtsi files OEM bakes into their dtb.img. Adds them to
  `dtb-y` with per-target `DTC_FLAGS_*-fat := -@` so DTC emits
  `__symbols__` (required for ABL's overlay phandle resolution).
  Validated label-equivalent to OEM oracle DTBs extracted from
  stock vendor_boot.img: 1922-1925/1923-1926 match per variant
  (only `qcom_qbt` missing — intentional, see fingerprint section).
- **`qcom/Makefile` drops `$(canoe-dtb-y)`** from `dtb-y`. That
  variable is the fdt_overlay-merged base × board matrix for
  non-infiniti boards (canoe-cdp/mtp/qrd/rcm/atp + alor variants);
  those overlays have stale node refs and fail with
  `FDT_ERR_NOTFOUND` at DTC time, and we don't ship those boards.
  `$(canoe-overlays-dtb-y)` still produces the bases + .dtbo files
  standalone for dtbo.img packing. Per-target `DTC_FLAGS_canoe* := -@`
  on the bases ensures `__symbols__` emission even when the
  base-dtb-y auto-derived list ends up empty.

The fingerprint label gap: OEM canoe.dtb has one extra label
`qcom_qbt → /soc/qcom,qbt_handler` for the legacy `qbt_handler.ko`
Qualcomm Biometric Touch driver. jm2 doesn't ship qbt_handler.ko
(not in our `TARGET_KERNEL_EXT_MODULES`), and OnePlus 15 actually
uses the modern OPLUS UFF stack (`oplus_bsp_uff_fp_driver.ko`,
binds `oplus,fp_spi`) defined in `oplus-uff-24831.dtsi` which is
part of the dtbo overlay (`infiniti-24831-canoe-overlay.dtbo`) —
ABL applies it at boot. So the missing label is a no-op for our
build.

Architectural rationale: ABL is the correct layer for overlay
resolution (correct symbol-propagating implementation that chains
overlays). Build-time tools (`fdtoverlay`, `fdtoverlaymerge`,
`ufdt_apply_overlay`) all share a `__symbols__`-propagation gap
that breaks chained-techpack devices (every post-SM8350 Qualcomm
SoC). OEM doesn't compose at build time either — they ship bases
in dtb.img and project + techpack overlays in dtbo.img and let
ABL apply at boot. This work mirrors that.

Companion changes in the device tree:
`device/oneplus/sm8850-common/{BoardConfigCommon.mk,dtbimg.mk,
dtboimg.mk,tools/dtb/}`. See that repo's README for the recipe and
oracle-diff tooling.

## Phases A–F — what changed and why

Each phase resolved a slice of the 110 unresolved-depmod-symbol set
that initially blocked a flashable image. Detail lives in commit
messages; this is the headline:

- **Phase A — kernel framework Kconfig restoration.** `rpmsg`,
  `remoteproc`, `gunyah`, `arm_scmi`, `qcom_smem_state`, `qcom_icc`
  Kconfig stanzas + Makefile entries that vendor's Kleaf flow
  expressed via `module_outs`. 110 → 25.
- **Phase B — oplus device-info modules wired in.** New Kbuild +
  Makefile pairs for `bootmode`, `cmdline_parser`,
  `oplus_projectinfo/qcom`, `standby_netlink`. Kernel-side companion
  shim `include/soc/oplus/boot/oplus_project.h` + `gh_arm_drv` bundle
  in `arch/arm64/gunyah/Makefile`. 25 → 17.
- **Phase C — camera-kernel oplus extension + soft-fail config.**
  `OPLUS_FEATURE_CAMERA_COMMON` define + 6 `drivers/oplus/...` sources
  bundled into `camera.ko` post-`camera-y :=` reset block.
  Kernel-side residuals (UFS CRYPTO QTI, arm64 gunyah Kconfig source,
  altmode-glink). Device-side `BOARD_KERNEL_MODULES_LOAD_ALLOW_MISSING`
  + `TARGET_AUTO_COLLECT_KERNEL_MODULE_DEPS`. 17 → 3, `mka kernel` exits 0.
- **Phase D — msm_drm.ko source-built with full oplus display
  surface.** 8 `OPLUS_FEATURE_DISPLAY*` defines + 24
  `oplus/SM8850/*.c` sources merged into `msm_drm-y` (post `camera-y :=`
  reset). New source-built modules: `device_info`,
  `oplus_bsp_tp_notify`, `msm_hfi_core`. Cross-module
  `KBUILD_EXTRA_SYMBOLS` chain wired through
  `display-drivers/msm/Makefile`.
- **Phase E retired.** The oplus extensions Phase E was going to stub
  for `gunyah_qtvm` turned out to be already covered by Phase A's
  `GUNYAH_QCOM_TRUSTED_VM` stanza.
- **Phase F — last 2 prebuilt symbols resolved.**
  `free_zram_is_ok` via in-tree stub linked into `zram.ko`;
  `__tracepoint_android_vh_scx_restore_flags` via `DECLARE_HOOK` +
  `EXPORT_TRACEPOINT_SYMBOL_GPL`. 3 → **0**. The `BOARD_VENDOR_KERNEL_MODULES`
  filter-out for `oplus_bsp_zram_opt.ko` / `oplus_bsp_sched_ext.ko`
  was dropped at the same time.

## Build-system fixes carried in this fork

Categories applied across modules in commits
`modules: build through 18 of TARGET_KERNEL_EXT_MODULES under mka kernel`
and `modules: build datarmnet/core + datarmnet-ext under mka kernel`:

1. **Missing `modules:` targets** — wrappers with only `all:` and
   `modules_install:`, no `modules:` rule and no `%:` catch-all,
   reported "No rule to make target 'modules'" since vendor/lineage's
   kernel.mk passes that target explicitly. Added `modules: all`
   shims to the affected wrappers.

2. **Cross-module `-I` paths** — Kbuilds patched per-module to add
   sibling-module include directories Kleaf would inject otherwise.

3. **Source-level shape mismatches** — vendor source predates clang 22
   in places (real `-Wuninitialized` bugs in `synx_util.c`/`synx.c`,
   `-Wunterminated-string-initialization` in `rmnet_vnd.c`,
   `-Wdefault-const-init-field-unsafe` in `sde_io_util.c`,
   non-`static-inline` stubs in headers causing link-time duplicate
   symbols). Demoted to warnings via `-Wno-error=...` for now;
   tracked for upstream cleanup.

4. **Path computation in wrappers** — `$(CURDIR)/../...` and
   `$(abspath $(CURDIR)/...)` instead of `$(KERNEL_SRC)/$(M)/...` /
   `$(M)/../$(...)` because under our absolute-`M=` invocation those
   double-prefix or fail to resolve.

5. **Bundle name collisions** — `MODULE = oplus_bsp_cmdline_parser`
   in the Kbuild had to differ from member `oplusboot.o` to avoid
   the bundle-vs-leaf same-name conflict that breaks kbuild's
   `-objs` linker step.

## Companion repos

- [`jm2/android_kernel_oneplus_sm8850`](../sm8850/) — kernel proper.
  See `README.lineage.md` for the genksyms prebuilt and the kernel-side
  Phase A/B/C/D/F patches.
- [`jm2/android_device_oneplus_sm8850-common`](../../device/oneplus/sm8850-common/) —
  device tree. `BoardConfigCommon.mk` drives the source-built vs
  prebuilt split via `TARGET_KERNEL_EXT_MODULES` and
  `BOARD_VENDOR_KERNEL_MODULES`.
- [`jm2/android_vendor_lineage`](../../../vendor/lineage/) — three local
  patches to `build/tasks/kernel.mk`. See its `README.lineage-jm2.md`.
