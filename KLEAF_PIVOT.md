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

---

## Concrete findings — snapshot SHAs + offline sync recipe (2026-06-06)

**Snapshot pin (step a) — CORRECTED for CPH2749 (the device).** Region prefixes interleave on the
one branch: CPH2745/CPH2747 = India/Export, **CPH2749 = our export/NA device**, PLK110 = China.
- **Latest CPH2749 = `16.0.7.202(EX01)` (2026-06-03) = branch HEAD = what we synced.** SHAs:
  common `d9053b907db4`, msm/soc-repo `5d3c0aadefa2`, superproject `307d23721d20`
  (QCOM tag `android16-6.12-2025-06_r53`).
- CPH2749 published track: `16.0.2.401` (Feb 3, common `16099f8ab4cc`) → `16.0.3.503` (Feb 10,
  common `227664cbe007`) → `16.0.7.202` (Jun 3, HEAD). **There is NO CPH2749 16.0.5.x** — the only
  16.0.5.x is `PLK110_16.0.5.701` (China-only, `a554b51`); don't use it.
- Our DEPLOYED kernel (OOS 11.A.40, ~Dec 2025 GKI build `gb2a876903b49`) PREDATES every published
  CPH2749 snapshot (earliest = Feb's 16.0.2.401) — so an exact deployed-match isn't obtainable
  publicly. → Build the LATEST (`16.0.7.202`, the synced HEAD) and likely RE-EXTRACT the vendor
  partition from 16.0.7.202 too, for a clean current coherent base. The scmversion SHAs
  (`b2a876903b49`/`eb065695cf38`) are GKI/OEM-internal, not addressable here.
- CRC `module_layout` parity must be verified EMPIRICALLY (build → `modinfo -F vermagic` + module
  load vs the on-device set). GKI KMI is stable within android16-6.12, so a 16.0.7.202 kernel +
  its own source-built modules should be self-consistent and vendor-compatible — confirm on boot.

**Sync recipe (step b) — DONE/in progress:** synced to **`/run/media/jmulesa/lineage/android/kernel-6.12`**
(= `$(BUILD_TOP)/../kernel-6.12`, the sibling location kernel.mk expects with `TARGET_KERNEL_VERSION:=6.12`):
```
repo init -u https://github.com/OnePlusOSS/kernel_manifest -b oneplus/sm8850 -m oneplus_15.xml
repo sync -c -j4 --no-tags --no-clone-bundle --retry-fetches=3 --depth=1
```
**⚠ 2026-06-07 SYNC STATUS — clang is the ONE missing piece; resume with `--depth=1`.**
Everything is synced EXCEPT the host clang toolchain. Present + intact (19G total after cleanup):
OnePlus source (`kernel_platform/common @ d9053b907`, `soc-repo`, build, oplus, qcom, common-modules)
and most prebuilts — `kernel_platform/prebuilts` (4.2G) has build-tools, clang-tools, gcc, jdk,
kernel-build-tools (incl. **bazel 8.0.0**), ndk-r26. **MISSING:**
`kernel_platform/prebuilts/clang/host/linux-x86/clang-r536225` (clo-la project has 0 finalized packs).
That clang prebuilt is a single **>10 GB git fetch that is NOT resumable** — the flaky link + laptop
sleep drive-unmounts (agent memory [[reference_drive_sleep_and_pkill_gotchas]]) killed it repeatedly,
each retry restarting from 0 and piling up ~10 GB dead `tmp_pack_*` partials (cleaned — freed ~59 GB).
**RESUME (on AC + sleep-inhibited):** `cd <BUILD_TOP>/../kernel-6.12 && find .repo -name '*.lock' -delete
&& PATH=$HOME/.local/bin:$PATH repo sync -c -j4 --no-tags --no-clone-bundle --retry-fetches=3 --depth=1`.
The **`--depth=1`** shrinks clang to ~3–5 GB (toolchain FILES only, no git history — fine for the bazel
build) so it can actually finish on this link; if a pinned-SHA project rejects shallow, full-fetch just
that one on a wired connection.
- Manifest pins the 3 OnePlus repos to the MOVING branch → after sync `git checkout` the bracketing
  snapshot in each: common → `kernel_platform/common`, msm → `kernel_platform/soc-repo`, superproj → `./`.
- `network.bazelrc` defaults `--config=no_internet`; build via
  `./kernel_platform/oplus/build/oplus_build_kernel.sh canoe perf`. Verify clang-r536225 present first.

**✅ 2026-06-08 — SYNC COMPLETE; tree build-ready (33G).** clang-r536225 (verified
`clang --version` = Android clang 19.0.1 r536225, exact match to deployed) + clang-r547379, rust
(@6ff98fe), trusty (@3408234), bazel 8.0.0, gcc/jdk/ndk/build-tools, common @ d9053b907, soc-repo —
all present. **CORRECTION to the recipe above: `--depth=1` via repo does NOT work for these
codelinaro SHA-pinned prebuilts** — `repo sync` has no `--depth`, and `repo init --depth=1` set
repo.depth=1 but repo still fetched them non-shallow (3 failed attempts, ~13GB wasted). **The shallow
method that WORKS is RAW git, per project:** delete the repo gitdir + worktree, then in the (empty)
worktree run
`git init && git remote add clo-la https://git.codelinaro.org/clo/la/<project-name> &&
git fetch --depth=1 clo-la <pinned-SHA-from-manifest> && git checkout <SHA>`
(GitLab allows reachable-SHA-in-want → pulls only the pinned commit's tree). Exact wire cost:
clang **1.9GB**, rust **1.2GB**, trusty ~0. NEXT = step (c) build `canoe_perf_dist` offline.
- OEM build helper: `./kernel_platform/oplus/build/oplus_build_kernel.sh canoe perf` (wraps
  `tools/bazel run //…:canoe_perf_dist`). NOTE: the msm-kernel maps to `kernel_platform/soc-repo`,
  so the bazel package label may be `//soc-repo:canoe_perf_dist` (and `TARGET_KERNEL_SOURCE` the
  in-platform path to the build rules) — confirm at step (c) via `tools/bazel query`.

**Provenance of this section:** two research sub-agents (kernel.mk Kleaf path + OnePlusOSS drop;
then snapshot/manifest pin) cross-checked against live OnePlusOSS/`gh` + CLO-LA GitLab, plus the
device `/proc/version`. Sync kicked 2026-06-06.

## STEP (c) RESULT — `canoe perf` BUILD SUCCEEDED (2026-06-08)

Ran from `<…>/kernel-6.12`: **`unset -f grep`** first (the dev shell aliases grep→ugrep, which breaks
the build the same way it broke `lunch` — see [[reference_grep_ugrep_breaks_lunch]]) + sleep-inhibit,
then `./kernel_platform/oplus/build/oplus_build_kernel.sh canoe perf` (offline; wraps
`prepare_vendor.sh canoe perf` → `tools/bazel run`). **RC=0 in 17m20s.** Artifacts in
`kernel_platform/out/msm-kernel-canoe-perf/dist/`:
- **Image** 39.9MB (`Linux kernel ARM64 boot executable Image, little-endian, 4K pages`),
  **vmlinux** 376MB, **System.map**, **boot.img** (+ boot-gz / boot-lz4).
- **449 `.ko`** modules (incl. `cfg80211.ko`, `mac80211.ko`).
- canoe DTBs (`canoe`/`canoep`/`-tp`/`-v2`…) + the packed `infiniti-…-dtbo.img` (overlays for
  peach-cnss / wcn786x-bt / display / camera / audio variants).
- **clang-r536225 confirmed in use** (build warns `CLANG_PREBUILT_BIN … clang-r536225/bin`).

Benign warnings only: `gki vmlinux files is not found`, `CLANG_PREBUILT_BIN should not be set`, and a
non-fatal `FileNotFoundError: …/prebuilts/asuite` (a build-metadata git step; asuite wasn't fetched and
isn't needed — did NOT abort). **This validates the whole pivot: the OEM's exact kernel builds from
source, offline, with the matching clang — dissolving the KMI-skew premise that blocked the old Kbuild
route.**

**REMAINING (toward a WiFi-fixed source-kernel boot):**
- **(e) cnss2 byte-reversed-MAC patch** — `cnss2.ko` is NOT in the core `dist/` (cfg80211/mac80211
  are, but the WLAN/cnss driver is a separate vendor module set / bazel target). Step e: locate that
  module build, patch `cnss2/qmi.c` to de-reverse the DMS WLAN MAC ([[project_jun03_wifi_softsku_rootcause]]),
  rebuild it.
- **(d) wire the device**: `USE_PREBUILT_KERNEL=false`, `TARGET_KERNEL_PLATFORM_TARGET=canoe_perf`,
  source path, `TARGET_KERNEL_VERSION=6.12` (BoardConfig — these live in the !USE_PREBUILT_KERNEL branch).
- **(f)** build the ROM against it, flash, verify `wlan0`.
