# Kernel build: pivot from hand-translated Kbuild → OEM Kleaf `_dist`

**Status:** DECIDED 2026-06-05 (de-risking in progress). Supersedes the Kbuild
source-build approach in `IMPLEMENTATION_PLAN.md` / `WIRE_UP_RECIPE.md` as the
*primary* route to a source-built, bootable, WiFi-patched kernel. The Kbuild tree
is **parked, not deleted** (see "Kbuild set-aside" below).

This doc is the canonical record of *why* we pivoted, *what's verified*, the *plan*,
and the *generalization follow-up*. It exists because the original source-build plan
never evaluated the Kleaf path, and that turned out to be the wrong frame (a textbook
case of the `feedback_question_the_base_before_patching` lesson — one layer down).

---

## TL;DR

- LineageOS `kernel.mk` already has a Kleaf path (line ~782): when a device sets
  `TARGET_KERNEL_PLATFORM_TARGET`, it runs `./tools/bazel run
  //<src>:<target>_dist -- --destdir=<out>` and harvests the dist dir. The
  "connector" we thought we'd have to build mostly **already exists upstream.**
- The OEM publishes the real Kleaf `kernel_platform` for canoe (OnePlusOSS, below),
  it **builds offline by default**, and building the OEM's *own* kernel reproduces
  the exact `module_layout` CRCs our deployed `vendor_dlkm` prebuilts need →
  **dissolves the KMI-skew blocker** that the Kbuild path is stuck on.
- The deployed kernel is itself **Kleaf-built** (`/proc/version`: `kleaf@build-host`,
  clang 19.0.1) — so Kleaf is the OEM's native method, and it pins **clang 19**, which
  sidesteps the clang-22 `-Werror,-Wdefault-const-init-field-unsafe` friction that
  blocked our Kbuild build.

## Why the Kbuild path was the wrong base (root cause, not a patch target)

- `IMPLEMENTATION_PLAN.md:70-72` framed the job as "translate the OEM Bazel specs into
  Kbuild Makefiles that `mka kernel` can consume" — Bazel as a thing to translate
  *from*, never as a build path to *use*. The Kleaf-direct option was never raised.
- That path built on **generic Google ACK `android16-6.12-2025-06_r8`** merged with
  vendor patches (`IMPLEMENTATION_PLAN.md:22`, `README.lineage.md:189`) — NOT the OEM's
  exact kernel. Result: `module_layout` CRC mismatch vs the OEM `vendor_dlkm` prebuilts
  (557/557 rejected, `kmi_strict_audit.md`) → the #1 reason the Kbuild kernel can't boot.
  Months of wave work were spent source-building modules to paper over a self-inflicted
  base mismatch.
- It also hit "OEM-Bazel-environment-coupled" modules (e.g. 2F.3 charger) that don't
  translate cleanly to Kbuild — friction *caused by* avoiding Bazel.

## Verified facts (this session + research, 2026-06-05)

**Deployed kernel we must stay compatible with** (the working prebuilt build):
- `/proc/version`: `6.12.23-android16-5-gb2a876903b49-ab14541642-4k (kleaf@build-host)`,
  Android clang **19.0.1** (r536225), built **Fri Dec 5 2025**.
- Modules vermagic: `6.12.23-android16-5-o-geb065695cf38-4k` (the `-o-` OEM/msm-kernel build).
- Source = infiniti-kernel prebuilt `0696255` "Update from **OOS 11.A.40**" (2026-05-11).
- → Target snapshot ≈ the OnePlusOSS launch/early point-release (Dec-2025 kernel). EXACT
  snapshot pin is step (a) below.

**OEM Kleaf drop (OnePlusOSS, branch `oneplus/sm8850_b_16.0.0_oneplus_15`):**
- `OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8850` — the superproject
  (`kernel_platform/` + `vendor/`); carries `MODULE.bazel`, `tools/bazel`,
  `build/kernel/kleaf`, `device.bazelrc`, all deps via `local_path_override` → builds offline.
- `OnePlusOSS/android_kernel_common_oneplus_sm8850` — GKI/ACK common; Makefile 6.12.23;
  ships `gki/aarch64/{abi.stg,symbols/}` + `gki_defconfig` with `CONFIG_MODVERSIONS=y`.
- `OnePlusOSS/android_kernel_oneplus_sm8850` — msm-kernel; `build.config.msm.canoe`,
  `target_variants.bzl` (`canoe`, variants `perf`/`consolidate`), `kleaf-scripts/targets/canoe.bzl`.
- **Dist target = `//msm-kernel:canoe_perf_dist`** (perf = production/GKI; consolidate = debug).
  So `TARGET_KERNEL_PLATFORM_TARGET := canoe_perf`. (No `canoe_gki_dist`.)
- Offline: `build/kernel/kleaf/bazelrc/network.bazelrc` defaults `--config=no_internet`;
  bazel binary vendored at `prebuilts/kernel-build-tools/bazel/linux-x86_64/bazel`.

**LineageOS support:** `kernel.mk` Kleaf path added mid-2025 (commits `7cd90ecd34`,
`665b11d8b1`, `bec0fb162f`, …). SHIPPING on `foster`/`tegra_dist` + `genevn`/`ums9230_dist`.
**Caveat: NO Qualcomm LOS device uses it yet** — every QC OnePlus tree (incl. closest analog
`sm8750`/sun) uses hand-Kbuild. We'd be **first-on-QC** on a young path. The platform is
checked out as a SIBLING of the Android tree at `$(BUILD_TOP)/../kernel-<ver>` (its own
`repo` checkout) — `kernel.mk` runs `repo manifest` there for scmversion.

## Plan (bounded de-risking — do NOT big-bang)

a. **Pin the snapshot.** Map OOS 11.A.40 / kernel `geb065695cf38` (Dec-2025) → the exact
   OnePlusOSS "Synchronize code for CPH2745_16.0.x" commit on the three repos. Launch
   `16.0.0.204` (common `bd2553d`, Nov 2025) is the leading candidate; confirm via `gh` on
   `android_kernel_common_oneplus_sm8850` by matching Makefile SUBLEVEL + the build date.
b. **Stand up the sibling checkout.** `repo init`/`sync` the OEM superproject at the pinned
   snapshot as `<BUILD_TOP>/../kernel-6.12` (or wire `TARGET_KERNEL_VERSION`). Large sync
   (GKI common + prebuilts + external). Vendored prebuilts only — no network at build.
c. **Prove it builds offline standalone**, BEFORE any `m`:
   `cd kernel-6.12/kernel_platform && tools/bazel run //msm-kernel:canoe_perf_dist --
   --destdir=$PWD/out/dist` (default `--config=no_internet`). Harvest Image + dtbs + .kos.
d. **Wire the device** (sm8850-common): `TARGET_KERNEL_PLATFORM_TARGET := canoe_perf`,
   `TARGET_KERNEL_SOURCE := msm-kernel` (path within the platform to the build rules),
   `TARGET_KERNEL_VERSION`, keep `BOARD_USES_GENERIC_KERNEL_IMAGE`/`BOARD_KERNEL_IMAGE_NAME`.
   Confirm the exact var contract against `vendor/lineage/build/tasks/kernel.mk`.
e. **Apply the WiFi cnss2 MAC byte-order patch** in the OEM tree's cnss2
   (`cnss_qmi_get_dms_mac`, de-reverse the multicast DMS MAC — see
   `DEFERRED_FOLLOWUPS.md` WiFi entry + memory `project_jun03_wifi_softsku_rootcause`).
f. **Build via `m`/brunch, flash boot + super (with the dist's vendor_dlkm), verify `wlan0`.**

## Kbuild set-aside (parked, NOT discarded)

- The flattened Kbuild tree `kernel/oneplus/sm8850` @ 49797ea (Phase-5 Wave-2 work) stays
  in the repo. The `USE_PREBUILT_KERNEL != true` BoardConfig branch (incl. the canoe
  config edits committed in `dc40ce1`) is the Kbuild source path; leave it intact but unused.
- The **working default remains `USE_PREBUILT_KERNEL=true`** (prebuilt OEM kernel) — the
  device boots on that today. Kleaf is the new *source* path, replacing the Kbuild source path.
- Keep the Kbuild route recoverable in case the first-on-QC Kleaf path proves unworkable.

## Forking plan (note what/why; not done yet — premature until path validated)

- OEM repos (`OnePlusOSS/android_kernel_{modules_and_devicetree,common,oneplus}_sm8850`) are
  synced **read-only** at the pinned snapshot for the build.
- Once the Kleaf build is validated, **fork to jm2** only the repo(s) we must patch (the
  cnss2 WiFi fix + any LOS-adaptation), carrying our deltas as a thin overlay on the OEM
  snapshot — mirroring the device-tree convergence model. Document each fork + reason here
  when made. (Do not fork speculatively.)

## Generalization follow-up (make this turnkey for future devices)

The connector is ~80% upstream (`kernel.mk` Kleaf path). The reusable per-device residue is
mechanical and worth tooling:
1. **kernel_platform importer** — OEM monorepo/superproject → the sibling `kernel-<ver>`
   `repo` layout + manifest the bazel path expects (cf. the `klsplit.py` sketch from the
   Opus-Web session — treat platform codename as ONE guarded parameter; on-disk verify it).
2. **Wiring generator** — parse `build.config.msm.<plat>` + `target_variants.bzl` to emit the
   BoardConfig block (`TARGET_KERNEL_PLATFORM_TARGET=<plat>_perf`, source path, clang),
   `device.bazelrc`, and the local manifest. Confirm the `kernel.mk` switch var per LOS branch.
3. **Snapshot pinner** — map a device's deployed kernel SHA/build-date/OOS tag → the OEM
   "Synchronize code for…" snapshot commit (the squashed-snapshot matching problem).
4. **Defconfig-fragment shim** — keep LOS fragments as data, codegen into Starlark
   `pre/post_defconfig_fragments`.
5. **Offline-build doc** — `--config=no_internet`, vendored bazel/clang, `--repo_manifest`.

Goal: per-device kernel bring-up drops from "rewrite the build system" (what canoe Kbuild
became) to "import + pin snapshot + 4 BoardConfig vars," hours not weeks.

## Risks (carried into the de-risking steps)

- First-on-QC for LOS Kleaf path (young; bring-up bugs: sibling-repo requirement,
  scmversion/`repo`-sandbox, stray-file-in-source).
- Snapshot mismatch → recreates CRC skew. Must pin to the firmware-matching snapshot.
- Setup cost: large sibling sync + vendored prebuilts.
- Sets aside the Kbuild wave investment (acceptable — it built the wrong base, never booted;
  sunk cost is a bias).
