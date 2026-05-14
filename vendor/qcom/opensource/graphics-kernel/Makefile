ifeq ($(KGSL_MODULE_ROOT),)
CUR_MKFILE = $(abspath $(lastword $(MAKEFILE_LIST)))
KGSL_MODULE_ROOT = $(dir $(CUR_MKFILE))
endif

KBUILD_OPTIONS+=KGSL_PATH=$(KGSL_MODULE_ROOT)

# Lineage canoe: explicit KBUILD_EXTRA_SYMBOLS for cross-leaf deps.
# OEM msm_kgsl.ko consumes:
#   - synx-kernel symbols (in-tree source-built peer)
#   - qcom-dcvs symbols (OEM-prebuilt-only — Step 7.8d bridge via
#     synth_symvers'd ../qcom-dcvs.symvers; producer source isn't in
#     our ext-module corpus, will be source-built in a future wave)
#   - msm_performance symbols (same OEM-prebuilt-only situation; synth
#     bridge at ../msm_performance.symvers)
# Setting KBUILD_OPTIONS replaces kernel.mk auto-append; use $(CURDIR)
# per the 2I/2G-a lesson.
KBUILD_EXTRA_SYMBOLS := $(abspath $(CURDIR)/../synx-kernel/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../qcom-dcvs.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../msm_performance.symvers)
export KBUILD_EXTRA_SYMBOLS

all: modules

modules_install:
	$(MAKE) INSTALL_MOD_STRIP=1 -C $(KERNEL_SRC) M=$(M) modules_install

clean:
	rm -f *.cmd *.d *.mod *.o *.ko *.mod.c *.mod.o Module.symvers modules.order

%:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $@ $(KBUILD_OPTIONS)
