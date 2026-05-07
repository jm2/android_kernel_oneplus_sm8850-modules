# Bazel → Kbuild wire-up recipe

How to translate one OnePlus external module from its `BUILD.bazel`
definition into the Kbuild + Makefile + Board-config trio that
`mka kernel` consumes, producing a `.ko` that loads cleanly against
our source-built kernel.

This is the per-module recipe used in IMPLEMENTATION_PLAN.md Phase 5+.
Phase 4 validated it end-to-end on `oplus_bsp_dfr_keyevent_handler`
as the proof-point.

---

## Inputs

For any module you're wiring up, you need:

1. **Bazel definition** — typically in
   `vendor/<vendor>/kernel/<subsystem>/oplus_local_modules.bzl` (for oplus
   modules) or `vendor/qcom/opensource/<subsystem>/<dir>/BUILD.bazel`
   (for qcom). Look for `define_oplus_ddk_module(...)` or
   `define_kernel_module(...)` calls.

2. **Source files** — usually a directory peer to the BUILD.bazel,
   with one or more `.c` files plus shared headers under
   `<subsystem>/include/`.

3. **OEM prebuilt** at `device/oneplus/infiniti-kernel/<name>.ko` —
   useful as a reference for which symbols the module is supposed
   to import/export. Diff this against the source-built result later.

---

## Step 1 — Read the Bazel definition

A typical `define_oplus_ddk_module(...)` block:

```python
define_oplus_ddk_module(
    name = "oplus_bsp_dfr_keyevent_handler",
    srcs = native.glob([
        "**/*.h",
        "common/keyevent_handler/keyevent_handler.c",
    ]),
    includes = ["."],
    ko_deps = [
        "//vendor/oplus/kernel/boot:oplus_bsp_boot_projectinfo",
    ],
    local_defines = ["CONFIG_OPLUS_FEATURE_KEYEVENT_HANDLER"],
)
```

What each field maps to:

| Bazel field | Kbuild equivalent |
|---|---|
| `name` | The `.ko` filename (drop `.ko`). Use as `MODULE = name`. |
| `srcs` (glob `.c` files) | `$(MODULE)-objs := <foo>.o <bar>.o ...` |
| `srcs` (glob `.h` files) | Implicit — header files don't need listing |
| `includes` | `ccflags-y += -I$(srctree)/$(src)/<dir>` (only if outside the module's own dir) |
| `local_defines` | `ccflags-y += -DCONFIG_X` (or just rely on the CONFIG knob in `KBUILD_OPTIONS`) |
| `ko_deps` | `KBUILD_EXTRA_SYMBOLS := <path-to-other-module's>/Module.symvers` |
| `conditional_defines = {"qcom": [...]}` | `ccflags-y += -DFOO` if QCOM is the platform (it is, for sm8850) |
| `header_deps` | Add the dep's include path via `ccflags-y` |

**Always include every `ko_deps` entry — don't skip based on judgment.**
A Phase 5 wave 1 stress-test confirmed this. When wiring
`oplus_bsp_dfr_dump_device_info`, the BUILD.bazel listed `oplusboot`
as a `ko_dep`. The `oplusboot` module isn't in modules.load and
appears unused at first glance, so I dismissed it. modpost then
errored on `serial_no` undefined — turns out dump_device_info
imports `serial_no` (defined in `oplusboot.c`) via
`#include <soc/oplus/system/oplus_project.h>`. The fix was adding
the right symvers, but the diagnostic was a wasted iteration. The
recipe rule stands: extra deps are harmless, missing deps cause
modpost errors. Translate every `ko_deps` entry; trust the BUILD.bazel.

**Cross-module name mapping is non-trivial.** A Bazel `ko_deps`
target like `//vendor/oplus/kernel/boot:oplusboot` doesn't always
correspond to a `.ko` of that name in our build. Source files can be
bundled — e.g. `oplusboot.c` is one of seven `.c` files compiled into
`oplus_bsp_cmdline_parser.ko` in our build. The KBUILD_EXTRA_SYMBOLS
path is the BUNDLE's `Module.symvers`, not the original Bazel target's.

To find the right path:

1. `grep -rn 'EXPORT_SYMBOL.*<missing-symbol>' kernel/oneplus/sm8850-modules/vendor/`
   to find the source file that exports it.
2. Walk up to the dir containing the Kbuild — that's the bundle.
3. `cat <bundle-dir>/Kbuild` confirms via `MODULE = ...` and `-objs := ...`.
4. The bundle's `Module.symvers` lives in the same dir as the Kbuild.

The `bazel_kbuild_diff.py` tool (in `tools/jm2/`) can parse the BUILD
file and compare against your Kbuild to flag missing/extra entries.

---

## Step 2 — Author the per-module Kbuild

In the module's source dir, create `Kbuild`:

```makefile
# SPDX-License-Identifier: GPL-2.0-only
MODULE = oplus_bsp_dfr_keyevent_handler
$(MODULE)-objs := keyevent_handler.o
obj-$(CONFIG_OPLUS_FEATURE_KEYEVENT_HANDLER) += $(MODULE).o
```

Key points:

- **`MODULE` name must be the OEM-shipping `.ko` name.** This is what
  `modules.load` expects. If the source file is `keyevent_handler.c`
  but the OEM ships `oplus_bsp_dfr_keyevent_handler.ko`, the Kbuild
  must rename via `$(MODULE)-objs`.
- **Multi-source modules:** list every `.c` (as `.o`) in `$(MODULE)-objs`.
  Watch for conditional sources (e.g., `<MODULE>-objs += $(if $(CONFIG_X),y.o)`).
- **Single-source modules where the source filename matches the module
  name:** drop the `$(MODULE)-objs := ...; obj-X += $(MODULE).o`
  indirection and use `obj-X += <name>.o` directly. Otherwise kbuild
  hits a circular self-reference: it tries to build `<name>.o` (the
  compound-link intermediate kbuild expects from `-objs`) FROM
  `<name>.o` (the same name, as the .c-derived object). The error is
  `make[4]: Circular .../<name>.o <- .../<name>.o dependency dropped.`
  Example: `oplus_network_esim.c` → `oplus_network_esim.ko`, written as:

  ```makefile
  EXTRA_CFLAGS += -DQCOM_PLATFORM
  obj-m += oplus_network_esim.o
  ```
- **The `obj-$(CONFIG_X) += $(MODULE).o` line** is what triggers the
  build when CONFIG_X is `m` or `y`.
- **Headers in adjacent dirs:** `#include "../../include/foo.h"` from
  the source file resolves via the relative path; no `ccflags-y` needed
  unless the source includes by absolute name.

If the source's `#include` resolution fails at compile time, add
`ccflags-y += -I$(srctree)/$(src)/../../include` (or similar) to the
Kbuild.

---

## Step 3 — Author the per-module Makefile

In the same dir, create `Makefile`:

```makefile
# SPDX-License-Identifier: GPL-2.0-only
KBUILD_OPTIONS += CONFIG_OPLUS_FEATURE_KEYEVENT_HANDLER=m

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(KBUILD_OPTIONS) $(@)
```

Key points:

- **`KBUILD_OPTIONS`** forces the CONFIG_X to `m` for this build. No
  need to add anything to the kernel's defconfig.
- **`KBUILD_EXTRA_SYMBOLS`** for inter-module deps:

  ```makefile
  KBUILD_EXTRA_SYMBOLS := \
      $(abspath $(CURDIR)/../../boot/projectinfo/Module.symvers) \
      $(abspath $(CURDIR)/../../power/standby_netlink/Module.symvers)
  export KBUILD_EXTRA_SYMBOLS
  ```

  Each path is the OTHER module's `Module.symvers`. Order doesn't
  matter; the modpost step concatenates them.

  **CRITICAL: KBUILD_EXTRA_SYMBOLS goes in `Makefile`, NOT `Kbuild`.**
  In `Kbuild`, `$(M)` is set by the kbuild invocation rooted at
  `KERNEL_OBJ`, and `$(M)/../sibling/Module.symvers` is resolved
  *lexically* (string concatenation), not *canonically* (filesystem
  traversal). The resulting path looks valid but doesn't correspond
  to a real file; kbuild's symvers loader **silently skips it** and
  modpost then fails on unresolved symbols. The error you see is
  "ERROR: modpost: \"foo\" undefined!" — not "cannot find Module.symvers"
  — which makes the path-resolution issue easy to misdiagnose as a
  missing-export problem.

  In `Makefile`, `$(CURDIR)` is the module's own dir and
  `$(abspath ...)` canonicalizes the `..` traversals before kbuild
  ever sees the value. Use `$(abspath $(CURDIR)/...)` always; never
  rely on `$(M)/...` from Kbuild.

  See `dump_device_info/Makefile` and `oplus_projectinfo/qcom/Makefile`
  for canonical examples.
- **Don't replace the existing `Makefile`** without understanding
  what it had. OnePlus modules sometimes ship a Makefile that's
  actually an in-tree-style `obj-$(CONFIG_X) += <obj>.o` list — if
  so, that content moves to `Kbuild` and the new `Makefile` is the
  external-module driver above. Prefer to author `Kbuild` AND
  rewrite `Makefile`, not edit either in place.

---

## Step 3.5 — Kconfig authoring (when needed)

If the source uses a `CONFIG_OPLUS_FEATURE_*` (or similar) symbol via
`#ifdef`, the build will silently miscompile (skipping the `#ifdef`'d
code) unless that CONFIG is defined somewhere reachable. Three places
to land it:

**Option A — module-local Kconfig (most common):**
The OEM ships a Kconfig file alongside the source dir, e.g.
`vendor/oplus/kernel/dfr/common/keyevent_handler/Kconfig`:

```
config OPLUS_FEATURE_KEYEVENT_HANDLER
    tristate "generic keyevent_handler"
    default n
    help
      define this config to enable generic keyevent_handler.
```

If the file is already there, just confirm the parent
`vendor/<subsystem>/Kconfig` has a `source` line for it. Setting
`CONFIG_OPLUS_FEATURE_KEYEVENT_HANDLER=m` happens via the
external module's Makefile (`KBUILD_OPTIONS +=`) — no defconfig
fragment needed.

**Option B — defconfig fragment:**
Some configs (especially gates that affect compile-time behavior of
in-tree code, not just out-of-tree modules) need to land in
`kernel/oneplus/sm8850/arch/arm64/configs/lineage_genksyms_workaround.config`
or a sibling fragment. This applies if:
- An in-tree driver `#ifdef`s on the symbol
- Modpost's whitelist trim depends on it being known to Kconfig

**Option C — Bazel `local_defines` only:**
If the symbol is defined via Bazel `local_defines = [...]` and is
purely a `-DCONFIG_X` macro pass (no Kconfig backing it on the OEM
side either), translate to `ccflags-y += -DCONFIG_X` in the Kbuild.
This is appropriate for small per-module flags that don't need to
participate in `make menuconfig`.

**Anti-pattern:** `#ifdef`-stubbing the use sites in source. Don't.

---

## Step 4 — Wire into the device tree

In `device/oneplus/sm8850-common/BoardConfigCommon.mk`, append the
module's directory path to `TARGET_KERNEL_EXT_MODULES`:

```makefile
TARGET_KERNEL_EXT_MODULES := \
    ...existing entries... \
    oplus/kernel/dfr/common/keyevent_handler
```

The path is relative to `TARGET_KERNEL_EXT_MODULE_ROOT`
(which is `kernel/oneplus/sm8850-modules/vendor`).

Special syntax `<path>:kbuild` — used for modules that need a
Kbuild-style nested-directory build instead of the standard
external-module recipe (rare; see `oplus/kernel/device_info/oplus_fpga/fpga_monitor`
for the only current case). Most modules don't need this.

---

## Step 5 — Static check (run BEFORE the build)

Before spending a kernel-rebuild cycle, run the static translation
checker. Catches missing source files, name typos, and missing
dependencies in seconds rather than minutes.

```bash
python3 kernel/oneplus/sm8850-modules/tools/jm2/bazel_kbuild_diff.py \
    --bazel kernel/oneplus/sm8850-modules/vendor/<subsystem>/oplus_local_modules.bzl \
    --kbuild kernel/oneplus/sm8850-modules/vendor/<subsystem>/<dir>/Kbuild
```

Expect either `OK: no discrepancies found` or specific flagged items.
The diff covers the WHOLE BUILD.bazel — if you've only wired one
module from a multi-module bzl, expect "missing obj-m" errors for
the others. That's correct behavior; ignore them and check that
your one module isn't flagged.

When wiring up a parent-tree dir (one Kbuild that produces all
modules in the subsystem), the diff should come back clean.

---

## Step 6 — Build

```bash
~/android/iter_kernel.sh <iteration_tag>
```

Expected:
- mka kernel exits 0
- A `<MODULE>.ko` lands at
  `out/target/product/infiniti/obj/PACKAGING/kernel_modules_intermediates/lib/modules/<release>/updates/<MODULE>.ko`

**Always confirm the `.ko` exists before declaring success.** A
silently-mismatched CONFIG name produces no `.ko` while `mka kernel`
still exits 0. The build is a no-op without the obj-y/m hookup.

---

## Step 7 — Per-module validation

Use the wrapper (no need to hand-construct the find/symvers args):

```bash
kernel/oneplus/sm8850-modules/tools/jm2/validate_module.sh \
    out/target/product/infiniti/obj/PACKAGING/kernel_modules_intermediates/lib/modules/<release>/updates/<MODULE>.ko
```

Wrapper behavior:
- Auto-discovers all `Module.symvers` files in the modules tree
- Passes the canonical kernel symvers + every external's symvers
- Outputs the kmod_validate CSV row + stderr summary
- Exits 0 if verdict is `pass`, 1 otherwise

If the verdict isn't `pass`, the failure-mode taxonomy:
- `fail-no-vermagic` → kernel build regression (Phase H broke?)
- `fail-vermagic-mismatch` → built against a different kernel; rebuild
- `fail-crc-mismatch` → impossible for a same-build module unless a
  dep is wrong; check KBUILD_EXTRA_SYMBOLS
- `fail-crc-unknown-symbol` → missing inter-module symvers; add to
  KBUILD_EXTRA_SYMBOLS
- `fail-unresolved-imports` → consumer missing a KBUILD_EXTRA_SYMBOLS,
  OR the source uses a kernel-internal symbol that needs adding to
  `android/abi_gki_aarch64_oneplus_15_extras`, OR the consumer needs
  a new EXPORT_SYMBOL added to in-tree code (see EXPORT_SYMBOL_HANDLING.md)

---

## Step 7.5 — When exports_superset_check flags fail-missing-exports

Run `tools/jm2/exports_superset_check.py` against the build artifacts
in `updates/` after every brunch closeout. The verdict
`fail-missing-exports` flags modules whose source-built version
exports fewer symbols than the OEM prebuilt counterpart. The tool's
strict-superset rule is correct: in general, an OEM-prebuilt consumer
that depends on a missing symbol will fail to load against a
source-built producer that doesn't export it.

But the tool can't tell whether an OEM-prebuilt consumer for the
missing symbols is actually in our final image. That requires
per-consumer inspection, NOT just `depmod` — `modules.dep` checks
symbol-name resolution but doesn't catch call sites that reach a
missing symbol indirectly through a function pointer or wrapper.

When the tool flags `fail-missing-exports`, the diagnostic gate is:

```bash
# For each missing symbol, find OEM prebuilts that consume it
for sym in <missing-symbols>; do
    echo "Symbol: $sym"
    for ko in device/oneplus/infiniti-kernel/*.ko; do
        if nm "$ko" 2>/dev/null | grep -qE "^\s+U\s+${sym}$"; then
            echo "  $(basename $ko) consumes $sym"
        fi
    done
done
```

Then for each consumer found:

- If the consumer is also source-built (in `TARGET_KERNEL_EXT_MODULES`),
  our build replaces it; check whether our version still uses the
  missing symbol or has migrated to a different API.
- If the consumer is OEM-prebuilt-only and consumes the missing
  symbol, this is a **real runtime bug** — the module will fail to
  load. Either (a) add the missing EXPORT_SYMBOL in our source tree,
  or (b) source-build the consumer too with the new API.
- If no consumer references the missing symbol, the verdict is a
  *true positive on the static rule* but a *false positive on
  runtime impact*. Document explicitly in the sub-wave retro and
  move on.

**Don't accept a `depmod` pass alone as proof of safety.** depmod
catches `__versions` mismatches; the `nm U` check catches actual
call sites. Both are needed. (Surfaced 2026-05-03 in 2D's
oplus_hbp_core API-version-delta finding; see wave_02_status.md.)

---

## Step 7.6 — When obj-y subdir recursion silently produces no .ko

If you add a subdir to a parent Kbuild's `obj-y :=` and brunch
exits 0 but the expected .ko files aren't in the build output,
the silent skip is almost always a Make-side / C-side CONFIG-flag
asymmetry.

The audio-kernel-style canoe config is split across two files:

- `<root>/config/canoeauto.conf` — read by GNU make via
  `include $(AUDIO_ROOT)/config/canoeauto.conf`. Contains
  `export CONFIG_X=m` lines that set Make variables consumed by
  `obj-$(CONFIG_X) += foo.o` in per-leaf Kbuilds.
- `<root>/config/canoeautoconf.h` — included by the C compiler
  via `INCS += -include $(AUDIO_ROOT)/config/canoeautoconf.h`.
  Contains `#define CONFIG_X 1` lines that gate `#ifdef CONFIG_X`
  blocks in the source code.

Setting `#define CONFIG_X 1` in the .h alone is a no-op for
`obj-$(CONFIG_X)` — the Make variable is unset, so the obj line
expands to `obj- += foo.o` which doesn't queue anything to build.
The build succeeds because no error fires; the module just
doesn't get built.

The reverse failure also exists: setting `export CONFIG_X=m` in
.conf without `#define CONFIG_X 1` in .h produces a .ko whose
source `#ifdef CONFIG_X` blocks compile out, so the .ko is
syntactically built but functionally empty.

**Both files must list every CONFIG flag. Always set both.**

Diagnostic when a module silently fails to build:

```bash
# 1. Confirm the obj-y subdir was traversed
grep "Entering directory.*<subdir>" <brunch.log>

# 2. Confirm the module.order entry was created
grep <module-name> <root>/modules.order

# 3. If no entry: the obj-$(CONFIG_X) didn't fire.
#    Check both:
grep "CONFIG_X" <root>/config/canoeauto.conf      # Make-side
grep "CONFIG_X" <root>/config/canoeautoconf.h     # C-side
```

If the install path is non-standard (e.g.
`updates/oplus/codecs/aw882xx/foo.ko` rather than `updates/foo.ko`),
that's NOT a failure — it's just the obj-y subdir-recursive INSTALL
preserving the source-tree layout. The depmod step then flat-installs
to `vendor_dlkm/lib/modules/foo.ko`. Look at the final installed
location, not the build-tree intermediate.

**Verification rule of thumb:** check `find updates/ -name '*.ko'`
(recursive) when iterating, NOT `ls updates/*.ko` (flat). The flat
layout only appears post-depmod in `vendor_dlkm/lib/modules/`. A
flat-only check will report "module missing" even when it built
correctly under a multi-subdir M= dir. (Cost two iterations of
debugging in 2F.1 wire-up before the lesson landed.)

---

## Step 7.7 — When OEM-source -Wunterminated-string-initialization fires

Newer clang treats `-Wunterminated-string-initialization` as
`-Werror` (warns when a string literal exactly fills a fixed-size
char array, eliding the null terminator). OEM source frequently
trips this in `i2c_device_id::name` / `of_device_id::compatible`
fields where `I2C_NAME_SIZE = 20` exactly matches the compatible
string length.

OEM presumably built with an older toolchain that didn't flag
this, or had a per-module suppression. Their .ko ships with the
elided null terminator anyway — the of_match / i2c_match logic
treats name as bounded by the size, not the terminator, so the
match still works.

**Match OEM bug-for-bug**: add `-Wno-error=unterminated-string-initialization`
to `ccflags-y` in the affected Kbuild. Don't patch the source
to truncate the string by one char — that would change the
runtime DT/i2c match and would break the binding contract.

(Surfaced 2026-05-04 in 2F.2 magcvr_ak09973 + magcvr_mxm1120.
The `oplus,magcvr_ak09973` literal is 20 chars + null = 21 bytes
into a `char name[20]`; the null is silently elided.)

(Surfaced 2026-05-04 in 2F.1 wire-up; v1+v2 silently produced 0
audio modules until canoeauto.conf was updated alongside
canoeautoconf.h.)

---

## Step 7.8 — Recognize the OEM-Bazel-environment-coupled module class

A small but real fraction of OEM modules are not Bazel-portable in
the sense that translating their Bazel rules to kbuild produces a
buildable result. They depend on properties of OEM's Bazel build
environment that don't ship with the source tree. Trying to source-
build these without first replicating the Bazel environment is
open-ended — each iteration uncovers a new layer of implicit
dependency.

**Pre-build signature check.** Before committing to a full wire-up
of a new module, inspect against this 6-row table. If 3+ rows
match, time-box the wire-up attempt rather than committing
open-endedly.

| # | Property | Bazel-portable | OEM-Bazel-coupled |
|---|---|---|---|
| 1 | Source dir = build dir | yes | no — generated-at-build headers (e.g. JSON-driven `*_cfg.h`, scripts/ic_cfg_parse.py) |
| 2 | Bazel module name = output `.ko` name | yes | no — `name = "{target}_X"` with `out = "X.ko"` override |
| 3 | All `local_defines` covered by `OPLUS_ARCH_EXTENDS` (set in canoeautoconf.h) | yes | no — needs additional Bazel-only defines (`OPLUS_FEATURE_CHG_BASIC`, `CONFIG_QTI_BATTERY_CHARGER`, etc.) |
| 4 | Source uses only sibling-relative includes | yes | no — uses OEM-specific symlinks to non-existent paths (e.g. `kernel_platform/common/drivers/gpio/gpiolib.h`) |
| 5 | Cross-leaf consumers all source-built or kernel-internal | yes | no — needs additional new ext-modules to satisfy `KBUILD_EXTRA_SYMBOLS` |
| 6 | Single Kbuild + Makefile suffices | yes | no — needs `Makefile.json-build`-style sub-makefile mechanisms for codegen, custom `.lds`, etc. |

**Disposition for matched modules.** Source-build infrastructure
goes in the tree (Kbuild + Makefile + any generated-headers wiring)
so future work can resume from where the attempt stopped, but the
module is NOT added to `TARGET_KERNEL_EXT_MODULES`. OEM prebuilt
ships in the meantime via `BOARD_VENDOR_KERNEL_MODULES`. Resume
the source-build attempt only if a future engineering investment
in replicating OEM's Bazel environment paths becomes worthwhile
(upstreaming, security audit, multi-device port).

**Calibration note.** The 0-EXPORT prior over Wave 2 sub-waves
applies to **Bazel-portable** modules. OEM-Bazel-environment-
coupled modules don't run the test (build never reaches MODPOST
cleanly), so they're neither evidence for nor against the prior.
Don't extend the prior to a new module class without first
checking the 6-row signature.

(Surfaced 2026-05-05 by 2F.3 charger v2 — 14 brunch iterations
without convergence; each iteration uncovered a new layer. Other
Wave 2 sub-waves landed in 1–4 iterations.)

---

## Step 7.8a — OEM-build-system-coupled module classes (meta)

Wave 2 has identified two distinct module classes where OEM has
build-system infrastructure our tree lacks. Both share the
meta-pattern "OEM-build-system-coupled," but they manifest
differently and have different remediation paths. Future
sub-waves should expect to identify additional sub-classes as
different module trees expose different OEM-specific build
mechanisms.

| Sub-class | Where | Symptom | Remediation |
|---|---|---|---|
| OEM-Bazel-environment-coupled (Step 7.8 above) | Ext-module trees translated to TARGET_KERNEL_EXT_MODULES | 6+ Bazel-only build assumptions; iteration count exceeds 2× running max without convergence | **Defer** to OEM prebuilt; preserve in-tree build infrastructure for future resumption |
| OEM-techpack-overlay-coupled (Step 7.8b below) | Kernel-internal drivers under `kernel/oneplus/sm8850/drivers/...` | Source file + Kconfig present, but Makefile in same directory has no `obj-$(CONFIG_X)` entry | **Replicate**: per-module triage — patch Makefile for runtime-active modules; defer OEM-internal/diagnostic-only modules to OEM prebuilt |
| OEM-prebuilt-sibling-producer (Step 7.8d below) | Source-built consumer references symbols exported by an OEM-prebuilt-only producer (typical when sibling subsystem is deferred to a later wave) | modpost: `undefined! [consumer.ko]`; depmod: `needs unknown symbol` | **Bridge**: synth_symvers (modpost layer) + BOARD_VENDOR_KERNEL_MODULES_DEPMOD_BRIDGE_DIR (depmod layer). Both required. |

**Three remediation paths emerge: defer / replicate / bridge.**
The disposition decision when OEM has build infrastructure we
don't depends on which class fits and what the cost ratio looks
like. Don't conflate the classes: a Bazel-coupled module is not
fixed by a bridge; a prebuilt-sibling is not fixed by replicating
OEM's Makefile; a techpack-overlay is not fixed by deferral.

When a future module is identified as OEM-build-system-coupled,
classify it into the relevant sub-class. The disposition workflow
differs by sub-class. If a new manifestation emerges that doesn't
fit either, document it as a third sub-class.

**Related verification pitfall (not an OEM-coupling class but
surfaced during OEM-techpack-overlay-coupled remediation):**
name-collision-pass-exact false-positive — see Step 7.8c.

---

## Step 7.8b — OEM-techpack-overlay-coupled module class

Kernel-internal drivers (under `kernel/oneplus/sm8850/drivers/...`,
not external modules) where the source file exists, the Kconfig
entry exists, but the Makefile in the same directory has **no
`obj-$(CONFIG_X) += foo.o`** entry. Setting `CONFIG_X=m` alone
won't compile the module — the source isn't wired into the
kernel's build graph at the Makefile level. OEM ships these via
Qualcomm's tech-package overlay (an out-of-tree patch system that
adds vendor-specific obj entries to in-tree Makefiles); our tree
lacks the overlay patches.

**Symptom signature.**

```bash
# 1. Source file present?
ls drivers/<subsystem>/qcom-foo.c  # found

# 2. Kconfig entry present?
grep "config QCOM_FOO" drivers/<subsystem>/Kconfig  # found

# 3. Makefile obj-$() entry present?
grep "qcom-foo\.o" drivers/<subsystem>/Makefile  # NOT FOUND ← signature
```

If all three are needed but the third is missing, you're in this
class.

**Disposition framework.**

Per-module triage by runtime role:

- **Secure-boot or measured-boot path** (e.g., spss/q6v5
  secure-side processor) → patch Makefile to add the obj-$()
  entry. Source is upstream; the patch is a 1-line addition.
- **Active runtime hardware functionality** (regulators, ADCs,
  haptics, PMIC bus, low-power management) → patch. These do
  meaningful work on canoe.
- **Diagnostic / debug only** (sleep stats, ramoops dynamic
  config, iommu debug) → defer to OEM prebuilt. They're
  already shipping; source-build adds little value.
- **OEM-internal vendor extension with no upstream equivalent**
  → defer. We couldn't upstream the Makefile patch anyway.

**Depends-on check (also required).**

Even after Makefile patch, the build will fail if the CONFIG has
unmet Kconfig dependencies. Always grep `Kconfig` for the
`depends on` line and confirm each dependency is satisfiable in
our tree:

```bash
grep -A5 "config QCOM_FOO" drivers/<subsystem>/Kconfig | grep "depends on"
```

The Makefile patch and the depends-on check are independent;
both need to clear before brunch.

**Maintenance cost.**

Each Makefile patch is small but compounds across kernel rebases.
For each AOSP/Qualcomm kernel update, every patched obj-$()
entry needs to either land cleanly (if the upstream Makefile
didn't change) or be re-applied with conflict resolution.
Across multiple rebases this is real maintenance burden — factor
into the patch-vs-defer decision.

**Mandatory verification: modinfo description match.**

When wiring up a kernel-internal driver, MULTIPLE source files in
different parts of the tree may produce a .ko with the same name.
`obj-$(CONFIG_X) += foo.o` from `drivers/A/Makefile` and `obj-$(CONFIG_Y)
+= foo.o` from `drivers/B/Makefile` both produce `foo.ko`; whichever
was wired up wins, and exports_superset_check at 0/0 EXPORTs will
pass either way (name-collision-pass-exact failure mode).

Before declaring a kernel-internal source-build complete, **always**
verify:

```bash
# Our build's description should match OEM's
diff <(modinfo our-build/foo.ko 2>/dev/null | grep '^description:') \
     <(modinfo OEM-prebuilt/foo.ko 2>/dev/null | grep '^description:')
```

If the descriptions don't match, the wire-up targeted the wrong
source. Defer + re-investigate; don't ship.

For the failure mode where two different sources in the tree
both produce a .ko of the same name (and exports_superset_check
passes false-positively), see Step 7.8c.

(Surfaced 2026-05-05 in 2E qcom_qti pre-flight: 11 of 25 modules
have source + Kconfig but no Makefile obj-$() entry. OEM ships
via tech-package overlay; our tree lacks it.)

---

## Step 7.8c — Name-collision false-positive (a.k.a. name-collision-pass-exact)

**Class definition.** A source-built `.ko` shares its filename
with the corresponding OEM prebuilt `.ko`, but is built from a
*different* source path (different driver, different feature
scope, different runtime behavior). Because both .kos export zero
symbols (or coincidentally identical export sets),
`exports_superset_check` reports `pass-exact` falsely. The
build is structurally clean and the static check is green, but
the deployed module is the wrong driver.

**Stable signature (reproducible, transferable to future
sub-waves).** Three signals jointly characterize the class:

1. `.ko` filenames match OEM (collision precondition)
2. Both `.ko`s export zero symbols — `exports_superset_check`
   verdict `pass-exact` 0/0 (the false positive)
3. `modinfo description:` differs OR `.ko` sizes differ by
   more than ~50% (after accounting for debug info)

Any one of (3)'s two sub-signals is sufficient to flag the
collision; both together is unambiguous.

This is **not** an OEM-build-system-coupling class (Step 7.8a),
because the issue isn't where OEM wires the module — it's where
*we* wired ours. It's a verification false-positive that surfaces
during OEM-techpack-overlay-coupled remediation (Step 7.8b) when
the OEM .ko name doesn't uniquely encode its source path.

**Why exports_superset_check misses it.**

The check compares the EXPORT_SYMBOL set of our build against
OEM's. If both sets are empty (a leaf consumer driver that
provides no exports for other modules), the check passes
trivially regardless of what code is actually inside. Empty ⊇
empty is always true. The check is sound for its design (it
catches *missing exports*, not wrong-source builds).

**Detection signature.**

| Signal | Behavior in name-collision case |
|---|---|
| `.ko` filename | matches OEM ✓ (collision precondition) |
| `exports_superset_check` verdict | `pass-exact` 0/0 — false positive |
| `modinfo description:` | **mismatched** ← primary signal |
| `.ko` size | typically 2–4× different (debug info aside, the actual code differs) |
| `nm -D` symbol set | different (different undefineds, different statics) |
| `modinfo depends:` | typically different (different framework deps) |

The `modinfo description:` field is the primary distinguishing
signal because it's a single static string written into the
source's `MODULE_DESCRIPTION()` macro and survives strip. Size
deltas can also come from debug info presence, so size alone is
weak. nm symbol-set compare is strong but expensive.

**Mandatory verification (also documented in Step 7.8b).**

```bash
diff <(modinfo our-build/foo.ko 2>/dev/null | grep '^description:') \
     <(modinfo OEM-prebuilt/foo.ko 2>/dev/null | grep '^description:')
```

If output is empty → match → safe. If diff prints anything →
wrong source. Defer + re-investigate.

**Mitigation (pre-build).**

Before patching `obj-$(CONFIG_X) += foo.o` for a kernel-internal
module, confirm `foo.c` is the right source by reading its
`MODULE_DESCRIPTION()` macro and comparing against
`modinfo OEM-prebuilt/foo.ko | grep description:`. Don't rely
on filename alone — kernel trees regularly have multiple `foo.c`
or near-name-collisions across `drivers/<subsys>/`.

**Surfaced 2026-05-05 during 2E batch 1.**

`qcom_lpm.ko` wire-up mistakenly built
`drivers/soc/qcom/qcom_lpm_monitor.c` (a debug "LPM monitor"
driver, ~28 KB output) when OEM's `qcom_lpm.ko` is the cpuidle
governor at `drivers/cpuidle/governors/qcom-lpm.c` plus
`qcom-cluster-lpm.c` and `qcom-lpm-sysfs.c` (~89 KB output, gated
on `CONFIG_SCHED_WALT`). Both leaf consumers, both 0-export →
pass-exact 0/0. Modinfo description was the only static signal:
"QTI LPM monitor" (ours) vs "QTI cpuidle LPM governor" (OEM).

The wire-up was reverted (commit `c6c8c60a43a3`) and qcom_lpm
deferred to a Kconfig+Makefile batch where the multi-source
bundle and SCHED_WALT dep gate can be authored correctly.

**Why this class matters (runtime consequence).**

Without the modinfo-match check, the wrong-source `qcom_lpm.ko`
would have shipped to vendor_dlkm, loaded at boot, and registered
nothing useful as a cpuidle governor. The device would have been
deployed without its low-power-management governor entirely. At
hardware bring-up (Phase 6) the symptom would surface as
"battery drains 3× faster than expected" or similar runtime
behavior with no obvious link to the kernel-module wire-up
days/weeks earlier. None of the prior verification stack catches
it: depmod passes (the .ko is well-formed), vermagic matches
(same kernel build), exports_superset_check passes vacuously
(0/0). The modinfo-description check is the load-bearing
diagnostic that closes the gap.

This is exactly the failure-mode class that pre-flash
calibration discipline is meant to catch. Treat the modinfo
check as a non-negotiable verification step for every
kernel-internal module wire-up, not an optional sanity check.

---

## Step 7.8d — OEM-prebuilt-sibling-producer class (modpost + depmod bridges)

**Class definition.** A source-built consumer module references
symbols exported by a producer .ko that we don't source-build —
the producer ships only as an OEM prebuilt under
`device/<vendor>/<board>-kernel/`. Typical case: a sub-wave
source-builds a cross-tree consumer (e.g. bt-kernel's btpower.ko)
that depends on a sibling subsystem we deferred (e.g. WLAN's
cnss_utils.ko). The producer is shipping today via
`BOARD_VENDOR_KERNEL_MODULES`; modprobe at runtime resolves the
dependency fine because both .kos are in vendor_dlkm. The build,
however, runs two checks the OEM-prebuilt isn't visible to:
modpost and depmod. Both fail despite runtime correctness.

**This class has TWO layers, requiring TWO bridge primitives.**
Both primitives are needed; using only one isn't enough.

### Layer 1 — modpost-layer bridge (synth_symvers)

Modpost validates that every undefined external symbol in our
source-built `.ko` resolves against either vmlinux's `Module.symvers`
or against an explicitly-listed `Module.symvers` from
`KBUILD_EXTRA_SYMBOLS`. OEM-prebuilt producers don't have a
`Module.symvers` in our tree because we don't build them.

**Tool:** `tools/jm2/synth_symvers.py`. Extracts the CRC and
GPL/non-GPL classification for a symbol from an OEM .ko's
`__crc_*` + `__ksymtab` sections, emits a Module.symvers row
in the kernel's exact format (`0x<crc>\t<sym>\t<src>\t<EXPORT_*>\t<ns>`).
Usage:

```bash
python3 tools/jm2/synth_symvers.py \
  --from-ko device/<vendor>/<board>-kernel/<producer>.ko \
  --symbol <symbol-name> \
  --src-path <plausible-source-path-of-producer> \
  --out vendor/qcom/opensource/<producer-tree>/Module.symvers
```

The output Module.symvers is a synthetic seed (force-add to git
overriding the standard `.gitignore: Module.symvers` rule —
explain provenance in the commit message). Wire into the
consumer ext-module's wrapper Makefile via:

```makefile
KBUILD_EXTRA_SYMBOLS := $(abspath $(CURDIR)/../<sibling-tree>/Module.symvers)
KBUILD_EXTRA_SYMBOLS += <other-paths-as-needed>
export KBUILD_EXTRA_SYMBOLS
```

**Use `$(CURDIR)`, not `$(M)`.** LineageOS kernel.mk passes
`M=../sm8850-modules/.../<consumer>` as a CLI override which
makes `$(M)` a relative path; `$(abspath $(M)/../...)` then
resolves with CWD-prefixing and produces a doubled-up bogus
path. `$(CURDIR)` is always the absolute Make CWD regardless of
`M=` override. (Surfaced 2026-05-07 in 2I bt-kernel v4 → v5
iteration; pattern matches `datarmnet-ext/*/Makefile`.)

### Layer 2 — depmod-layer bridge (BOARD_VENDOR_KERNEL_MODULES_DEPMOD_BRIDGE_DIR)

Even with modpost satisfied, Lineage's `kernel.mk` runs depmod
on the source-built module set and greps stderr for `"needs
unknown symbol"`. depmod ignores `Module.symvers` files; it
walks the staging dir and reads each .ko's symbol table directly.
Without the OEM producer .ko in the staging dir, depmod can't
find the exporter and errors.

**Patch:** Lineage's `vendor/lineage/build/tasks/kernel.mk`
`build-image-kernel-modules-lineage` function gains a `$(9)`
parameter for the OEM-prebuilt-bridge directory. The directory's
.kos are flat-staged into the depmod staging dir BEFORE the
source-built modules are copied, so source-built versions
override OEM on name collision (preserving our build's
authority over modules we replace) while OEM-only producers
become visible to depmod's symbol resolver.

**Device opt-in:** set
`BOARD_VENDOR_KERNEL_MODULES_DEPMOD_BRIDGE_DIR` in the device's
BoardConfig to the OEM prebuilt directory:

```makefile
BOARD_VENDOR_KERNEL_MODULES_DEPMOD_BRIDGE_DIR := \
    $(COMMON_PATH)/../<board>-kernel
```

Three vendor_dlkm depmod call sites in kernel.mk pass this
through as `$(9)`. Empty by default; no behavior change for
devices that don't opt in.

**Why two primitives, not one.** Modpost reads `Module.symvers`
files (we synthesize one); depmod reads `.ko` symbol tables
(we stage the actual OEM .ko). The semantics differ; the
plumbing differs. Conflating them produces an incomplete bridge
that passes the early stage and fails the later stage — exactly
what 2I v3 → v5 surfaced (modpost passed at v5 only to fail at
depmod immediately after).

### Detection signature

| Stage | Symptom |
|---|---|
| modpost | `ERROR: modpost: "<sym>" [<consumer>.ko] undefined!` |
| depmod | `depmod: WARNING: <consumer>.ko needs unknown symbol <sym>` followed by `ERROR: kernel module(s) need unknown symbol(s)` |

Producer identification:

```bash
# Find the .ko in OEM prebuilts that exports the symbol
nm <oem-prebuilt-dir>/*.ko | grep " T <symbol>" | head -3
# Or if the symbol's gated, check .modinfo
modinfo <oem-prebuilt-dir>/<candidate>.ko | grep '^description:'
```

### Disposition framework

- **Source-built consumer + OEM-prebuilt producer (typical
  case):** apply both bridges. Cheap once primitives exist.
- **Source-built producer + OEM-prebuilt consumer (inverse):**
  no bridge needed for our build (consumer is OEM, runs through
  OEM build flow); we just need to ensure our source-built
  producer exports the same symbols at the same CRCs as OEM's.
  Verified by `exports_superset_check` and CRC consistency.
- **Both source-built (eventually):** standard ext-module flow
  via `KBUILD_EXTRA_SYMBOLS` pointing at the producer's actual
  Module.symvers (no synthesis, no depmod-bridge). 2C audio-kernel
  + 2I bt-kernel's swr_* dependency is this case.

**Don't drop the consumer's reference to satisfy modpost.**
Compiling out a `#ifdef CONFIG_X` gate to avoid the dep
introduces behavioral divergence vs OEM (the same calibration
discipline that made 2F.3 a defer rather than a stub-and-ship).
The bridge approach preserves parity.

**Don't source-build the producer just to satisfy modpost.**
Pulling Wave 5 (or whichever wave the producer belongs to)
forward to unblock the current sub-wave is exactly the scope
creep that 2F.3's 14-iteration overrun demonstrated against.
Use the bridge primitives instead.

### Surfaced 2026-05-07 during 2I batch 1.

`bt-kernel/pwr/btpower.c` references `cnss_utils_fmd_status`
under `#ifdef CONFIG_FMD_ENABLE` (FM-coexistence-detection
power-coordination path). OEM target.bzl `define_canoe()` enables
`CONFIG_FMD_ENABLE` for canoe. The producer `cnss_utils.ko` is
in `wlan/platform/` (Wave 5, deferred). v3 surfaced the modpost
half (multiple swr_* + cnss_utils symbols undefined); the
synth_symvers + KBUILD_EXTRA_SYMBOLS fix landed at v5. v5
surfaced the depmod half (same symbol re-flagged at depmod);
the kernel.mk + BoardConfig bridge fix landed at v6.

The class is now fully characterized with both bridges
documented. Future sub-waves should expect to use both.

---

## Step 7.9 — Iteration-count escalation as structural-mismatch signal

The 6-row signature in Step 7.8 is best run pre-build, but a
sub-wave can also escape it (Bazel-portable on the surface,
structurally coupled in deeper layers). The iteration count is
the in-flight signal:

**Rule.** If a sub-wave's brunch iteration count reaches **2x
the previous max** without converging on green, pause the
tactical-fix loop and explicitly run the Step 7.8 signature
check. The recurrence-vs-new-class pattern of bugs across
those iterations is the diagnostic — recurring classes mean
the recipe is working; new classes per iteration mean
structural mismatch.

**Threshold sources.** Track the running max iteration count to
green across Wave 2:

| Sub-wave | Iterations to green | Running max |
|---|---|---|
| 2H | 4 | 4 |
| 2D | 1 | 4 |
| 2F.1 | 3 | 4 |
| 2F.2 | 4 | 4 |
| 2F.3 | (n/a, deferred at 14) | 4 |

So at 2026-05-05 the escalation threshold is **8 iterations**
(= 2 × 4). When the next sub-wave reaches v8 without a green
build, the prep agent should pause and run Step 7.8.

**Why not earlier.** A linear "stop at v6" rule would over-trigger
on legitimately complex but Bazel-portable modules. 2F.2 took 4
iterations cleanly; some modules will too. The 2x-of-running-max
rule rises naturally as the project's ceiling rises and stays
calibrated to actual difficulty.

**What pause means.** Pause = stop the next tactical fix. Do
NOT mean "abandon"; do mean "characterize before continuing."
Run the Step 7.8 6-row check. Look at the bug-class pattern
across iterations: recurrence-heavy = continue; novel-class-per-iter
= structural mismatch, deferral candidate.

(Surfaced 2026-05-05 in 2F.3 post-mortem. Charger v2's
structural mismatch was *visible* by iteration 4–5 but the
decision to stop didn't happen until iteration 14. Earlier
recognition would have saved ~9 iterations of effort. This
rule encodes the lesson.)

---

## Step 7.10 — Canonical cumulative-evidence format (two metrics)

Wave 2's "0 EXPORTs cumulative" framing was load-bearing in
spirit but degenerate in form: every sub-wave through 2E batch 1
had OEM-EXPORT count = 0 and source-built EXPORT count = 0,
which made the literal "0 EXPORTs" wording ambiguous between
two distinct metrics. Sub-wave 2I forces the disambiguation —
bt-kernel modules export 5 symbols; the cumulative count goes
non-zero.

The disambiguation: track **two separate metrics, not one
renamed.**

### Metric A — Missing EXPORTs cumulative (calibration metric)

Counts EXPORT_SYMBOL declarations the project has had to add to
upstream kernel files because a source-built module needs a
symbol the kernel doesn't currently export. This was always the
metric the EXPORT_SYMBOL upstream-cadence retirement criterion
referred to. Wave 2 has been at 0 across all sub-waves to date.

Aggregate cumulatively across all sub-waves. Retire the
upstream-submission-pipeline tracker when this stays ≤ 2 through
Wave 2 close.

### Metric B — OEM-EXPORT delivery (per-sub-wave verification)

Counts whether our source-built `.ko`s expose the same
EXPORT_SYMBOL surface as the OEM prebuilts they replace.
`pass-exact N/N` per module from `exports_superset_check`. This
is binary per-module and per-sub-wave; it does NOT aggregate
across sub-waves the way Metric A does.

Track as "passing sub-wave count / total sub-wave count" and the
per-sub-wave EXPORT total.

### Canonical line (post-2I onwards)

> **Missing EXPORTs: 0 cumulative across all sub-waves.** Buffer: `<B>`.
> Evidence: `<N>` ext-module sub-waves + `<M>` kernel-internal-already-built + `<P>` techpack-overlay-patched + ... = `<N+M+P+...>` data points across `<C>` classes.
> Per-sub-wave OEM-EXPORT verification: `<S>`/`<T>` sub-waves passing.

Field semantics:
- **Missing EXPORTs**: Metric A. Cumulative across all sub-waves.
- **N, M, P, ...**: per-class data-point counts (modules in each
  class). Each named class gets its own term. Don't fold
  differently-shaped classes together.
- **C**: count of distinct module classes spanned.
- **Buffer B**: modules whose disposition is pending (deferred
  awaiting audit, mid-batch, or characterization in flight).
  Not in the cumulative count yet.
- **S/T**: Metric B. Number of sub-waves whose OEM-EXPORT
  verification passed (typically all of them) over total
  sub-wave count.

### Example (post-2E batch 1, pre-2I)

> **Missing EXPORTs: 0 cumulative across all sub-waves.** Buffer: 2.
> Evidence: 8 ext-module sub-waves + 14 kernel-internal-already-built + 2 techpack-overlay-patched = 24 data points across 3 classes.
> Per-sub-wave OEM-EXPORT verification: 8/8 sub-waves passing (all at 0/0 OEM-export count).

### Example projection (post-2I, assuming 4/4 modules clean)

> **Missing EXPORTs: 0 cumulative across all sub-waves.** Buffer: 2.
> Evidence: 9 ext-module sub-waves + 14 kernel-internal-already-built + 2 techpack-overlay-patched = 28 data points across 3 classes.
> Per-sub-wave OEM-EXPORT verification: 9/9 sub-waves passing (8 at 0/0; 2I at 5/5 pass-exact across btpower + btfmcodec).

### Why two metrics, not one

Metric A is about KMI surface evolution (are we adding API to
the kernel?). Metric B is about per-build verification (do our
modules match OEM's exported surface?). These are answering
different questions:
- A says "we did NOT need to expand the kernel's API."
- B says "what we built matches what OEM ships, symbol-wise."

A staying at 0 across Wave 2 is the upstream-submission story.
B staying at 100% pass-rate is the per-sub-wave verification
story. Conflating them — as the original "0 EXPORTs cumulative"
framing did — produced a true claim that nevertheless fell
apart the moment a sub-wave shipped non-zero exports. Keeping
them separate keeps each claim sharp.

### Drift to avoid

- ❌ "0 EXPORTs cumulative" — old framing; ambiguous post-2I
- ❌ "24 sub-waves at 0" — collapses class structure (Metric A)
- ❌ "8 + 14 + 2 = 24, all clean" — drops the class qualifier
- ❌ Reporting only one metric — drops the calibration vs
  verification distinction

If a future sub-wave introduces a new module class, add a new
term to the Evidence line (`+ Q Kconfig+Makefile-patched`, etc.)
and increment `C`. Resist the urge to fold it into an existing
term unless the class is genuinely the same shape.

---

## Step 8 — Confirm the OEM-kernel-prebuilt fallback still works

Each commit must keep the `BOARD_VENDOR_KERNEL_MODULES` (OEM-prebuilt
wildcard) path green so we can always retreat to a flashable build.

Concrete check: build the device tree's fallback hybrid and verify
depmod is clean:

```bash
# This builds the ROM with the wildcard prebuilt set still in scope.
~/android/iter_brunch.sh fallback_check_<tag>
# After it completes, confirm depmod did not error:
grep -E "depmod.*ERROR|ERROR.*depmod" build_logs/build_brunch_fallback_check_<tag>.log
```

If your wire-up overwrites a same-named OEM prebuilt at install time
(via `kernel/oneplus/sm8850-modules` → `vendor_dlkm/lib/modules/`),
this is fine — it's the expected pattern. But if depmod surfaces
unresolved-symbol errors that the OEM prebuilt set was satisfying
before, you've broken the fallback and need to address it (likely
by adding the symbol to `abi_gki_aarch64_oneplus_15_extras`).

---

## Anti-patterns (forbidden — see IMPLEMENTATION_PLAN.md §12)

- ❌ **Don't `#ifdef`-stub a missing CONFIG.** If the source uses
  `CONFIG_OPLUS_FEATURE_FOO` and it's not in any Kconfig, add the
  Kconfig stanza (`config OPLUS_FEATURE_FOO ...`) and surface the
  knob via `KBUILD_OPTIONS`. Don't blank out the use sites.
- ❌ **Don't disable CONFIG_MODVERSIONS.** Module CRC validation is
  how we know things will load. Suppressing it = silent breakage at
  modprobe time.
- ❌ **Don't FORCE_LOAD as a coping mechanism.** Reserved for the
  Phase 8 Bucket-D residual.
- ❌ **Don't skip a module to declare a wave done.** Every module
  in scope must build, validate, and pass `wave_gate.py`.
- ❌ **Don't break the OEM-kernel-prebuilt fallback.** Each commit
  should keep `BOARD_VENDOR_KERNEL_MODULES` (the OEM prebuilt
  wildcard) working as a recovery path.

---

## Anti-pattern: silent CONFIG name drift

A subtle but common pitfall: a module's source uses
`CONFIG_OPLUS_FEATURE_FOO` but the Bazel `local_defines` says
`CONFIG_OPLUS_FOO` (no FEATURE prefix). Pick the source's name in
the Kbuild's `obj-$(CONFIG_X) += $(MODULE).o` line; the build will
silently produce nothing if you pick the wrong name (no obj-y/m =>
no .ko, but mka exits 0).

After every wire-up, **always confirm a `.ko` exists** in
`out/.../updates/`. If not, the CONFIG name is mismatched somewhere.

---

## Allowed scope expansion

The one allowed scope expansion during wire-up: **adding missing
`EXPORT_SYMBOL`s** to in-tree kernel code when a downstream external
module needs a symbol that isn't currently exported. These are cheap,
sometimes necessary, and may warrant upstream submission. Track them
in `kernel_export_additions.md` (one line per addition: symbol,
consumer module, file added in).

---

## Proof-point reference (Phase 4)

`oplus_bsp_dfr_keyevent_handler` was the simplest possible wire-up:

| Field | Value |
|---|---|
| Bazel def | `vendor/oplus/kernel/dfr/oplus_local_modules.bzl` |
| Source | `vendor/oplus/kernel/dfr/common/keyevent_handler/keyevent_handler.c` (157 lines) |
| Imports | None vendor-internal — basic kernel notifier APIs only |
| Exports | `keyevent_register_notifier`, `keyevent_unregister_notifier` |
| `ko_deps` | (one declared but not actually consumed at symbol level — omitted) |
| `local_defines` | `CONFIG_OPLUS_FEATURE_KEYEVENT_HANDLER` |

Files added/changed for the wire-up:
- New: `vendor/oplus/kernel/dfr/common/keyevent_handler/Kbuild`
- Replaced: `vendor/oplus/kernel/dfr/common/keyevent_handler/Makefile`
- Edited: `device/oneplus/sm8850-common/BoardConfigCommon.mk`
  (one line in `TARGET_KERNEL_EXT_MODULES`)

Build time: under 1 minute for the incremental rebuild after Phase H.
Validation: `kmod_validate.py` reports `pass`, vermagic and CRCs match
our kernel exactly.
