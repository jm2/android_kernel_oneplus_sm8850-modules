#By default build for CLD
RMNET_APS_SELECT := CONFIG_RMNET_APS=m
KBUILD_OPTIONS += $(RMNET_APS_SELECT)
KBUILD_OPTIONS += $(KBUILD_EXTRA) # Extra config if any
# Vendor's Kleaf populates DATARMNET_CORE_PATH / RMNET_CORE_INC_DIR;
# hardcode the relative-from-this-Makefile path for the make-driven
# build. $(CURDIR) is the absolute cwd when this wrapper runs (mka
# kernel cd's into the module dir before invoking make), so resolving
# via $(abspath $(CURDIR)/...) gives Module.symvers an absolute path
# that survives kbuild's O= cwd-switch dance.
DATARMNET_CORE_PATH ?= datarmnet/core
RMNET_CORE_INC_DIR ?= $(abspath $(CURDIR)/../../datarmnet/core)
KBUILD_OPTIONS += RMNET_CORE_INC_DIR=$(RMNET_CORE_INC_DIR)
KBUILD_EXTRA_SYMBOLS := $(abspath $(CURDIR)/../../$(DATARMNET_CORE_PATH)/Module.symvers)
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
