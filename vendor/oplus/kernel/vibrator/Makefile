# SPDX-License-Identifier: GPL-2.0-only
# Bazel ko_deps:
#   haptic_feedback: oplus_bsp_dft_kernel_fb
#   haptic:          oplus_bsp_haptic_feedback (auto-merged in this M dir)
#                    + oplus_bsp_boot_projectinfo + oplus_bsp_bootmode (cmdline_parser bundled)
KBUILD_EXTRA_SYMBOLS := \
    $(abspath $(CURDIR)/../dft/Module.symvers) \
    $(abspath $(CURDIR)/../boot/cmdline_parser/Module.symvers) \
    $(abspath $(CURDIR)/../boot/bootmode/Module.symvers) \
    $(abspath $(CURDIR)/../boot/oplus_projectinfo/qcom/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(@)
