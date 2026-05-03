# SPDX-License-Identifier: GPL-2.0-only
# Bazel ko_deps:
#   //vendor/oplus/kernel/network:oplus_network_oem_qmi  → consumed for
#                                                          oem_qmi_common_req
KBUILD_EXTRA_SYMBOLS := \
    $(abspath $(CURDIR)/../oplus_network_oem_qmi/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(@)
