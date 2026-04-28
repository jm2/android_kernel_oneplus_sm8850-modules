# jm2/android_kernel_oneplus_sm8850-modules — Lineage source-build notes

External vendor module tree (`vendor/qcom/opensource/...`,
`vendor/oplus/...`, `vendor/nxp/...`) for OnePlus 15 (infiniti, SM8850)
under LineageOS 23.2. This fork carries the build-system fixes needed
to compile each module via vendor/lineage's `kernel.mk` per-module
`make -C $module M=$path` flow, which is shaped differently from
vendor's Kleaf/Bazel pipeline.

## Quick start

Built as part of the LineageOS build via `mka kernel` (see the kernel
fork's `README.lineage.md`). To verify just this tree builds:

```bash
cd /home/jmulesa/android/lineage
source build/envsetup.sh
lunch lineage_infiniti-bp4a-userdebug
mka kernel
```

The 26 modules listed under "Phase 2 — source-built" below are
produced as `.ko` and installed under
`out/target/product/infiniti/obj/PACKAGING/kernel_modules_intermediates/lib/modules/<release>/updates/`.

## Phase 2 — source-built (current state)

These build cleanly under `mka kernel` as of `lineage-23.2` HEAD:

```
qcom/opensource/mmrm-driver                       → msm-mmrm.ko
qcom/opensource/mm-drivers/hw_fence               → msm_hw_fence.ko
qcom/opensource/mm-drivers/msm_ext_display        → msm_ext_display.ko
qcom/opensource/mm-drivers/sync_fence             → sync_fence.ko
qcom/opensource/audio-kernel                      → audio_kernel suite
qcom/opensource/securemsm-kernel                  → 9 .ko (smcinvoke,
                                                    qseecom, tz_log,
                                                    qcrypto-msm,
                                                    qce50, hdcp_qseecom,
                                                    qcedev-mod, qrng,
                                                    smmu_proxy)
qcom/opensource/synx-kernel                       → synx-driver.ko,
                                                    ipclite.ko,
                                                    ipclite_test.ko
qcom/opensource/camera-kernel                     → camera.ko
qcom/opensource/data-kernel/drivers/smem-mailbox  → smem_mailbox.ko
qcom/opensource/dataipa/drivers/platform/msm      → ipa.ko (suite)
qcom/opensource/datarmnet/core                    → rmnet_core.ko, rmnet_ctl.ko
qcom/opensource/datarmnet-ext/aps                 → rmnet_aps.ko
qcom/opensource/datarmnet-ext/mem                 → rmnet_mem.ko
qcom/opensource/datarmnet-ext/offload             → rmnet_offload.ko
qcom/opensource/datarmnet-ext/perf                → rmnet_perf.ko
qcom/opensource/datarmnet-ext/perf_tether         → rmnet_perf_tether.ko
qcom/opensource/datarmnet-ext/sch                 → rmnet_sch.ko
qcom/opensource/datarmnet-ext/shs                 → rmnet_shs.ko
qcom/opensource/datarmnet-ext/wlan                → rmnet_wlan.ko
nxp/opensource/driver                             → nfc nci/secure_element
```

The order in `TARGET_KERNEL_EXT_MODULES` (in the device repo's
`BoardConfigCommon.mk`) matters because vendor/lineage's kernel.mk
builds them sequentially and consumers reference earlier modules'
`Module.symvers` via `KBUILD_EXTRA_SYMBOLS`. `datarmnet-ext/shs`
specifically must come before `perf` and `perf_tether`.

## Phase 2 — falling through to OEM prebuilt

These are excluded from `TARGET_KERNEL_EXT_MODULES` and instead come
from the OEM extract at `device/oneplus/infiniti-kernel/`, pulled in
via `BOARD_VENDOR_KERNEL_MODULES` in the device repo:

```
qcom/opensource/display-drivers/msm   → msm_drm.ko, dp/dsi/sde subsys
qcom/opensource/dsp-kernel            → spf_core, audio_q6, etc.
qcom/opensource/eva-kernel            → msm-eva.ko
qcom/opensource/graphics-kernel       → msm.ko (KGSL)
qcom/opensource/spu-kernel            → spcom, spss_utils, etc.
qcom/opensource/video-driver          → msm_video.ko
qcom/opensource/wlan/platform         → cnss2, cnss_nl, wlan_firmware_service
qcom/opensource/wlan/qcacld-3.0       → qca_cld3_wlan.ko
qcom/opensource/bt-kernel             → bt-fm-driver.ko
oplus/* (all entries in vendor/oplus/)
```

Each is blocked on a different missing piece — see "Phase 3" below
for what would unblock them.

## Phase 3 — completing the source-build

The blocker for each remaining module is documented here so a future
contributor (or future-you) can pick the lowest-hanging fruit first.

### display-drivers/msm

**Blocker:** depends on a large oplus extension API surface
(`oplus_ofp_*`, `oplus_adfr_*`, `oplus_apuir_*`, `oplus_display_ops`,
`trackpoint_report`) whose source files aren't shipped with the
LineageOS kernel/modules manifest. Vendor's Kleaf flow pulls these
in via additional `kernel_module(deps=[...])` references that resolve
to internal-only repos.

**WIP carried in this fork** (see commit
`display-drivers: Phase-3 WIP — partial source-build under mka kernel`):
- `vendor/qcom/opensource/display-drivers/msm/lineage_oplus_stub.c` —
  zero/false-returning stubs for `get_eng_version`, `oplus_ofp_*`,
  `oplus_display_ops` global, `oplus_display_trace_enable`. Enough
  to advance modpost past about 10 of the ~50 oplus-side undefined
  references.
- `vendor/qcom/opensource/display-drivers/msm/Kbuild` — adds `-I`
  paths for cross-module headers Vendor's Kleaf injects (mm-drivers/
  sync_fence + msm_ext_display, synx-kernel, oplus/{common,SM8850}/
  trackpoint+include), `-Wno-error=` for vendor source predating
  clang 22's stricter checks, `dp/edp_pll_4nm.o + 5nm.o` added to
  `msm_drm-y`.
- `vendor/qcom/opensource/display-drivers/msm/Makefile` —
  `DISPLAY_ROOT=$(CURDIR)/../` and `KBUILD_EXTRA_SYMBOLS` pointing at
  sibling synx, sync_fence, msm_ext_display, hw_fence, securemsm-
  kernel symvers.

**To finish source-building this**, you'd need to:

1. **Locate the missing oplus extension source.** Possible homes
   include:
   - The OnePlusOSS `kernel_platform/oplus/...` Bazel-only subtree
     (some pieces accessible via the OnePlusOSS GitHub orgs).
   - Vendor's full Kleaf manifest, accessible to OnePlus partners.
   - A different OplusOSS-shaped GitHub repo containing the
     `oplus_display.ko` / `oplus_adfr.ko` / `oplus_ofp.ko` source.
   Search GitHub for `oplus_ofp_is_supported` or `oplus_adfr_sa_handle`
   in C source — if the producer source surfaces, mirror it into
   `kernel/oneplus/sm8850-modules/vendor/oplus/kernel/display/...`
   or similar, give it a Kbuild + Makefile, add it to
   `TARGET_KERNEL_EXT_MODULES` in the device repo before
   `display-drivers/msm`.

2. **Wire cross-module dependencies.** Once oplus_display/ofp/adfr/etc.
   build, `display-drivers/msm/Makefile` needs `KBUILD_EXTRA_SYMBOLS`
   entries for each — pattern is the same as the existing entries for
   synx-kernel / mm-drivers / securemsm-kernel.

3. **Remove the stub.** Delete or guard
   `vendor/qcom/opensource/display-drivers/msm/lineage_oplus_stub.c`
   so the real oplus extension symbols win (they should produce the
   same EXPORT_SYMBOL names; modpost will flag duplicates).

4. **Re-add to TARGET_KERNEL_EXT_MODULES** in
   `device/oneplus/sm8850-common/BoardConfigCommon.mk`.

Per-module follow-up: once `display-drivers/msm` is source-built,
remove the corresponding `*.ko` files from the prebuilt set (or leave
them — source-built install overwrites at depmod time).

### dsp-kernel / eva-kernel / graphics-kernel / spu-kernel / video-driver

Each of these is in the same shape as `display-drivers/msm` — vendor
Kleaf injects cross-module `-I`s plus deps on internal-only oplus
extension modules. The same Phase-3 procedure applies:

1. Source for the missing modules.
2. Cross-module include paths.
3. KBUILD_EXTRA_SYMBOLS chain.
4. Move from `BOARD_VENDOR_KERNEL_MODULES` (prebuilt) to
   `TARGET_KERNEL_EXT_MODULES` (source-built) in the device repo.

These modules also each have their own Bazel-shape vs make-shape
mismatches similar to what's already fixed in `datarmnet/core` and
`audio-kernel` — `MODNAME` sentinel for kbuild-vs-standalone branches,
relative-vs-absolute path issues in wrapper Makefiles, missing
`modules:` rules. Follow the patterns established in:

- `vendor/qcom/opensource/audio-kernel/Makefile` — `MODNAME` sentinel
  pinned in `KBUILD_OPTIONS` to short-circuit the Kbuild's
  `obj-y += ./` self-recursion.
- `vendor/qcom/opensource/datarmnet/core/Kbuild` — cross-module
  `-I`s for `<linux/ipa.h>`, `<linux/msm_ipa.h>` from
  `dataipa/drivers/platform/msm/include[/uapi]`, and
  `-DRMNET_TRACE_INCLUDE_PATH=$(src)` overriding the relative
  `../../../../...` vendor path.
- `vendor/qcom/opensource/datarmnet-ext/perf/Makefile` —
  `$(abspath $(CURDIR)/../../...)` for KBUILD_EXTRA_SYMBOLS so
  symvers paths resolve regardless of how vendor/lineage's kernel.mk
  passes `M=`.

### wlan/{platform,qcacld-3.0}, bt-kernel, nxp

`wlan/qcacld-3.0` in particular is a large source tree with many
config gates and its own KBUILD machinery. Likely worth doing last;
the OEM prebuilt has a known-good Wi-Fi driver and source-building
this without breaking it is non-trivial.

### oplus/* family

These are the smallest-surface modules but the most numerous. Each
has its own Kbuild + Makefile pair that may or may not have the
common shape issues. Walk through each in
`BoardConfigCommon.mk:TARGET_KERNEL_EXT_MODULES` once you have the
missing oplus extension producers wired up — many of these consume
each other through internal headers that vendor's Kleaf cross-injects.

## Build-system fixes carried in this fork

Categories applied across modules in commit
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

## Companion repos

- [`jm2/android_kernel_oneplus_sm8850`](../sm8850/) — kernel proper.
  See its `README.lineage.md` for the genksyms prebuilt and other
  kernel-side patches.
- [`jm2/android_device_oneplus_sm8850-common`](../sm8850-common/) —
  device tree. `BoardConfigCommon.mk` declares which modules in this
  tree to source-build (`TARGET_KERNEL_EXT_MODULES`) vs which to fall
  through to OEM prebuilts (`BOARD_VENDOR_KERNEL_MODULES`).
