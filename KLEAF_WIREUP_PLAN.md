# LOS ↔ OEM-Kleaf wire-up plan (step d) — built as a reusable adapter

**Status: PLANNED 2026-06-08 (not yet implemented). Session wrapped here.**
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
