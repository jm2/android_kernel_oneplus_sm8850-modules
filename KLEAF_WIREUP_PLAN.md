# LOS ↔ OEM-Kleaf wire-up plan (step d) — built as a reusable adapter

**Status: IMPLEMENTED + COMMITTED 2026-06-09. Parts B/A/D done + parse-validated; Part C
done COMPREHENSIVELY — not just WLAN: the full stock-parity module set (644 .ko, 0 missing
vs all four stock load lists) builds source-side against the canoe_perf kernel. See
"## IMPLEMENTATION RESULTS" and "## COMPREHENSIVENESS RESULTS" at the end. Commits:
jm2 vendor/lineage `ce094def` (adapter, patch 5) + `9fecd801` (tolerant staging, patch 6);
jm2 sm8850-common `ae416ee` (BoardConfig + build-canoe-kleaf.sh + known-source-gaps.txt).
Remaining: Part E (brunch + flash + verify on hardware) + fork the OEM modules repo for
the cnss2 patch (DEFERRED_FOLLOWUPS).**

**(Original PLAN of 2026-06-08 preserved below; the results section records what actually
landed and the deltas from the plan.)**
Prereq DONE: the OEM Kleaf kernel builds (`canoe_perf`, RC=0 — see `KLEAF_PIVOT.md` §"STEP (c)
RESULT") and the cnss2 byte-reversed-MAC fix is committed (`21fae367`,
`vendor/qcom/opensource/wlan/platform/cnss2/qmi.c`). This doc is the plan to make a LineageOS
`brunch` (with `USE_PREBUILT_KERNEL=false`) drive that OEM Kleaf build and load the patched WLAN
modules — designed as **generic tooling** so future devices on the Kleaf path are plug-and-play,
with canoe/infiniti as consumer #1.

## Goal & locked decisions

Goal: a `brunch infiniti` with `USE_PREBUILT_KERNEL=false` produces a boot.img + vendor_dlkm whose
kernel = the OEM Kleaf `canoe_perf` build and whose WLAN modules = our source (incl. the cnss2 MAC
fix), with KMI/CRCs matching (that was the entire point of the pivot). Build the bridge **once,
generically**; canoe just sets a few vars.

User decisions (2026-06-08):
1. **Build driver = the OEM wrapper** `kernel_platform/oplus/build/oplus_build_kernel.sh <plat> <variant>`
   (proven end-to-end) — NOT a reconstructed bare `bazel run`. The adapter calls the wrapper and
   maps its `dist/` output into LineageOS's `KERNEL_OUT`.
2. **WLAN/cnss2 = the correct DDK path** — build cnss2/qcacld (incl. the patched cnss2) as Kleaf
   **`ddk_module`s** against the canoe `kernel_build`, so the CRCs match the OEM kernel. NOT the
   interim "dist-as-prebuilt + side-build" shortcut.

## The two structural gaps the adapter must absorb (the reusable findings)

QC-OEM Kleaf tree shape (OnePlusOSS; expected to generalize to other QC OEMs):
- repo root (`/run/media/jmulesa/lineage/android/kernel-6.12`) holds **`.repo`**;
- the **bazel workspace is the `kernel_platform/` subdir** (`tools/bazel`, `WORKSPACE`,
  `soc-repo`, `common`, `prebuilts`, `oplus/`);
- build is driven by the OEM **wrapper** `kernel_platform/oplus/build/oplus_build_kernel.sh canoe perf`
  → `prepare_vendor.sh` → `bazel … //soc-repo:canoe_perf_dist`; output lands in
  `kernel_platform/out/msm-kernel-canoe-perf/dist/`;
- **WLAN (cnss2/qcacld) is NOT in the OEM kernel_platform** — it's a separate vendor module set; ours
  is at `kernel/oneplus/sm8850-modules/vendor/qcom/opensource/wlan/{platform,qcacld-3.0}`.

LineageOS `vendor/lineage/build/tasks/kernel.mk` Kleaf path (lines 776-794) assumes a DIFFERENT shape:
- `KERNEL_PATH := $(abspath $(BUILD_TOP)/kernel/platform/kernel-$(TARGET_KERNEL_VERSION))` (line 777) —
  must be simultaneously a **repo root** (line 781 runs `repo manifest` there) AND the **bazel
  workspace** (line 782 runs `./tools/bazel`); manifest projects must be prefixed
  `kernel/platform/kernel-<ver>/` (the sed on 781); it does a **bare `bazel run`**, not the OEM wrapper;
- it builds ONLY the bazel target's modules (793-794 collect `*.ko` from `KERNEL_OUT`); it does **not**
  build `TARGET_KERNEL_EXT_MODULES` on this path (that's the Kbuild/`FULL_KERNEL_BUILD` path's job) —
  so our patched cnss2 would not be built by the stock Kleaf path.

→ Gap 1 = **layout/driver** (workspace-in-subdir, `.repo`-vs-workspace split, OEM wrapper vs bare bazel).
→ Gap 2 = **external WLAN modules** built against the Kleaf kernel and merged in.

## Implementation plan

### Part A — Place the OEM tree where the adapter expects it (generalizes → "importer", tooling #1)
kernel.mk hardcodes `$(BUILD_TOP)/kernel/platform/kernel-<ver>`. Our tree is the sibling
`$(BUILD_TOP)/../kernel-6.12`. With the OEM-wrapper driver we don't need kernel.mk's repo-root
assumptions, but we DO need a stable path. Plan:
- Add an optional `TARGET_KERNEL_PLATFORM_ROOT` var (absolute path to the OEM repo root). When set,
  the adapter uses it directly (tree can live anywhere — no symlink, no in-tree 33G copy).
- Reusable importer (later): a `.repo/local_manifests` snippet (or a `tools/jm2/kleaf_import.sh`) that
  `repo init`/syncs the OEM drop to a canonical sibling path and pins the snapshot (tooling #1 + #3).
- For canoe now: `TARGET_KERNEL_PLATFORM_ROOT := /run/media/jmulesa/lineage/android/kernel-6.12`
  (or a repo-relative resolution); workspace subdir = `kernel_platform`.

### Part B — kernel.mk adapter via the OEM wrapper (the core reusable tooling)
Patch the **jm2 `vendor/lineage` fork** (`build/tasks/kernel.mk`) — add a wrapper-driven branch inside
the `ifneq ($(TARGET_KERNEL_PLATFORM_TARGET),)` block (776-794). New optional vars:
- `TARGET_KERNEL_PLATFORM_ROOT` — OEM repo root (Part A).
- `TARGET_KERNEL_PLATFORM_WORKSPACE_SUBDIR` — e.g. `kernel_platform` (where `tools/bazel`/packages live).
- `TARGET_KERNEL_PLATFORM_BUILD_WRAPPER` — e.g. `oplus/build/oplus_build_kernel.sh` (relative to root).
- `TARGET_KERNEL_PLATFORM_BUILD_ARGS` — e.g. `canoe perf`.
- `TARGET_KERNEL_PLATFORM_DIST` — e.g. `kernel_platform/out/msm-kernel-canoe-perf/dist` (artifact src).

Recipe (replaces the bare bazel run on 781-782 when the wrapper var is set):
```
cd $(TARGET_KERNEL_PLATFORM_ROOT) && \
  ./$(TARGET_KERNEL_PLATFORM_BUILD_WRAPPER) $(TARGET_KERNEL_PLATFORM_BUILD_ARGS)
# then map dist/ → KERNEL_OUT for LOS packaging:
cp -a $(TARGET_KERNEL_PLATFORM_ROOT)/$(TARGET_KERNEL_PLATFORM_DIST)/. $(KERNEL_OUT)/
```
After the copy, LineageOS's existing logic consumes `KERNEL_OUT`: module collection (793-794), dtb/dtbo
packaging (796-806), `TARGET_PREBUILT_INT_KERNEL := $(KERNEL_OUT)/$(BOARD_KERNEL_IMAGE_NAME)` (191).
Notes:
- IMPORTANT shell-env: builds run from the Bash tool must `unset -f grep` first (grep→ugrep breaks the
  OEM scripts the same way it broke `lunch`) — see agent memory `reference_grep_ugrep_breaks_lunch`.
- The OEM wrapper handles its own repo_manifest/stamp, so kernel.mk's manifest-sed (781) is SKIPPED on
  this branch (good — that sed assumes the generic layout and would mis-fire on the OnePlus manifest).
- Incrementality: the wrapper/bazel cache lives in `kernel_platform/out` + `bazel-cache`; the cp is the
  only LOS-side step. Consider a stamp so brunch re-invokes the wrapper only when needed.
- Module-load lists: prefer the OEM `dist/*.modules.load` (system_dlkm/vendor_dlkm) to partition the
  `.ko`, reconciled with `BOARD_*_KERNEL_MODULES_LOAD`.

### Part C — WLAN as Kleaf DDK external modules (Gap 2; the novel, must-investigate piece)
The OEM `canoe_perf_dist` does not build cnss2/qcacld. Build them as `ddk_module`s against the canoe
`kernel_build` so symbols/CRCs match. Concrete anchors in the tree:
- canoe targets: `kernel_platform/soc-repo/kleaf-scripts/targets/canoe.bzl` (defines `canoe_perf`,
  `canoe_perf_abi`, loads `configs/canoe_perf.bzl`); kernel_build machinery in
  `soc-repo/kleaf-scripts/{generic_qtvm,consolidate,dtbs}.bzl`; module lists in
  `soc-repo/{modules,qcom_modules}.bzl` + `target_variants.bzl`.
- DDK tooling present: `soc-repo/kleaf-scripts/ddk_uapi_headers_cc_library.bzl` (+ the build already
  compiled OEM DDK modules like `//vendor/oplus/kernel/boot:cdt_integrity`).

Investigation/steps (do at implementation time):
1. Find an existing `ddk_module(...)` definition in the tree to model (grep `ddk_module(` across
   `kernel_platform/{vendor,soc-repo,common-modules}` — the OEM vendor DDK modules; the macro may be
   wrapped). Note the `kernel = ":<canoe_perf kernel_build target>"`, `deps`, `hdrs`, `includes`.
2. Identify the exact `canoe_perf` `kernel_build` target name DDK modules attach to (from `canoe.bzl`
   / `target_variants.bzl`).
3. Bring our WLAN source into the workspace as DDK packages: add `BUILD.bazel` + `ddk_module` for
   `cnss2`, `cnss_utils`, `cnss_prealloc`, `icnss2`, and `qcacld-3.0` (`qca_cld3_*`), sourcing from
   `kernel/oneplus/sm8850-modules/vendor/qcom/opensource/wlan/...` (symlink/overlay the source into
   `kernel_platform/`, or add a kleaf package pointing at it). The patched `cnss2/qmi.c` (21fae367) is
   the cnss2 source.
4. Build the WLAN DDK target(s) against canoe; resolve missing symbols (GKI/vendor symbol list — the
   pivot's premise is that this MATCHES because we build the OEM's exact kernel).
5. Emit the WLAN `.ko` into `dist/` (extend the dist target) or a parallel collection, so Part B's cp
   picks them up; ensure cnss2/qca_cld3 land in vendor_dlkm + the right modules.load.
RISK: this is the genuinely new engineering. Fallback if DDK-against-OEM-kernel proves hard: build the
WLAN modules via the OEM's own out-of-tree module mechanism (prepare_vendor.sh extra-modules), or the
interim dist-as-prebuilt + side-build (explicitly the non-chosen path, kept as escape hatch).

### Part D — BoardConfig wiring (device-specific; the small per-device surface → "wiring generator", tooling #2)
`device/oneplus/sm8850-common/BoardConfigCommon.mk`, inside the existing `ifneq ($(USE_PREBUILT_KERNEL),true)`
branch (currently lines ~92-118, wired for the PARKED Kbuild path: `TARGET_KERNEL_SOURCE=kernel/oneplus/sm8850`,
`TARGET_KERNEL_CONFIG`, the `.list.{msm,oplus}.canoe` module lists, `TARGET_KERNEL_EXT_MODULES`). Switch
that branch to the Kleaf adapter vars:
- `TARGET_KERNEL_PLATFORM_TARGET := canoe_perf`
- `TARGET_KERNEL_VERSION := 6.12`
- `TARGET_KERNEL_SOURCE := soc-repo`   (bazel package for `//soc-repo:canoe_perf_dist`)
- `TARGET_KERNEL_PLATFORM_ROOT := <abs path to kernel-6.12>`
- `TARGET_KERNEL_PLATFORM_WORKSPACE_SUBDIR := kernel_platform`
- `TARGET_KERNEL_PLATFORM_BUILD_WRAPPER := oplus/build/oplus_build_kernel.sh`
- `TARGET_KERNEL_PLATFORM_BUILD_ARGS := canoe perf`
- `TARGET_KERNEL_PLATFORM_DIST := kernel_platform/out/msm-kernel-canoe-perf/dist`
- keep `BOARD_KERNEL_IMAGE_NAME := Image`; source module-load lists from the OEM dist.
- drop the Kbuild-only `TARGET_KERNEL_CONFIG` / `TARGET_KERNEL_EXT_MODULES` on the Kleaf path.
ALL inside `!USE_PREBUILT_KERNEL` → the working prebuilt build (`USE_PREBUILT_KERNEL=true`, device
boots today) stays UNAFFECTED. `infiniti/BoardConfig.mk:7` `USE_PREBUILT_KERNEL ?= true` remains the
default; flip to false only to exercise the source path.

### Part E — Build + flash + verify (step f)
- `USE_PREBUILT_KERNEL=false BOARD_…` `brunch infiniti` → adapter runs the OEM wrapper → dist → KERNEL_OUT
  + WLAN DDK `.ko` → vendor_dlkm/vendor_boot; assemble super (see `reference_iter_brunch_env`,
  iter_brunch.sh auto-builds super) + boot.img.
- Flash boot + super via **bootloader fastboot** (NOT fastbootd — see `feedback_op15_fastbootd`).
- Verify: boots; `wlan0` present; `ip link`/dmesg show a **unicast** MAC (= BT+1); WiFi associates.
  Cross-check the cnss2 fix: "Received DMS MAC" now logs the de-reversed (unicast) MAC and qcacld
  probe succeeds (no `__wlan_hdd_validate_mac_address` reject / `probe -1`).

## Generalization mapping (what becomes reusable tooling vs per-device)
- Part B kernel.mk adapter = **the core reusable tooling** (in jm2 vendor/lineage): any QC-OEM Kleaf
  device works by setting the Part-D vars.
- Part A = importer/snapshot-pinner (tooling #1/#3): sync+pin any OEM drop to a canonical path.
- Part C = the generic **DDK-external-module-on-OEM-kernel recipe** (tooling): build a distro's vendor
  modules (WLAN, etc.) as DDK against an imported OEM Kleaf kernel.
- Part D vars = output of the **wiring generator** (tooling #2): parse `target_variants.bzl` +
  `targets/<plat>.bzl` + the wrapper → emit the BoardConfig block automatically.
- defconfig-fragment shim (tooling #4): LOS config deltas → Starlark `pre/post_defconfig_fragments`.
- Net per-device surface: snapshot pin + ~8 BoardConfig vars + (optional) defconfig fragments. Verdict
  from the generalization deferred item ("import + pin + a few vars, not a build-system rewrite") holds.

## Open questions / risks
- **Part C is the real risk**: exact `ddk_module` wiring + whether our WLAN source builds clean as DDK
  against the canoe KMI (symbol availability). The pivot premise says CRCs should match (OEM's exact
  kernel); confirm empirically.
- Mapping the OEM `dist/` → `KERNEL_OUT` cleanly (module partitioning via the OEM modules.load; dtb/dtbo
  naming vs `TARGET_{DTB,MERGE_DTBOS}_*_WILDCARD`).
- Brunch incrementality + the wrapper's own caching; avoid rebuilding the world each brunch.
- The adapter must not regress the FULL_KERNEL_BUILD (Kbuild) path or the prebuilt path — guard the new
  branch strictly on the new vars.

## Current state / resumption pointers
- OEM Kleaf kernel builds standalone (RC=0) via `oplus_build_kernel.sh canoe perf`; artifacts in
  `kernel_platform/out/msm-kernel-canoe-perf/dist/` (Image, vmlinux, boot.img, 449 .ko, canoe DTBs,
  infiniti dtbo). See `KLEAF_PIVOT.md`.
- cnss2 MAC fix committed (jm2 sm8850-modules `lineage-23.2` @ 21fae367).
- NOTHING wired yet: BoardConfig still on the Kbuild source vars; kernel.mk unpatched; no symlink/import;
  no WLAN DDK targets. The working prebuilt build is intact and unaffected.
- Trees: ROM = `/run/media/jmulesa/lineage/android/lineage` (BUILD_TOP); OEM Kleaf =
  `/run/media/jmulesa/lineage/android/kernel-6.12` (sibling; ~33G + build out). External-drive/sleep +
  flaky-link caveats: `reference_drive_sleep_and_pkill_gotchas`. jm2 forks push over SSH:
  `reference_jm2_forks_use_ssh`.
- Implementation order when resuming: B (adapter, the reusable core) → A (placement var) → D (canoe
  BoardConfig) → C (WLAN DDK — the hard part) → E (build/flash/verify). Stop/checkpoint at any part.

---

## IMPLEMENTATION RESULTS — 2026-06-09

Implemented B→A→D→C in one session. All edits LOCAL/uncommitted (awaiting the user's go-ahead).
The working prebuilt build (`USE_PREBUILT_KERNEL=true`) is untouched throughout.

### Part B + A — `jm2 vendor/lineage build/tasks/kernel.mk` (on top of its 7 existing Kbuild-era patches)
- New wrapper-driven branch inside the Kleaf path (`ifneq ($(TARGET_KERNEL_PLATFORM_TARGET),)`):
  a `kernel-platform-dist-cmd` define, guarded by `TARGET_KERNEL_PLATFORM_BUILD_WRAPPER`, that does
  `cd $(ROOT) && $(WRAPPER) $(ARGS) && cp -a $(ROOT)/$(DIST)/. $(KERNEL_OUT)/`. The stock bare-`bazel run`
  command is preserved verbatim as the `else`. The shared module-collection / dtb recipe below is
  unchanged (the flat OEM dist is exactly the shape it expects).
- The `$(error "NO KERNEL")` existence guard now validates the wrapper at `$(TARGET_KERNEL_PLATFORM_ROOT)`
  when that var is set (the OEM tree is a sibling outside BUILD_TOP), instead of the stock
  `$(BUILD_TOP)/kernel/platform/kernel-<ver>/$(KERNEL_SRC)`.
- Dropped the forced `./` prefix so `BUILD_WRAPPER` may be an absolute path.
- New vars: `TARGET_KERNEL_PLATFORM_{ROOT,WORKSPACE_SUBDIR,BUILD_WRAPPER,BUILD_ARGS,DIST}`.

### Part D — `jm2 device sm8850-common BoardConfigCommon.mk` (!USE_PREBUILT_KERNEL branch)
- Replaced the parked-Kbuild wiring with the Kleaf adapter vars: `TARGET_KERNEL_PLATFORM_TARGET=canoe_perf`,
  `TARGET_KERNEL_VERSION=6.12`, `TARGET_KERNEL_SOURCE=soc-repo`, `ROOT ?= .../kernel-6.12`,
  `WORKSPACE_SUBDIR=kernel_platform`, `BUILD_WRAPPER=$(abspath $(COMMON_PATH))/kernel-build/build-canoe-kleaf.sh`,
  `BUILD_ARGS="canoe perf"`, `DIST=kernel_platform/out/msm-kernel-canoe-perf/dist`.
- Module-load lists come from the OEM dist's own `*.modules.load` (parse-time `$(shell cat ...)`); verified
  all 125 vendor_boot + 314 vendor_dlkm entries resolve to flat `.ko` in the dist. `BOOT_KERNEL_MODULES`
  uses `$(notdir ...)` (dist `.ko` are flat). `BOARD_KERNEL_MODULES_LOAD_ALLOW_MISSING := true`.
- DTB/DTBO block simplified to always use separated-DTBO (the dist ships flat `*.dtb`/`*.dtbo` +
  `dtbo.img`, same shape the prebuilt path consumes); the Kbuild-only `BOARD_USES_QCOM_MERGE_DTBS_SCRIPT`
  path is gone.
- VALIDATED: `m nothing` with `USE_PREBUILT_KERNEL=false` parses the full graph clean (kernel.mk parsed,
  no `NO KERNEL`, exit 0) → the adapter routes correctly.

### Part C — WLAN as Kleaf DDK (the crux — PROVEN; deltas vs plan)
- **Big delta vs the plan:** we did NOT author `ddk_module`s from scratch. The OEM tree ALREADY ships
  complete WLAN bazel/DDK wiring at `kernel-6.12/vendor/qcom/opensource/wlan/{platform,qcacld-3.0}`
  (`BUILD.bazel` → `define_modules()`), with canoe_perf variants already defined. The OEM kernel build
  (`build_with_bazel.py`) simply never builds them — it queries only `soc-repo/...` targets generated by
  `define_canoe`; WLAN is under `//vendor/...` with `generator=define_modules`, so it's out of scope.
- Targets (attach to `//soc-repo:canoe_perf_base_kernel`; `socrepo=true` is the `device.bazelrc` default):
  - platform: `//vendor/qcom/opensource/wlan/platform:canoe_perf_modules_dist`
    → cnss2, cnss_utils, cnss_prealloc, wlan_firmware_service, cnss_nl, cnss_plat_ipc_qmi_svc, icnss2
  - qcacld: `//vendor/qcom/opensource/wlan/qcacld-3.0:canoe_perf_all_modules_dist`
    → qca_cld3_{peach_v2,kiwi_v2,wcn7750}.ko  (canoe chipsets)
- cnss2's `ddk_module` sets `local_defines = [... "OPLUS_FEATURE_WIFI_MAC" ...]` and lists `cnss2/qmi.c`
  in `conditional_srcs[CONFIG_CNSS2_QMI]` → **our byte-reversed-MAC fix compiles in** (it's guarded by
  `OPLUS_FEATURE_WIFI_MAC`).
- **PROOF:** built `canoe_perf_cnss2` → `cnss2.ko` with **vermagic `6.12.23-android16-5-o-gd9053b907db4-4k`**,
  exactly matching the kernel we built (`gd9053b907db4`). 1241/1339 bazel action-cache hits → the kernel
  did NOT rebuild; only WLAN compiled (51 s). This empirically confirms the pivot's premise: DDK modules
  built against the OEM kernel are KMI/CRC-matched by construction.
- Bazel recipe to hit the warm cache + identical config: from `kernel_platform/`,
  `./tools/bazel --output_user_root=$ROOT/bazel-cache build <opts> //...:<target>` where `<opts>` are read
  from the kernel dist's `build_opts.txt` (`%workspace%`→`$KP`): `--//soc-repo:skip_abl=true`,
  `--incompatible_sandbox_hermetic_tmp=false`, `--noenable_workspace`, and 3× `--override_module=…fake_modules`.
- The `_modules_dist` outputs are UNSTRIPPED (qca_cld3 ≈540 MB each w/ DWARF). Strip with the OEM clang
  `llvm-strip --strip-debug` (same as the kernel's `INSTALL_MOD_STRIP=1`; preserves symtab/modinfo/vermagic):
  cnss2→1.1 M, icnss2→1.6 M, qca_cld3→≈20 M each, helpers tiny.
- Chipset reality: live device (`adb lsmod`) loads `qca_cld3_peach_v2`; the prebuilt LOS build lists ALL
  10 WLAN modules in `vendor_dlkm.modules.load` (modprobe resolves deps via modules.dep; non-matching
  qca_cld3 chipsets fail probe gracefully — only peach_v2 ends up loaded). We mirror that (include all 10,
  list all 10).
- The cnss2 MAC fix was applied to the LOCAL OEM tree (`kernel-6.12/vendor/qcom/opensource/wlan/platform/
  cnss2/qmi.c`) — byte-identical to the jm2 `sm8850-modules` copy except for the fix (== commit `21fae367`).
  FOLLOW-UP: fork the OEM modules repo to jm2 and commit this patch there (currently the fix lives only in
  the local synced tree for the Kleaf build).

### Integration — NEW committed tooling: `device/oneplus/sm8850-common/kernel-build/build-canoe-kleaf.sh`
Keeps the LOS adapter generic: the adapter just "runs a wrapper + cp's the dist." This device wrapper
encapsulates the device-specific orchestration: (1) run `oplus_build_kernel.sh canoe perf`; (2) build the
WLAN platform + qcacld dist targets (reusing the kernel build's exact `build_opts.txt` bazel config);
(3) `llvm-strip` the WLAN `.ko` and merge them into the kernel dist, appending their names (deduped) to
`vendor_dlkm.modules.load`. Two non-obvious fixes baked in:
- `exec </dev/null` at the top — the OEM build runs `make oldconfig`, which prompts for NEW Kconfig
  symbols; with EOF it auto-takes defaults (exactly what the OEM's own clean build does). Without it, a
  background/brunch (non-tty) caller hangs forever on the prompt.
- `cd $KP` (the `kernel_platform/` workspace) before the WLAN `bazel` runs — bazel from the `.repo` repo
  root errors `Unable to determine root of repository`.

### Remaining
- **Part E (needs hardware — user):** `USE_PREBUILT_KERNEL=false brunch infiniti` → adapter runs the wrapper
  → kernel+WLAN dist → `KERNEL_OUT` → super + boot.img; flash via bootloader fastboot (NOT fastbootd); verify
  it boots, `wlan0` present with a UNICAST MAC (= BT+1), WiFi associates, and dmesg shows the de-reversed
  "Received DMS MAC" + no `__wlan_hdd_validate_mac_address` reject.
- Fork+commit the OEM WLAN modules repo (cnss2 patch) to jm2 for reproducibility (see DEFERRED_FOLLOWUPS).

## COMPREHENSIVENESS RESULTS — 2026-06-09 (full stock-parity module set)

The WLAN-only wrapper was extended to deliver the COMPLETE module set, fully source-built ("kernel and
modules as fully source-built as possible" — user goal). Findings + final state:

- Gap analysis vs the working prebuilt ROM: stock loads **673 unique modules**; the kernel-only dist had
  459 → 214 missing = (a) ~80 GKI system_dlkm modules (built by the kernel into
  `system_dlkm_staging_archive.tar.gz`, just not flat) + (b) ~134 vendor techpack modules. The OEM
  standalone kernel build NEVER builds `//vendor/...` (build_with_bazel queries only soc-repo/define_canoe)
  — same root cause that excluded WLAN. Without (b), no display (msm_drm), audio, camera, BT, rmnet.
- The OEM tree has **82 canoe_perf `*_dist` targets under `//vendor/...`** (enumerated via bazel query
  `filter("canoe_perf.*dist", //vendor/...)` + filtering `_dist_{manifest,tool,internal}` helpers and
  qcacld per-chipset dups). All techpacks are wired for canoe: display, graphics, camera, video/eva,
  audio, dsp (fastrpc), securemsm, bt, datarmnet(+ext)/dataipa, mm-drivers, mmrm, synx, spu, NFC
  (nxp + st), and ~48 oplus packages.
- **Wrapper now (4 stages):** (1) OEM kernel build; (2) enumerate + one parallel `bazel build
  --keep_going` of all vendor targets + per-target `bazel run -- --dist_dir` (fallback `--destdir`) into
  a stage dir; (3) `llvm-strip --strip-debug` every staged .ko into the dist + extract the GKI modules
  named by `system_dlkm.modules.load` from the staging archive; (4) coverage gate vs the STOCK load
  lists with a committed exceptions file (`known-source-gaps.txt`) — any UNDOCUMENTED first-stage gap
  fails the build.
- **BoardConfig switched to stock-parity load lists** (`device/oneplus/infiniti-kernel/modules/*` — the
  exact lists the booting prebuilt path uses; membership AND order): vendor_dlkm + vendor_ramdisk +
  recovery + system_dlkm + both blocklists; `BOOT_KERNEL_MODULES = notdir(recovery list)` (mirrors
  `infiniti-kernel/BoardConfig.mk` — recovery ⊇ ramdisk, verified).
- **New jm2 vendor/lineage patch 6:** Kleaf-path `BOOT/RECOVERY_KERNEL_MODULES` staging is a direct cp
  (hard-fails on one missing .ko; patch-4 ALLOW_MISSING didn't cover it). Now, under
  `BOARD_KERNEL_MODULES_LOAD_ALLOW_MISSING := true`, missing first-stage modules are skipped with a
  warning, filtered shell-side at recipe runtime (make `$(wildcard)` would evaluate BEFORE the same
  recipe's kernel-build step populates KERNEL_OUT — wrong).
- **21 documented no-source gaps** (`kernel-build/known-source-gaps.txt` w/ per-module risk notes):
  `oplus_bsp_ex_gpio` (only first-stage one; AW951XX GPIO expander, use-count 0 on stock; OnePlus ships
  only an empty-stub BUILD.bazel — no public source), the oplus_network_* optimizer/satellite family,
  oplus_icc_mcu, variant touch leaves (atmel/goodix/st_fts/qts — infiniti's synaptics IS source-built),
  qbt_handler (infiniti uses oplus uff fp — source-built). Borrowing stock .ko is impossible: stock
  vermagic `…geb065695cf38` ≠ ours `…gd9053b907db4`.
- 8 oplus dist targets fail to compile (cs_press, fpga, pogo_keyboard, tri_state_key, secureguard,
  3× sensorhub) — verified NONE of their modules is in any stock load list (and the sensorhub modules
  are delivered by the succeeding `oplus_bsp_sensor_dist` anyway). Logged, not blocking.
- **FINAL VALIDATED STATE: 0 missing across all four stock lists** (first-stage 0+1 known-gap,
  recovery 0+16, vendor_dlkm 0+20, system_dlkm 0+0), **644 flat .ko in dist**, wrapper exit 0,
  idempotent re-runs. Every shipped module is source-built against the same canoe_perf kernel_build
  (KMI/vermagic-matched by construction); the ONLY non-source content is the 21 documented extras,
  which simply don't ship.

## ADVERSARIAL REVIEW + HARDENING — 2026-06-09/10

A multi-agent adversarial review (llvm-nm/ckati-verified findings) of the wireup found 4 brunch/boot
blockers beyond the first implementation; all fixed + re-validated (vendor/lineage `88663f8e`,
sm8850-common `2b30f74`; final run: all five gates 0-missing, vermagic all-644-match, exit 0):
1. **First-stage understaging:** staging only the recovery LOAD LIST dropped 15 dependency-only
   modules stock stages by DIRECTORY (verified: msm_drm has 14 strong undefined hdcp_* symbols
   exported only by hdcp_qseecom_dlkm → depmod -ae build failure + no display at boot). Fix:
   `BOOT_KERNEL_MODULES := $(sort $(notdir $(wildcard …/vendor_ramdisk/*.ko)))` (prebuilt
   semantics) + the kernel.mk ALLOW_MISSING staging filter (patch 6) + a staged-dir coverage gate.
2. **zram/zsmalloc dual-copy collision:** stock ships GKI copies (system_dlkm) AND oplus-patched
   copies (vendor_dlkm) of the same names; the flat dist holds the vendor ones → GKI-only
   system_dlkm depmod fails on the oplus symbols AND the comm split silently drops zram from
   vendor_dlkm. Fix: wrapper drops colliding names from system_dlkm.modules.load (vendor copy
   ships/loads via the stock vendor list — what the OEM device actually uses).
3. **dtbo never produced on the source path** (BOARD_PREBUILT_DTBOIMAGE was prebuilt-include-only →
   no dtbo.img target, broken --recovery_dtbo, unsatisfiable AVB chain). Fix: kernel.mk "dist dtbo
   passthrough" rule publishes the dist's OEM-packed dtbo.img (all 8 variant overlays) at
   BOARD_PREBUILT_DTBOIMAGE; the BoardConfig assignment MUST be deferred `=` — an immediate `:=`
   captures empty TARGET_OUT_INTERMEDIATES → absolute `/KERNEL_OBJ/...` → **soong glob-walk panic**
   (`filepath.Rel(TOP, /)`).
4. **OEM build failures undetectable** (their scripts tee with no pipefail; cached rebuilds rewrite
   NO dist files so mtime freshness is meaningless). Fix: parse bazel's failure sentence from the
   LOGDIR log + artifact existence + a **vermagic gate** over every shipped .ko against the GKI
   archive's release (the authoritative kernel-release source — kbuild's kernel.release only exists
   inside bazel sandboxes).
   Plus: per-target staging subdirs + sha256 cross-target collision gate; merge manifest (stale .ko
   removed each run); KOPTS hard checks; stock-list absence fails the hard gates; KERNEL_OUT
   consumed-namespace cleanup in the adapter; guard re-keyed on BUILD_WRAPPER.
   Known-accepted (documented, non-blocking): system_dlkm image ships no modules.load on the Kleaf
   path (runtime loader ignores it on this device — upstream Kleaf-path behavior, not ours); the
   8 never-stock-loaded oplus targets that fail to compile; coverage is name-based but staleness is
   now covered by the vermagic gate.
