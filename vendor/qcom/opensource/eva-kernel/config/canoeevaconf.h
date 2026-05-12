/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * canoe per-target eva-kernel C-side #defines.
 *
 * Mirrors canoeeva.conf's Make-side exports. Sourced via Kbuild's
 * `LINUXINCLUDE += -include canoeevaconf.h` under the CONFIG_ARCH_CANOE
 * gate so #ifdef checks across the eva sources see the same set the
 * Make rules saw at obj-$() time.
 */

#define CONFIG_MSM_EVA       1
#define CONFIG_EVA_CANOE     1
#define TARGET_SYNX_ENABLE   1
#define TARGET_DSP_ENABLE    1
#define TARGET_MMRM_ENABLE   1
#define CONFIG_MSM_MMRM      1
