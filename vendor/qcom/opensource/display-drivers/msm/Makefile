# SPDX-License-Identifier: GPL-2.0

# $(KERNEL_SRC)/$(M)/../ doubles paths under our build (KERNEL_SRC is
# absolute, M is also absolute after the kernel's KBUILD_EXTMOD realpath
# patch). $(CURDIR) is the absolute cwd at wrapper time — vendor/lineage's
# kernel.mk -C's into this module dir before invoking make — so
# $(CURDIR)/../ reliably resolves to display-drivers/.
KBUILD_OPTIONS+= DISPLAY_ROOT=$(CURDIR)/../

# Cross-module Module.symvers that vendor's Kleaf wires via bzl deps —
# msm_drm.ko links against synx, mm-drivers (sync_fence + msm_ext_display),
# securemsm-kernel (hdcp1_*).
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../synx-kernel/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../mm-drivers/sync_fence/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../mm-drivers/msm_ext_display/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../mm-drivers/hw_fence/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../securemsm-kernel/Module.symvers)

# Phase D: oplus display extension calls into Phase B oplus modules:
#   get_project / get_PCB_Version / get_eng_version / get_Operator_Version
#     ← oplus_bsp_boot_projectinfo.ko
#   get_boot_mode / op_is_monitorable_boot
#     ← oplus_bsp_bootmode.ko
#   verified_bootstate / serial_no / cmdline parser helpers
#     ← oplus_bsp_cmdline_parser.ko
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../../../oplus/kernel/boot/oplus_projectinfo/qcom/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../../../oplus/kernel/boot/bootmode/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../../../oplus/kernel/boot/cmdline_parser/Module.symvers)

# Phase D: msm_drm.ko consumes mmrm-driver's mmrm_client_register / etc.
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../mmrm-driver/Module.symvers)
# hfi_core_*: consumed by msm_drm.ko (HFI = Hardware Firmware Interface).
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../mm-drivers/hfi_core/Module.symvers)
# register_device_proc: oplus device_info module.
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../../../oplus/kernel/device_info/device_info/Module.symvers)
# touchpanel_event_register_notifier: oplus touchpanel notifier.
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../../../oplus/kernel/touchpanel/touchpanel_notify/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

all: modules

modules_install:
	$(MAKE) INSTALL_MOD_STRIP=1 -C $(KERNEL_SRC) M=$(M) modules_install

%:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $@ $(KBUILD_OPTIONS)

clean:
	rm -f *.o *.ko *.mod.c *.mod.o *~ .*.cmd Module.symvers
	rm -rf .tmp_versions

