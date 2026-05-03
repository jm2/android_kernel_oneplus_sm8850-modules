# SPDX-License-Identifier: GPL-2.0-only
# Bazel ko_deps:
#   //vendor/oplus/kernel/touchpanel/touchpanel_notify:oplus_bsp_tp_notify
#   //soc-repo:.../drivers/soc/qcom/panel_event_notifier (kernel-internal — auto-resolved)
KBUILD_EXTRA_SYMBOLS := \
    $(abspath $(CURDIR)/../../../../../../../oplus/kernel/touchpanel/touchpanel_notify/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(@)
