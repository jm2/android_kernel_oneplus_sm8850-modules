# SPDX-License-Identifier: GPL-2.0-only
# External Bazel ko_deps for the touch cluster (auto-merged internal
# symvers stay implicit because all 22 modules share this M= dir):
#   oplusboot           (bundled into oplus_bsp_cmdline_parser)
#   oplus_bsp_bootmode
#   oplus_bsp_boot_projectinfo
#   panel_event_notifier (kernel-internal — auto-resolved by KERNEL_SRC)
#   device_info
#   oplus_bsp_tp_notify
#   oplus_bsp_fw_update
KBUILD_EXTRA_SYMBOLS := \
    $(abspath $(CURDIR)/../../boot/cmdline_parser/Module.symvers) \
    $(abspath $(CURDIR)/../../boot/bootmode/Module.symvers) \
    $(abspath $(CURDIR)/../../boot/oplus_projectinfo/qcom/Module.symvers) \
    $(abspath $(CURDIR)/../../device_info/device_info/Module.symvers) \
    $(abspath $(CURDIR)/../touchpanel_notify/Module.symvers) \
    $(abspath $(CURDIR)/../kernelFwUpdate/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(@)
