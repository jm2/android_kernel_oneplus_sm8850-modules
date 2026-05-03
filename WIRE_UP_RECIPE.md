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
