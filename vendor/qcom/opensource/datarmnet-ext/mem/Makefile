#By default build for CLD
RMNET_MEM_SELECT := CONFIG_RMNET_MEM=m
KBUILD_OPTIONS += $(RMNET_MEM_SELECT)
KBUILD_OPTIONS += $(KBUILD_EXTRA) # Extra config if any

M ?= $(shell pwd)

all:
		$(MAKE) -C $(KERNEL_SRC) M=$(M) modules $(KBUILD_OPTIONS)

# vendor/lineage's kernel.mk passes 'modules' explicitly to avoid the
# wrapper-%:-fires-on-all double invocation that breaks under M=. This
# wrapper has no %: catch-all, so route 'modules' to 'all'.
modules: all

modules_install:
		$(MAKE) INSTALL_MOD_STRIP=1 -C $(KERNEL_SRC) M=$(M) modules_install

clean:
		$(MAKE) -C $(KERNEL_SRC) M=$(M) clean

