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

For the proof-point above, the `ko_deps` line is omitted in our wire-up
because keyevent_handler doesn't actually use anything from
oplus_bsp_boot_projectinfo at the symbol level (the dep was a Bazel
build-ordering hint, not a real symvers consumer). When you can't
tell, prefer to wire the KBUILD_EXTRA_SYMBOLS — extra deps are harmless,
missing deps cause modpost errors.

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
- **Don't replace the existing `Makefile`** without understanding
  what it had. OnePlus modules sometimes ship a Makefile that's
  actually an in-tree-style `obj-$(CONFIG_X) += <obj>.o` list — if
  so, that content moves to `Kbuild` and the new `Makefile` is the
  external-module driver above. Prefer to author `Kbuild` AND
  rewrite `Makefile`, not edit either in place.

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

## Step 5 — Build and validate

```bash
~/android/iter_kernel.sh <iteration_tag>
```

Expected outcome (for a single new module):

- mka kernel exits 0
- A `<MODULE>.ko` lands at
  `out/target/product/infiniti/obj/PACKAGING/kernel_modules_intermediates/lib/modules/<release>/updates/<MODULE>.ko`
- Run validator:
  ```bash
  python3 kernel/oneplus/sm8850-modules/tools/jm2/kmod_validate.py \
      --symvers out/target/product/infiniti/obj/KERNEL_OBJ/Module.symvers \
      $(find kernel/oneplus/sm8850-modules -name Module.symvers \
        -printf -- '--symvers %p\n' | tr -d \\n) \
      --stablelist kernel/oneplus/sm8850/android/abi_gki_aarch64_oneplus_15 \
      --header \
      out/.../updates/<MODULE>.ko
  ```
- Verdict should be `pass`. Any `fail-*` means iterate:
  - `fail-no-vermagic` → kernel build issue (Phase H regression?)
  - `fail-vermagic-mismatch` → built against a different kernel; rebuild
  - `fail-crc-mismatch` → impossible for a same-build module unless
    a dep is wrong; check KBUILD_EXTRA_SYMBOLS
  - `fail-crc-unknown-symbol` → missing inter-module symvers; add to
    KBUILD_EXTRA_SYMBOLS
  - `fail-unresolved-imports` → check if the consumer's missing a
    KBUILD_EXTRA_SYMBOLS, or if the source uses a kernel-internal
    symbol that needs adding to `android/abi_gki_aarch64_oneplus_15_extras`

---

## Step 6 — Cross-check against the BUILD.bazel

```bash
python3 kernel/oneplus/sm8850-modules/tools/jm2/bazel_kbuild_diff.py \
    --bazel kernel/oneplus/sm8850-modules/vendor/oplus/kernel/dfr/oplus_local_modules.bzl \
    --kbuild kernel/oneplus/sm8850-modules/vendor/oplus/kernel/dfr/common/keyevent_handler/Kbuild
```

Expect either `OK: no discrepancies found` (typical for clean wire-ups)
or specific flagged items requiring manual review.

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
