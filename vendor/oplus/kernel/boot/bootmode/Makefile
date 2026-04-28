# SPDX-License-Identifier: GPL-2.0-only
KBUILD_OPTIONS += CONFIG_OPLUS_FEATURE_BOOTMODE=m

# boot_mode.c references oplus_ftm_mode / sku / bootmode / startup_mode /
# charger_present which live in ../cmdline_parser/.
KBUILD_EXTRA_SYMBOLS := $(abspath $(CURDIR)/../cmdline_parser/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(KBUILD_OPTIONS) $(@)
