# SPDX-License-Identifier: GPL-2.0-only
# External-module driver.

KBUILD_OPTIONS += CONFIG_OPLUS_FEATURE_PMIC_MONITOR=m

# No ko_deps in BUILD.bazel — module is self-contained.

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(KBUILD_OPTIONS) $(@)
