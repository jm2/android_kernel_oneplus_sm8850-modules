# SPDX-License-Identifier: GPL-2.0-only
# Bazel ko_deps:
#   //vendor/oplus/kernel/touchpanel/oplus_touchscreen_v2:oplus_bsp_tp_custom
#   plus oplusboot, bootmode, projectinfo, panel_event_notifier (soc-repo),
#   device_info, oplus_bsp_tp_notify, oplus_bsp_fw_update
KBUILD_EXTRA_SYMBOLS := \
    $(abspath $(CURDIR)/../oplus_touchscreen_v2/Module.symvers) \
    $(abspath $(CURDIR)/../touchpanel_notify/Module.symvers) \
    $(abspath $(CURDIR)/../kernelFwUpdate/Module.symvers) \
    $(abspath $(CURDIR)/../../boot/cmdline_parser/Module.symvers) \
    $(abspath $(CURDIR)/../../boot/bootmode/Module.symvers) \
    $(abspath $(CURDIR)/../../boot/oplus_projectinfo/qcom/Module.symvers) \
    $(abspath $(CURDIR)/../../device_info/device_info/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(@)
