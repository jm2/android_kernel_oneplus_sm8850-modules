# SPDX-License-Identifier: GPL-2.0-only
# External-module shell for charger v2.
# The kbuild rules live in the sibling Kbuild file (renamed from the
# original Makefile). canoe-specific CONFIG flags come from
# bazel/defconfig/oplus_canoe_perf_config.bzl, mirrored here as
# KBUILD_OPTIONS for our build.
KBUILD_OPTIONS := \
    CONFIG_OPLUS_CHG_V2=m \
    CONFIG_OPLUS_CHARGER_DDK_BUILD=y \
    CONFIG_OPLUS_CHARGER=y \
    CONFIG_OPLUS_ADSP_CHARGER=y \
    CONFIG_OPLUS_CHIP_SOC_NODE=y \
    CONFIG_OPLUS_SHIP_MODE_SUPPORT=y \
    CONFIG_OPLUS_SMART_CHARGER_SUPPORT=y \
    CONFIG_OPLUS_CHG_DRM_PANEL_NOTIFY=y \
    CONFIG_OPLUS_CALL_MODE_SUPPORT=y \
    CONFIG_OPLUS_CHECK_CHARGERID_VOLT=y \
    CONFIG_OPLUS_CHG_DYNAMIC_CONFIG=y \
    CONFIG_OPLUS_CHG_TEST_KIT=m \
    CONFIG_OPLUS_RTC_DET_SUPPORT=y \
    CONFIG_OPLUS_CHG_IC_DEBUG=y \
    CONFIG_OPLUS_CHG_MMS_DEBUG=y \
    CONFIG_OPLUS_WIRELESS_NU1669=y \
    CONFIG_OPLUS_WIRELESS_SC96257=y \
    CONFIG_OPLUS_CHG_VOOCPHY=y \
    CONFIG_OPLUS_CHG_VOOCPHY_CHGLIB=y \
    CONFIG_OPLUS_CHG_AP_VOOCPHY=y \
    CONFIG_OPLUS_CHG_ADSP_VOOCPHY=y \
    CONFIG_OPLUS_SY6603_BATT_BAL=y \
    CONFIG_OPLUS_SC7637_LEVEL_SHIFT=y \
    CONFIG_OPLUS_VOOCPHY_SC8517=y \
    CONFIG_OPLUS_AUDIO_SWITCH_GLINK=y \
    CONFIG_OPLUS_DYNAMIC_CONFIG=m \
    CONFIG_OPLUS_DYNAMIC_CONFIG_CHARGER=y \
    CONFIG_OPLUS_HL7603_CHARGER=y \
    CONFIG_OPLUS_GAUGE_NFG8011B=y \
    CONFIG_OPLUS_STATE_RETENTION=y \
    CONFIG_OPLUS_MAGCVR_NOTIFY=y \
    CONFIG_OPLUS_FEATURE_OLC=y \
    CONFIG_OPLUS_FEATURE_FEEDBACK=m \
    CONFIG_OPLUS_PHY_SC8547D=y \
    CONFIG_OPLUS_UFCS_CLASS=m

# C-side mirror of KBUILD_OPTIONS so source-level #ifdef CONFIG_X
# blocks evaluate true. KBUILD_OPTIONS sets Make variables (for
# obj-$(CONFIG_X) gating) but does NOT translate to C preprocessor
# defines — that's the kernel build's auto.conf job, which we don't
# have for external-module CONFIG flags. Same Make-side / C-side
# asymmetry pattern as 2F.1 audio (canoeauto.conf vs canoeautoconf.h).
EXTRA_CFLAGS_DEFINES := \
    -DCONFIG_OPLUS_CHG_V2 \
    -DCONFIG_OPLUS_CHARGER_DDK_BUILD \
    -DCONFIG_OPLUS_CHARGER \
    -DCONFIG_OPLUS_ADSP_CHARGER \
    -DCONFIG_OPLUS_CHIP_SOC_NODE \
    -DCONFIG_OPLUS_SHIP_MODE_SUPPORT \
    -DCONFIG_OPLUS_SMART_CHARGER_SUPPORT \
    -DCONFIG_OPLUS_CHG_DRM_PANEL_NOTIFY \
    -DCONFIG_OPLUS_CALL_MODE_SUPPORT \
    -DCONFIG_OPLUS_CHECK_CHARGERID_VOLT \
    -DCONFIG_OPLUS_CHG_DYNAMIC_CONFIG \
    -DCONFIG_OPLUS_CHG_TEST_KIT \
    -DCONFIG_OPLUS_RTC_DET_SUPPORT \
    -DCONFIG_OPLUS_CHG_IC_DEBUG \
    -DCONFIG_OPLUS_CHG_MMS_DEBUG \
    -DCONFIG_OPLUS_WIRELESS_NU1669 \
    -DCONFIG_OPLUS_WIRELESS_SC96257 \
    -DCONFIG_OPLUS_CHG_VOOCPHY \
    -DCONFIG_OPLUS_CHG_VOOCPHY_CHGLIB \
    -DCONFIG_OPLUS_CHG_AP_VOOCPHY \
    -DCONFIG_OPLUS_CHG_ADSP_VOOCPHY \
    -DCONFIG_OPLUS_SY6603_BATT_BAL \
    -DCONFIG_OPLUS_SC7637_LEVEL_SHIFT \
    -DCONFIG_OPLUS_VOOCPHY_SC8517 \
    -DCONFIG_OPLUS_AUDIO_SWITCH_GLINK \
    -DCONFIG_OPLUS_DYNAMIC_CONFIG \
    -DCONFIG_OPLUS_DYNAMIC_CONFIG_CHARGER \
    -DCONFIG_OPLUS_HL7603_CHARGER \
    -DCONFIG_OPLUS_GAUGE_NFG8011B \
    -DCONFIG_OPLUS_STATE_RETENTION \
    -DCONFIG_OPLUS_MAGCVR_NOTIFY \
    -DCONFIG_OPLUS_FEATURE_OLC \
    -DCONFIG_OPLUS_FEATURE_FEEDBACK \
    -DCONFIG_OPLUS_PHY_SC8547D \
    -DCONFIG_OPLUS_UFCS_CLASS \
    -DOPLUS_FEATURE_CHG_BASIC \
    -DCONFIG_QTI_BATTERY_CHARGER
export EXTRA_CFLAGS_DEFINES

KERNEL_SRC ?= /lib/modules/$(shell uname -r)/build
M ?= $(shell pwd)

# OEM build flow generates 3 headers from JSON config files via
# scripts/ic_cfg_parse.py. Their stock Makefile.json-build assumes
# in-tree paths under drivers/power/oplus/v2 — wrong for our
# external-module build. Pre-generate the headers in $(M) before
# invoking kbuild; kbuild's -I$(src) finds them naturally.
GENERATED_HEADERS := \
    $(M)/oplus_chg_ic_cfg.h \
    $(M)/oplus_chg_ic_cfg_str.h \
    $(M)/oplus_chg_ic_auto_debug.h

generate-headers:
	@python3 $(CURDIR)/scripts/ic_cfg_parse.py -hd $(CURDIR)/include/oplus_chg_ic_cfg.h        $(CURDIR)/config/oplus_chg_ic.json
	@python3 $(CURDIR)/scripts/ic_cfg_parse.py -s  $(CURDIR)/include/oplus_chg_ic_cfg_str.h    $(CURDIR)/config/oplus_chg_ic.json
	@python3 $(CURDIR)/scripts/ic_cfg_parse.py -df $(CURDIR)/include/oplus_chg_ic_auto_debug.h $(CURDIR)/config/oplus_chg_ic.json

modules: generate-headers
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(KBUILD_OPTIONS) $(@)

modules_install clean:
	$(MAKE) -C $(KERNEL_SRC) M=$(M) $(KBUILD_OPTIONS) $(@)
