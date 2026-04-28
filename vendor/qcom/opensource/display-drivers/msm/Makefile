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
export KBUILD_EXTRA_SYMBOLS

all: modules

modules_install:
	$(MAKE) INSTALL_MOD_STRIP=1 -C $(KERNEL_SRC) M=$(M) modules_install

%:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $@ $(KBUILD_OPTIONS)

clean:
	rm -f *.o *.ko *.mod.c *.mod.o *~ .*.cmd Module.symvers
	rm -rf .tmp_versions

