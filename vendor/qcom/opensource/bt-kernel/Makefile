KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)

M=$(PWD)
BT_ROOT=$(KERNEL_SRC)/$(M)

KBUILD_OPTIONS+=  BT_ROOT=$(BT_ROOT)

# Cross-tree symvers wiring (Lineage canoe). Two producers our 4
# canoe modules consume from:
#   audio-kernel  — swr_dlkm.ko's swr_* symbols (source-built in 2C)
#   wlan/platform — cnss_utils.ko's cnss_utils_fmd_status
#                   (OEM-prebuilt; symvers synthesized via
#                    tools/jm2/synth_symvers.py — see WIRE_UP_RECIPE
#                    Step 7.8d, OEM-prebuilt-sibling-producer class)
KBUILD_EXTRA_SYMBOLS := $(abspath $(M)/../audio-kernel/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(M)/../wlan/platform/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

all:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) modules $(KBUILD_OPTIONS)

modules_install:
	$(MAKE) INSTALL_MOD_STRIP=1 -C $(KERNEL_SRC) M=$(M) modules_install

clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) clean

# vendor/lineage's kernel.mk passes 'modules' explicitly; route to 'all'.
modules: all
