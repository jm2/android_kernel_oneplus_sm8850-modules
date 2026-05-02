# SPDX-License-Identifier: GPL-2.0-only
# External-module driver (matches the bootmode/cmdline_parser pattern used
# by the existing 36 source-built externals from kernel/oneplus/sm8850-modules).

KBUILD_OPTIONS += CONFIG_OPLUS_FEATURE_KEYEVENT_HANDLER=m

# No ko_deps in BUILD.bazel → no KBUILD_EXTRA_SYMBOLS needed.

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(KBUILD_OPTIONS) $(@)
