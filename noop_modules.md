# noop_modules.md — modules in modules.load that don't do meaningful work on canoe

Tracks source-built modules that ship for build-graph completeness but
either don't register a platform_driver, register one whose compatible
doesn't bind on canoe, or short-circuit at runtime. See
DEFERRED_FOLLOWUPS.md "noop_modules.md tracking across Wave 2" for
context on the two sub-classes.

Format: one entry per module, classified.

## obvious-stub class

Detectable from a static read of the .c file. init/exit return 0,
no platform_driver, no sysfs/proc/file_operations registration.

| Module | Source | Sub-wave | OEM .ko same? |
|---|---|---|---|
| `oplus_network_rf_cable_monitor` | `vendor/oplus/kernel/network/oplus_rf_cable_monitor/oplus_rf_cable_monitor.c` | 2H | yes (OEM also no-op) |

## runtime-effective-no-op class

Real platform_driver registration, real probe — but the driver's
`compatible` string doesn't match any DT node on canoe (24831/24863),
or the matching DT node has `status = "disabled"`. Module loads,
probe registers, never fires.

The active touch driver on canoe is **Synaptics S3910 via HBP** —
DT node `synaptics_hbp` with compat `oplus,tp_hbp_syna_s3910`. The
non-HBP `synaptics_tcm@0` node has `status = "disabled"`. All other
per-chip leaves are loaded for modules.load completeness, register
their platform_driver, and never bind on canoe.

| Module | Source compat | DT match on canoe? | Sub-wave |
|---|---|---|---|
| `oplus_bsp_tp_ft3683g` | `oplus,tp_noflash` | no canoe DT node | 2D |
| `oplus_bsp_tp_ft3681` | `oplus,tp_noflash` | no canoe DT node | 2D |
| `oplus_bsp_tp_ft3658u_spi` | (no in-source compat) | n/a | 2D |
| `oplus_bsp_tp_ft3518` | (no in-source compat) | n/a | 2D |
| `oplus_bsp_tp_ft8057p` | `oplus,tp_noflash` | no canoe DT node | 2D |
| `oplus_bsp_tp_gt9916` | `goodix-gt9916` | no canoe DT node | 2D |
| `oplus_bsp_tp_gt9966` | `goodix-gt9966` | no canoe DT node | 2D |
| `oplus_bsp_tp_ilitek7807s` | `oplus,tp_noflash` | no canoe DT node | 2D |
| `oplus_bsp_tp_nt36528_noflash` | `oplus,tp_noflash` | no canoe DT node | 2D |
| `oplus_bsp_tp_nt36532_noflash` | `oplus,tp_noflash` | no canoe DT node | 2D |
| `oplus_bsp_tp_nt36536_noflash` | `oplus,tp_noflash` | no canoe DT node | 2D |
| `oplus_bsp_tp_nt36672c_noflash` | (no in-source compat) | n/a | 2D |
| `oplus_bsp_tp_tcm_S3910` | `synaptics-s3910` | matches but `status = "disabled"` | 2D |
| `oplus_bsp_tp_tcm_S3908` | `synaptics-s3908_spi` | no canoe DT node | 2D |
| `oplus_bsp_tp_td4377_noflash` | (no in-source compat) | n/a | 2D |

15 entries from sub-wave 2D. The Focal/Novatek/Ilitek leaves register
for `oplus,tp_noflash` but canoe's DT has no such node (canoe is
Synaptics S3910 HBP only).

The "tcm_S3910 matches but disabled" case is the most interesting
of these — driver finds matching DT node, but kernel sees
`status = "disabled"` and skips probe(). That's a legitimate OEM
decision, not a bug.

## Active drivers on canoe (NOT in this file)

Recorded for context — these DO probe and ARE functional:

- `oplus_bsp_tp_hbp_syna_s3910` (HBP touch driver)
- `oplus_bsp_synaptics_tcm2` (separate synaptics_hbp tree — also
  matches `synaptics-s3910`; per-device which one binds depends
  on whether HBP or non-HBP node is enabled — TODO investigate)
- `oplus_bsp_uff_fp_driver` (fingerprint)
- `oplus_bsp_haptic` + `oplus_bsp_haptic_feedback`
- `oplus_bsp_fw_update`
- `oplus_hbp_core` (foundation, consumed by `oplus_bsp_tp_hbp_syna_s3910`
  and `oplus_ft3683g`)
- `oplus_bsp_dft_kernel_fb` (haptic_feedback dep — NOT in modules.load
  but present for build graph; OEM ships .ko but doesn't load)

## Counts

| Sub-wave | obvious-stub | runtime-effective-no-op | total |
|---|---|---|---|
| 2H | 1 | 0 | 1 |
| 2D | 0 | 15 | 15 |
| **Wave 2 total to date** | **1** | **15** | **16** |

If Wave 2 closes with 15+ runtime-effective-no-op entries, file a
downstream-optimization task in DEFERRED_FOLLOWUPS for `vendor_dlkm`
slimming: removing per-chip leaves whose compatibles don't match
canoe DT would save ~3 MB of vendor_dlkm space. (Per-leaf .ko sizes
range 200–600 KB.)
