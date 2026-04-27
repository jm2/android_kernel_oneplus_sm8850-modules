#By default build for CLD
RMNET_PERF_SELECT := CONFIG_RMNET_PERF=m
KBUILD_OPTIONS += $(RMNET_PERF_SELECT)
KBUILD_OPTIONS += $(KBUILD_EXTRA) # Extra config if any
DATARMNET_CORE_PATH ?= datarmnet/core
DATARMNET_SHS_PATH ?= datarmnet-ext/shs
RMNET_CORE_INC_DIR ?= $(abspath $(CURDIR)/../../datarmnet/core)
KBUILD_OPTIONS += RMNET_CORE_INC_DIR=$(RMNET_CORE_INC_DIR)
KBUILD_EXTRA_SYMBOLS := $(abspath $(CURDIR)/../../$(DATARMNET_CORE_PATH)/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../../$(DATARMNET_SHS_PATH)/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

M ?= $(shell pwd)

all:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) modules $(KBUILD_OPTIONS)

modules_install:
	$(MAKE) INSTALL_MOD_STRIP=1 -C $(KERNEL_SRC) M=$(M) modules_install

clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) clean

# vendor/lineage's kernel.mk passes 'modules' explicitly. This wrapper has
# no %: catch-all, so route 'modules' to 'all'.
modules: all
