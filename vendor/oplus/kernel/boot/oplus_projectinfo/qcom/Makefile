# SPDX-License-Identifier: GPL-2.0-only
KBUILD_OPTIONS += CONFIG_OPLUS_FEATURE_BOOT_PROJECTINFO=m

# oplus_project.c references build_variant / serial_no from cmdline_parser/.
KBUILD_EXTRA_SYMBOLS := $(abspath $(CURDIR)/../../cmdline_parser/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(KBUILD_OPTIONS) $(@)
