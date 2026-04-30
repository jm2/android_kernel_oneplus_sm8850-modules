# SPDX-License-Identifier: GPL-2.0
vendor := $(src)

ifneq "$(wildcard $(vendor)/qcom)" ""
#OPLUS_DTS_OVERLAY start
	subdir-y += qcom
#OPLUS_DTS_OVERLAY end
endif
#OPLUS_DTS_OVERLAY start
subdir-y += oplus
#OPLUS_DTS_OVERLAY end

# jm2: pull in the 14 techpack devicetree subprojects (Stage B overlays).
# Each is a symlink to ../../../../vendor/qcom/opensource/<name>-devicetree.
# Their Kbuilds add CANOE/ALOR-gated dtbo-y entries that produce ~54+
# techpack overlay .dtbo files. merge_dtbs.py at Stage C consumes these
# along with the base DTBs from qcom/ and overlays from oplus/.
# This avoids the M= external-module mode, which fights kbuild's
# VPATH=empty-when-EXTMOD-set assumption and breaks scripts_basic.
subdir-y += $(foreach d,audio bt camera data display dsp eSE eva graphics mm mmrm nfc synx video,$(if $(wildcard $(vendor)/$(d)-devicetree/Kbuild),$(d)-devicetree))
