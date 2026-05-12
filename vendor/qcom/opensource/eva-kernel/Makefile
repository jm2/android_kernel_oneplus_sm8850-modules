KBUILD_OPTIONS+= EVA_ROOT=$(KERNEL_SRC)/$(M)

# Lineage 2G batch-2G-a: cross-leaf symvers explicit. Setting
# KBUILD_EXTRA_SYMBOLS replaces the kernel.mk auto-append, so we
# enumerate every sibling we link against:
#   - synx-kernel: synx_recover (in-tree source-built)
#   - mmrm-driver: mmrm_client_{register,deregister,check_scaling_supported}
#     (in-tree source-built)
#   - dsp-kernel: fastrpc_driver_{register,unregister,invoke} — bridge
#     primitive (synth_symvers'd from OEM frpc-adsprpc.ko since
#     dsp-kernel is deferred to Wave 5+; see Step 7.8d). depmod-layer
#     covered by BOARD_VENDOR_KERNEL_MODULES_DEPMOD_BRIDGE_DIR in
#     device tree.
# Use $(CURDIR) per the 2I lesson; $(M) doubles paths under our build.
KBUILD_EXTRA_SYMBOLS := $(abspath $(CURDIR)/../synx-kernel/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../mmrm-driver/Module.symvers)
KBUILD_EXTRA_SYMBOLS += $(abspath $(CURDIR)/../dsp-kernel/Module.symvers)
export KBUILD_EXTRA_SYMBOLS

all:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) modules $(KBUILD_OPTIONS)

modules_install:
	$(MAKE) M=$(M) -C $(KERNEL_SRC) modules_install

%:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $@ $(KBUILD_OPTIONS)

clean:
	rm -f *.o *.ko *.mod.c *.mod.o *~ .*.cmd Module.symvers
	rm -rf .tmp_versions
