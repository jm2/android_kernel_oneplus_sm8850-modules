# SPDX-License-Identifier: GPL-2.0-only
# Bazel ko_deps: oplus_magnetic_cover deps oplus_magcvr_notify (sibling
# magtransfer/ tree). The hw leaves auto-merge with oplus_magnetic_cover
# in this M= dir.
KBUILD_EXTRA_SYMBOLS := \
    $(abspath $(CURDIR)/../magtransfer/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(@)
