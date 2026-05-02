# SPDX-License-Identifier: GPL-2.0-only
# External-module driver.

KBUILD_OPTIONS += CONFIG_OPLUS_FEATURE_DUMP_DEVICE_INFO=m

# Bazel ko_deps:
#   //vendor/oplus/kernel/boot:oplus_bsp_boot_projectinfo  → already source-built
#   //vendor/oplus/kernel/boot:oplusboot                   → bundled INTO
#                                                            oplus_bsp_cmdline_parser.ko
#                                                            in our build (oplusboot.c
#                                                            is one of cmdline_parser's
#                                                            -objs). Add cmdline_parser's
#                                                            symvers to resolve serial_no
#                                                            and the other oplusboot exports.
#   //soc-repo:.../drivers/soc/qcom/debug_symbol           → in-tree built; CRCs
#                                                            come via kernel symvers
KBUILD_EXTRA_SYMBOLS := \
    $(abspath $(CURDIR)/../../../boot/oplus_projectinfo/qcom/Module.symvers) \
    $(abspath $(CURDIR)/../../../boot/cmdline_parser/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(KBUILD_OPTIONS) $(@)
