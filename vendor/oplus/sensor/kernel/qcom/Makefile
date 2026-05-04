# SPDX-License-Identifier: GPL-2.0-only
# Bazel ko_deps:
#   oplus_sensor_kookong_ir_spi: oplus_sensor_ir_core (auto-merged) +
#                                soc-repo:smem (kernel-internal)
#   oplus_sensor_deviceinfo:     oplus_bsp_boot_projectinfo + smem
#   oplus_sensor_feedback:       smem + oplus_bsp_dft_kernel_fb
#   oplus_sensor_interact:       oplus_sensor_feedback (auto-merged) +
#                                panel_event_notifier (kernel-internal)
KBUILD_EXTRA_SYMBOLS := \
    $(abspath $(CURDIR)/../../../../oplus/kernel/boot/oplus_projectinfo/qcom/Module.symvers) \
    $(abspath $(CURDIR)/../../../../oplus/kernel/dft/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(@)
