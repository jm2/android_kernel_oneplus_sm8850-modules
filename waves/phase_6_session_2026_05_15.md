# Phase 6 boot-failure investigation — session retro 2026-05-15

A long session that started chasing the OnePlus-15 LineageOS boot
failure (OnePlus logo + orange state for ½s → black screen, no ADB,
no recovery) via cmdline parity testing, pivoted into a stock-super
rabbit hole, then refocused onto the strategically-correct work:
re-validate Phase 2.5 Path B'', refresh the OEM-prebuilt blob set,
and ready the prebuilt-kernel path for hardware test.

This doc captures the load-bearing findings, the calibration lessons,
and the resulting backlog. Future sessions should read this alongside
`PHASE_6_FLASH_PREP.md`, `kmi_strict_audit.md`, and the new
`DEFERRED_FOLLOWUPS.md` entries.

## Bootlayer bisection — what we proved

Starting symptom: source-build boot.img bricks the boot stack;
restoring requires reflashing all of `{boot, init_boot, vendor_boot,
dtbo, recovery}` from stock.

### What's in our boot.img / vendor_boot.img vs stock

- `BOARD_BOOT_HEADER_VERSION := 4` puts our `BOARD_KERNEL_CMDLINE`
  into **vendor_boot.img** (not boot.img). Boot.img has empty
  `command line args:` and just carries the kernel binary. Edits
  to cmdline therefore only need `m vendorbootimage`, not `m bootimage`.
- Our stock-parity cmdline was wired at `BoardConfigCommon.mk:112-118`
  with `video=vfb:640x400,bpp=32,memsize=3072000` + `buildvariant=user`
  and removal of `nohugevmalloc` + `sysctl.kernel.firmware_config.force_sysfs_fallback=1`
  (the latter explicitly reverted upstream too — "Breaks recovery").
- `bootconfig` is auto-appended by the build system when `BOARD_BOOTCONFIG`
  is set; don't include it in `BOARD_KERNEL_CMDLINE` source.
- `BOARD_BOOTCONFIG` is **missing `androidboot.hypervisor.version=gunyah`**
  vs stock. One-line fix (see DEFERRED_FOLLOWUPS).

### Hybrid vendor_boot.img test on hardware

Unpacked stock `vendor_boot.img`, repacked stock components (ramdisk,
dtb, bootconfig — all SHA256-identical to stock) with our cmdline,
added AVB hash footer matching stock's salt + algorithm=NONE +
partition_size=100663296. Flashed alongside flashing stock super
attempts (both failed independently — see below).

**Result with our hybrid vendor_boot + stock super (when we got
super-of-some-kind working)**: device booted past kernel handoff,
displayed the generic AOSP "android" text bootanimation for some
seconds, then reboot-looped (Android rescue-party signature). This is
**many layers past the previous black-screen failure** — kernel
handoff works, vendor_ramdisk first-stage init works, late-init starts
running, bootanim service launches. The cmdline content is therefore
NOT the load-bearing cause of the original black-screen failure mode;
the original failure was much earlier in the kernel boot path.

The generic "android" splash (vs OxygenOS-branded) suggests
`/product/media/bootanimation.zip` wasn't mounted by the time bootanim
ran — either because our super.img is structurally wrong (most likely
candidate, since flashing pure stock vendor_boot + our super reproduced
the same failure) or because dm-verity tripped on a dynamic partition
hash mismatch.

### Stock super.img assembly (WON'T-DO)

Two attempts:

1. `build_super_image.py` from `out/host/linux-x86/bin/build_super_image`
   + a hand-written `stock_super_info.txt` pointing at
   `dump/stock_images/*.img`. Result: super.img with partitions marked
   `Attributes: none`. Booted to "android" splash → reboot.
2. Direct `lpmake` with `:readonly:` attributes (matching what
   LineageOS's normal build produces for its own super.img). Same
   metadata structure verified via `lpdump` (virtual_ab_device flag,
   3 metadata slots, A/B groups, all 14 partitions with readonly
   attrs). Same boot failure.

Root cause not fully understood. Closed as won't-do per user direction
("I don't even care if we get stock working through our infra at this
point"). **The OEM-prebuilt path bypasses super assembly entirely** —
uses the device's existing super partition contents — and is the
recommended working path. See DEFERRED_FOLLOWUPS "Hybrid super.img
assembly" for the partial-progress trail in case anyone needs to
revisit.

## Source-build first-stage module staging — the big finding

`out/.../obj/PACKAGING/depmod_vendor_ramdisk_intermediates/lib/modules/`
contains only 44 of the 97 modules listed in
`device/oneplus/sm8850-common/modules.list.msm.canoe`. Classification
of the 53 missing:

- **Bucket A** (load-list-naming mismatch, hyphen-variant already in
  staging): **0**.
- **Bucket B** (built into `vendor_dlkm/` but not staged into
  `vendor_ramdisk/`): **40**. Critical members include `ufs_qcom.ko`
  (storage host controller — without it kernel can't mount any
  partition, boot impossible regardless of cmdline), `iommu-logger`,
  `qcom_iommu_util`, `msm_dma_iommu_mapping`, `gic_intr_routing`,
  `memory_dump_v2`, `minidump`, `qcom_dma_heaps`, `sched-walt`,
  `qcom-reboot-reason`, `qcom-dload-mode`, `pmic-pon-log`,
  `bcl_pmic5`, `cpu_hotplug`.
- **Bucket C** (genuinely not built anywhere): **13**. Oplus boot
  stack (`oplusboot.ko`, `buildvariant.ko`, `boot_mode.ko`,
  `bootloader_log.ko`, `oplus_ftm_mode.ko`, `oplus_charger_present.ko`,
  `olc.ko`, `kernel_fb.ko`) + gunyah (`gunyah_loader.ko`,
  `gh_virt_wdt.ko`) + cpufreq (`qcom-cpufreq-hw.ko`,
  `qcom-cpufreq-thermal.ko`) + `cpu_phys_log_map.ko`.

**Root cause of Bucket B**: `BOARD_VENDOR_RAMDISK_KERNEL_MODULES` —
the AOSP variable that explicitly stages source-built `.ko` files
into vendor_ramdisk — is **never assigned** in
`BoardConfigCommon.mk`. Without it, only modules from
`BOARD_VENDOR_RAMDISK_KERNEL_MODULES_LOAD` that happen to be in
default staging end up there. Fix is a one-line edit (see
DEFERRED_FOLLOWUPS "Source-build vendor_ramdisk first-stage module
staging gap"). This is the highest-leverage source-build improvement
available: 40 free modules in one line.

**Without UFS_QCOM at first stage, the source-build path cannot boot
on any cmdline.** This explains why earlier source-build attempts hit
black-screen so early — the kernel was failing to bring up the storage
controller before any display init could run.

## Kernel-rebuild bypass / Path B'' re-validation

Discovery during boot-failure investigation: the shipped May-12
vmlinux (`out/.../obj/KERNEL_OBJ/vmlinux`) had IKCONFIG showing all 12
Path B'' debug-config flags still `=y` — meaning Path B'' was never
actually built into the binary that "tested" it. The
`production_profile.config` fragment was authored and committed to
`arch/arm64/configs/` but never wired into `TARGET_KERNEL_CONFIG` in
BoardConfigCommon.mk. Build's Kbuild config-merge step never saw the
fragment, .config content matched dev-baseline, Kbuild correctly
reused the existing Image. Ninja emitted `Missing restat?` warning
(surfacing the stale-mtime symptom but not the load-bearing root
cause). Audit script ran cleanly. Conclusion was internally consistent.
The failure mode was invisible from build output alone.

Re-validation procedure executed 2026-05-15:

1. Wired `production_profile.config` into `TARGET_KERNEL_CONFIG` as
   the last fragment (so `# CONFIG_X is not set` directives override
   prior fragments).
2. Forced rebuild via `m bootimage`.
3. **Pre-flight gate**: confirmed Image mtime advanced (May 12 → May 15)
   AND IKCONFIG-extracted from new vmlinux matches B'' intent (11 of
   13 flags flipped — `LIST_HARDENED` and `DEBUG_KERNEL` stayed `=y`
   per Kconfig select-chains in other fragments, exactly as the
   fragment's own docstring predicted).
4. Re-ran `tools/jm2/kmi_audit.py` with
   `--baseline-csv kmi_audit_20260511_path_b_pp.csv`.

**Result**: 0/557 OEM modules unlock from load-fail to load-clean. 0
regressions. 557 unchanged load-fail-module-layout. The Phase 2.5
"ACK skew is dominant, Path B is the path" conclusion was correct in
spirit; now empirically supported by a real measurement. Full evidence
trail in `kmi_strict_audit.md` "Re-validation 2026-05-15 — actual B''
measurement".

The build failed at depmod (cached source-built vendor_dlkm modules
carry stale `__versions` referencing KASAN/HARDENED_USERCOPY symbols
the new B''-flipped kernel doesn't export) — exactly what the
production_profile.config docstring predicted. Orthogonal to the audit
measurement (audit reads Module.symvers, which was produced cleanly).

## OEM-prebuilt path — re-readied for hardware test

`device/oneplus/sm8850-common/BoardConfigCommon.mk:529-565` already
has the `ifeq ($(BOARD_PREBUILT_KERNEL),true)` block correctly wired
(commit `f1e12df`, validated end-to-end at fallback_v6_clean per
DEFERRED_FOLLOWUPS). What was stale: the
`device/oneplus/infiniti-kernel/` blob set. SHA comparison:

| File | Apr 24 (old) | May 8 (device's current stock) |
|---|---|---|
| Image | `615f5dd9...` (39,164,416 B) | `2609ff52...` (39,889,408 B) |
| dtbo.img | unchanged checksum | refreshed |
| board_*.dtb | 8 files | 14 files |
| *.ko | 557 | 669 |

The Apr-24 blobs were from CPH2745_16.0.3.503(EX01); the device has
since received OTAs to a different OS image. Flashing Apr-24-derived
prebuilt boot.img against May-8-derived vendor_dlkm would create the
exact ABI mismatch the prebuilt approach is supposed to avoid.

Refreshed 2026-05-15 from `dump/stock_images/` (May 8 dump). Originals
backed up to `/tmp/ik_refresh/` for revert. Refresh procedure
documented in DEFERRED_FOLLOWUPS "Refresh device/oneplus/infiniti-kernel/
from current stock dump" — the EROFS system_dlkm and LZ4-cpio
vendor_ramdisk extraction steps in particular are non-obvious.

Next: build via `~/android/iter_brunch_fallback.sh <tag>`, verify
boot.img kernel SHA matches `2609ff5297e2...`, hand off for hardware
flash.

## Upstream community context

Cross-referenced against
`https://github.com/orgs/OnePlus-SM8850-Development/repositories`:

- All four sm8850 device trees (infiniti, macan, macanc, fairlady)
  default to `USE_PREBUILT_KERNEL ?= true` and have NO
  `BOARD_KERNEL_CMDLINE` defined — they ship the OEM prebuilt boot.img
  as-is. chandu078 commits "Switch to prebuilt kernel" (Apr 20 2026
  infiniti, May 13 2026 sm8850-common) made this the default. Their
  source-build path is the secondary path.
- Their source-build path uses `BOARD_USES_QCOM_MERGE_DTBS_SCRIPT := true`
  (whole-tree merge) rather than our 11 granular per-techpack overlays.
  See DEFERRED_FOLLOWUPS "Evaluate dtbo construction swap".
- Their kernel fragments are `vendor/pineapple_GKI.config +
  vendor/oplus/pineapple_GKI.config` (GKI-canonical) not our
  `canoe_perf` (perf variant). Possible future evaluation.
- `force_sysfs_fallback=1` was reverted from their cmdline May 15 too
  ("Breaks recovery") and moved to `init.qcom.recovery.rc` `on early-init`
  — our removal matches.
- Our `bb34d83a` depmod-bridge patch has no analogue in their
  `android_vendor_lineage` fork (they sidestepped via prebuilts).
  Novel value upstream-able if/when they re-engage source-build.

**Strategic implication**: pursuing source-build is swimming against
the community's current direction; expect to be the sole source of
fixes for source-build-path issues. Our work is valuable but won't
benefit from community PR momentum until/unless the community
re-engages source-build.

## Backlog after this session

See `DEFERRED_FOLLOWUPS.md` for the canonical list with full context.
Quick reference:

- **Pre-flight verification gate** (`tools/jm2/verify_kernel_config.py`)
  — codify the IKCONFIG-mtime check that caught the unmeasured B'';
  any future config-fragment work must pass this gate before its
  audit results are treated as load-bearing. **Highest priority.**
- **`BOARD_VENDOR_RAMDISK_KERNEL_MODULES` staging fix** — one-line
  edit that unlocks 40 first-stage modules including UFS_QCOM.
  **Required for any future source-build hardware test.**
- **`androidboot.hypervisor.version=gunyah` in BOARD_BOOTCONFIG** —
  one-line edit for stock parity.
- **Bucket C investigation** (13 not-built modules) — oplus boot stack
  regression check + gunyah / cpufreq wire-up scoping.
- **dtbo construction swap evaluation** — granular vs merge_dtbs;
  source-build path concern.
- **Task A — vendor blob IMEI/RIL completeness** — preventive vs
  community's IMEI-placeholder report.
- **Task B — DT2W scoping** in tp_hbp_syna_s3910 — preparation for
  post-MVB feature parity.
- **OEM-prebuilt hardware retest** — now that infiniti-kernel/ is
  current, build via iter_brunch_fallback.sh and validate boot.

## Process learning (what to carry forward)

1. **The unmeasured-config-flip failure mode is invisible without
   IKCONFIG verification.** Build output, audit output, and ninja
   logs all looked clean. Only IKCONFIG extraction from the shipped
   binary revealed the discrepancy. Codify this as a pre-flight gate.
2. **`m bootimage` invokes a kernel-build edge but Kbuild correctly
   reuses Image when .config content is unchanged.** The ninja
   `Missing restat?` warning is a build-system smell, not a bug.
3. **A/B partition layout matters more than image content for
   non-OEM super assembly.** Two attempts with the right metadata
   structure still failed — the byte-level partition layout has
   constraints we don't fully understand without an actual OEM
   super.img to compare against. Prefer OEM-prebuilt path; don't
   re-attempt stock-via-our-infra super assembly without a real
   reason.
4. **Calibration discipline applied within-session paid off** — the
   user's "the kernel-staleness finding is bigger than its placement
   suggests" intervention reframed the entire Phase 2.5 retro and led
   to the proper re-validation. The audit framework's value
   depended on this kind of calibration; future agents should
   actively look for "is this measurement actually measuring what we
   think it's measuring?" before treating any audit verdict as
   load-bearing.
