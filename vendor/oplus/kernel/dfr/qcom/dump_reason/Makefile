# SPDX-License-Identifier: GPL-2.0-only
# External-module driver.

KBUILD_OPTIONS += CONFIG_OPLUS_FEATURE_DUMP_REASON=m

# Bazel ko_deps:
#   //vendor/oplus/kernel/dfr:oplus_bsp_dfr_dump_device_info → wave 1 sibling
#   //soc-repo:.../drivers/soc/qcom/smem                     → in-tree, kernel symvers
KBUILD_EXTRA_SYMBOLS := \
    $(abspath $(CURDIR)/../dump_device_info/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(KBUILD_OPTIONS) $(@)
