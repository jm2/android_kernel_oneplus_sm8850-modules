// SPDX-License-Identifier: GPL-2.0-only
/*
 * Lineage downstream stubs for vendor symbols that aren't shipped with
 * the LineageOS source-built tree:
 *
 * - get_eng_version: lives in oplus_projectinfo (no Kbuild, not in
 *   TARGET_KERNEL_EXT_MODULES). Returns OEM_RELEASE so factory/aging
 *   gates fall through to production behavior.
 *
 * - oplus_ofp_*: on-screen-fingerprint extension, source not in tree.
 *   Returns 0/false so the OFP feature is reported unsupported and
 *   downstream call paths short-circuit.
 *
 * - oplus_display_ops: zero-initialized struct so all the
 *   `if (oplus_display_ops.foo) { foo(...) }` guarded calls fall
 *   through to no-ops.
 *
 * - oplus_display_trace_enable: a tristate toggle — 0 = disabled.
 *
 * Replace any of these with real producers as the corresponding vendor
 * modules get wired up.
 */

#include <linux/module.h>
#include <linux/export.h>
#include <linux/types.h>
#include <oplus_display_interface.h>

unsigned int get_eng_version(void)
{
	return 0; /* OEM_RELEASE per oplus_project_data_ocdt.h */
}
EXPORT_SYMBOL(get_eng_version);

bool oplus_ofp_is_supported(void)
{
	return false;
}
EXPORT_SYMBOL(oplus_ofp_is_supported);

bool oplus_ofp_need_pcc_change(void *unused)
{
	return false;
}
EXPORT_SYMBOL(oplus_ofp_need_pcc_change);

int oplus_ofp_lhbm_backlight_update(void *unused)
{
	return 0;
}
EXPORT_SYMBOL(oplus_ofp_lhbm_backlight_update);

int oplus_ofp_hbm_handle(void *unused)
{
	return 0;
}
EXPORT_SYMBOL(oplus_ofp_hbm_handle);

int oplus_ofp_lhbm_handle_kick(void *unused)
{
	return 0;
}
EXPORT_SYMBOL(oplus_ofp_lhbm_handle_kick);

unsigned int oplus_display_trace_enable;
EXPORT_SYMBOL(oplus_display_trace_enable);

struct oplus_display_ops oplus_display_ops;
EXPORT_SYMBOL(oplus_display_ops);
