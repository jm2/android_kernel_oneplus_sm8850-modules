# SPDX-License-Identifier: GPL-2.0-only

# Lineage canoe (kernel.mk-driven build): OEM's Kleaf injects
# CONFIG_MSM_VIDC_ANDROID=m via KBUILD_OPTIONS so the top-level Kbuild
# uses the msm_video/ subdir (which has the canoe-specific iris4 obj
# additions and canoe_video.conf include). Our build doesn't have that
# injection point, so default it here.
CONFIG_MSM_VIDC_ANDROID ?= m

$(info CONFIG_MSM_VIDC_ANDROID=$(CONFIG_MSM_VIDC_ANDROID))

ifneq ($(CONFIG_MSM_VIDC_ANDROID), m)
M := $(shell pwd)
KBUILD_OPTIONS += VIDEO_ROOT=$(M)
VIDEO_ROOT := $(shell pwd)
else
# kernel.mk-driven build: M is passed by the caller (relative to the
# kernel tree). Resolve VIDEO_ROOT to absolute and propagate
# CONFIG_MSM_VIDC_ANDROID to the recursive make so the top-level Kbuild
# sees the `m` branch.
KBUILD_OPTIONS += VIDEO_ROOT=$(abspath $(KERNEL_SRC)/$(M))
KBUILD_OPTIONS += CONFIG_MSM_VIDC_ANDROID=m
VIDEO_ROOT := $(abspath $(KERNEL_SRC)/$(M))
endif

# Lineage canoe: cross-leaf symvers explicit (kernel.mk's auto-append
# is replaced when we set KBUILD_OPTIONS above). All three deps are
# in-tree source-built peers earlier in TARGET_KERNEL_EXT_MODULES.
# Use $(CURDIR) per the 2I/2G-a lesson; $(M) doubles paths.
KBUILD_EXTRA_SYMBOLS := $(abspath $(CURDIR)/../synx-kernel/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../mmrm-driver/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../mm-drivers/hw_fence/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

VIDEO_COMPILE_TIME = $(shell date)
VIDEO_COMPILE_BY = $(shell echo $(USER))
VIDEO_COMPILE_HOST = $(shell uname -n)
VIDEO_GEN_PATH = $(VIDEO_ROOT)/driver/vidc/inc/video_generated_h

all: modules

$(VIDEO_GEN_PATH): $(shell find . -type f \( -iname \*.c -o -iname \*.h -o -iname \*.mk \))
	echo '#define VIDEO_COMPILE_TIME "$(VIDEO_COMPILE_TIME)"' > $(VIDEO_GEN_PATH)
	echo '#define VIDEO_COMPILE_BY "$(VIDEO_COMPILE_BY)"' >> $(VIDEO_GEN_PATH)
	echo '#define VIDEO_COMPILE_HOST "$(VIDEO_COMPILE_HOST)"' >> $(VIDEO_GEN_PATH)

modules: $(VIDEO_GEN_PATH)
ifeq ($(CONFIG_MSM_VIDC_ANDROID), m)
	ln -sf $(VIDEO_ROOT)/driver $(VIDEO_ROOT)/msm_video/driver
else
	ln -sf $(VIDEO_ROOT)/driver $(VIDEO_ROOT)/video/driver
endif
	$(MAKE) -C $(KERNEL_SRC) M=$(M) modules $(KBUILD_OPTIONS)
ifeq ($(CONFIG_MSM_VIDC_ANDROID), m)
	rm $(VIDEO_ROOT)/msm_video/driver
else
	rm $(VIDEO_ROOT)/video/driver
endif

modules_install:
	$(MAKE) INSTALL_MOD_STRIP=1 -C $(KERNEL_SRC) M=$(M) modules_install

%:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $@ $(KBUILD_OPTIONS)

clean:
	rm -f *.o *.ko *.mod.c *.mod.o *~ .*.cmd Module.symvers
	rm -rf .tmp_versions
