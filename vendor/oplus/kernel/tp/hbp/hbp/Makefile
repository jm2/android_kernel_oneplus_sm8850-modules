# SPDX-License-Identifier: GPL-2.0-only
# Bazel ko_deps:
#   oplus_hbp_core: panel_event_notifier (kernel-internal), tp_notify, fw_update
#   oplus_bsp_tp_hbp_syna_s3910: oplus_hbp_core (auto-merged in this M dir)
KBUILD_EXTRA_SYMBOLS := \
    $(abspath $(CURDIR)/../../../touchpanel/touchpanel_notify/Module.symvers) \
    $(abspath $(CURDIR)/../../../touchpanel/kernelFwUpdate/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(@)
