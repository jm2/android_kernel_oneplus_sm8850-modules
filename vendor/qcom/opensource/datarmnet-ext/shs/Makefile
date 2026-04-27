KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build

KBUILD_OPTIONS := RMNET_SHS_ROOT=$(PWD)
KBUILD_OPTIONS += MODNAME?=rmnet_shs
DATARMNET_CORE_PATH ?= datarmnet/core
RMNET_CORE_INC_DIR ?= $(abspath $(CURDIR)/../../datarmnet/core)
KBUILD_OPTIONS += RMNET_CORE_INC_DIR=$(RMNET_CORE_INC_DIR)
KBUILD_EXTRA_SYMBOLS := $(abspath $(CURDIR)/../../$(DATARMNET_CORE_PATH)/Module.symvers)
export KBUILD_EXTRA_SYMBOLS
M ?= $(shell pwd)

all:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) modules $(KBUILD_OPTIONS) $(KBUILD_EXTRA_SYMBOLS)

modules_install:
	$(MAKE) INSTALL_MOD_STRIP=1 -C $(KERNEL_SRC) M=$(M) modules_install

clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) clean

# vendor/lineage's kernel.mk passes 'modules' explicitly. This wrapper has
# no %: catch-all, so route 'modules' to 'all'.
modules: all
