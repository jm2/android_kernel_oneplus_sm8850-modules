# SPDX-License-Identifier: GPL-2.0-only
# Bazel ko_deps: soc-repo:qcom-scm (kernel-internal, auto-resolved).
KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)
modules modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(@)
