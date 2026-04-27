M=$(PWD)
AUDIO_ROOT=$(KERNEL_SRC)/$(M)

# audio-kernel's per-subdir Kbuild files use `MODNAME` as a sentinel: empty
# MODNAME → "we're inside a standalone kernel tree" (Kleaf injects the file
# tree into the kernel) and the Kbuild recurses into `obj-y += ./` plus
# every subdir; non-empty MODNAME → "we're building as an external module"
# and the Kbuild only emits the explicit obj-$(CONFIG_*) module entries.
# Under mka kernel we always use the external-module shape, so set MODNAME
# unconditionally — the value isn't used as a module name, only as a
# truthiness flag. Without this audio-kernel/asoc/codecs/Kbuild line 287
# (`obj-y += ./`) sends kbuild into infinite self-recursion.
KBUILD_OPTIONS+=  AUDIO_ROOT=$(AUDIO_ROOT)
KBUILD_OPTIONS+=  MODNAME=audio_kernel

all: modules

clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) clean

%:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $@ $(KBUILD_OPTIONS)

