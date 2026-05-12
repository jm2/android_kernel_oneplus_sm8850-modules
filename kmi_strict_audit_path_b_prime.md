# KMI-strict audit — 2026-05-11

Per Phase 2.5 of IMPLEMENTATION_PLAN.md. Measures, per OEM-prebuilt `.ko`, whether it loads against our post-Phase-1 KMI-canonicalized kernel, and aggregates into a Phase-6 boot prediction.

Audit inputs:
- Kernel Module.symvers: `out/target/product/infiniti/obj/KERNEL_OBJ/Module.symvers`
- AOSP whitelist (qcom + oplus + base): **4696** symbols
- Local extension whitelist (oneplus_15 + _extras): **10545** symbols
- OEM modules audited: **652** (of which **389** are in modules.load)

## module_layout CRC — single-symbol veto

Per IMPLEMENTATION_PLAN §1.2, `module_layout` CRC mismatch makes NO module load regardless of any other consideration.

- match:    **95**
- mismatch: **557**
- missing:  **0** (kernel doesn't export `module_layout` at all — would be a Phase-1 regression)
- absent:   **0** (no `__versions` section)

**VETO ACTIVE.** Phase 6 boot prediction is moot until this is resolved. Investigate before any further analysis.

## Distribution

Verdict counts across the OEM corpus.

| Verdict | Full corpus | In `modules.load` (boot-loaded) |
|---|---:|---:|
| `load-clean` | 95 | 77 |
| `load-fail-missing` | 0 | 0 |
| `load-fail-crc` | 0 | 0 |
| `load-fail-module-layout` | 557 | 312 |
| `no-versions` | 0 | 0 |
| `excluded-source-built-override` | 0 | 0 |
| **TOTAL** | **652** | **389** |

**Phase 6 boot prediction (today):** 77/389 modules in modules.load resolve cleanly (19.8%).

## Secondary verdict — assuming `module_layout` canonicalized

If we canonicalize `module_layout` (by source-building all modules against our kernel, OR by aligning kernel headers with OEM's), what fails next? This is the planning view for post-veto cleanup.

| Verdict | Boot-loaded count |
|---|---:|
| `load-clean` | 77 |
| `load-fail-missing` | 0 |
| `load-fail-crc` | 312 |
| `no-versions` | 0 |
| `excluded-source-built-override` | 0 |

**Phase 6 boot prediction (after `module_layout` fix):** 77/389 = 19.8%. The delta between 19.8% (today) and 19.8% (post-fix) is the leverage of the single-symbol fix.

## Per-subsystem breakdown (boot-loaded only)

Primary verdicts (today, with `module_layout` veto active):

| Subsystem | Total | clean | fail-missing | fail-crc | fail-module-layout | no-versions | src-built |
|---|---:|---:|---:|---:|---:|---:|---:|
| audio | 29 | 0 | 0 | 0 | 29 | 0 | 0 |
| bt | 8 | 4 | 0 | 0 | 4 | 0 | 0 |
| camera | 2 | 0 | 0 | 0 | 2 | 0 | 0 |
| charger | 3 | 0 | 0 | 0 | 3 | 0 | 0 |
| dfr | 4 | 0 | 0 | 0 | 4 | 0 | 0 |
| display | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| fingerprint | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| firmware-virt | 6 | 0 | 0 | 0 | 6 | 0 | 0 |
| gpu | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| graphics-video | 2 | 0 | 0 | 0 | 2 | 0 | 0 |
| haptic | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| misc | 221 | 73 | 0 | 0 | 148 | 0 | 0 |
| mm | 2 | 0 | 0 | 0 | 2 | 0 | 0 |
| mm-driver | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| network | 17 | 0 | 0 | 0 | 17 | 0 | 0 |
| regulator-pmic | 12 | 0 | 0 | 0 | 12 | 0 | 0 |
| rproc-glink | 9 | 0 | 0 | 0 | 9 | 0 | 0 |
| secure | 9 | 0 | 0 | 0 | 9 | 0 | 0 |
| thermal | 2 | 0 | 0 | 0 | 2 | 0 | 0 |
| touch | 25 | 0 | 0 | 0 | 25 | 0 | 0 |
| usb | 21 | 0 | 0 | 0 | 21 | 0 | 0 |
| wlan | 8 | 0 | 0 | 0 | 8 | 0 | 0 |

Secondary verdicts (after `module_layout` canonicalization):

| Subsystem | Total | clean | fail-missing | fail-crc | no-versions | src-built |
|---|---:|---:|---:|---:|---:|---:|
| audio | 29 | 0 | 0 | 29 | 0 | 0 |
| bt | 8 | 4 | 0 | 4 | 0 | 0 |
| camera | 2 | 0 | 0 | 2 | 0 | 0 |
| charger | 3 | 0 | 0 | 3 | 0 | 0 |
| dfr | 4 | 0 | 0 | 4 | 0 | 0 |
| display | 1 | 0 | 0 | 1 | 0 | 0 |
| fingerprint | 1 | 0 | 0 | 1 | 0 | 0 |
| firmware-virt | 6 | 0 | 0 | 6 | 0 | 0 |
| gpu | 1 | 0 | 0 | 1 | 0 | 0 |
| graphics-video | 2 | 0 | 0 | 2 | 0 | 0 |
| haptic | 1 | 0 | 0 | 1 | 0 | 0 |
| misc | 221 | 73 | 0 | 148 | 0 | 0 |
| mm | 2 | 0 | 0 | 2 | 0 | 0 |
| mm-driver | 5 | 0 | 0 | 5 | 0 | 0 |
| network | 17 | 0 | 0 | 17 | 0 | 0 |
| regulator-pmic | 12 | 0 | 0 | 12 | 0 | 0 |
| rproc-glink | 9 | 0 | 0 | 9 | 0 | 0 |
| secure | 9 | 0 | 0 | 9 | 0 | 0 |
| thermal | 2 | 0 | 0 | 2 | 0 | 0 |
| touch | 25 | 0 | 0 | 25 | 0 | 0 |
| usb | 21 | 0 | 0 | 21 | 0 | 0 |
| wlan | 8 | 0 | 0 | 8 | 0 | 0 |

## High-leverage canonicalization extensions

Missing vendor-internal symbols ranked by how many boot-loaded OEM modules reference them. Adding the top N to our union whitelist + EXPORT_SYMBOL'ing the producer (where available in our kernel source) unlocks all listed modules.

### Top 30 missing symbols (boot-loaded modules only)

| Symbol | Boot modules referencing |
|---|---:|
| `ipc_log_string` | 39 |
| `ipc_log_context_create` | 37 |
| `ipc_log_context_destroy` | 31 |
| `tp_debug` | 18 |
| `tp_test_write` | 16 |
| `tp_judge_ic_match` | 15 |
| `common_touch_data_alloc` | 15 |
| `register_common_touch_device` | 15 |
| `common_touch_data_free` | 15 |
| `tp_healthinfo_report` | 15 |
| `tp_pm_suspend` | 15 |
| `tp_pm_resume` | 15 |
| `upload_mm_fb_kevent_limit` | 14 |
| `kasan_flag_enabled` | 13 |
| `swr_get_logical_dev_num` | 12 |
| `reset_healthinfo_time_counter` | 12 |
| `tp_touch_btnkey_release` | 12 |
| `msm_cdc_pinctrl_select_active_state` | 11 |
| `msm_cdc_pinctrl_select_sleep_state` | 11 |
| `msm_cdc_pinctrl_get_state` | 10 |
| `unregister_common_touch_device` | 10 |
| `swr_connect_port` | 9 |
| `swr_slvdev_datapath_control` | 9 |
| `swr_disconnect_port` | 9 |
| `swr_driver_register` | 9 |
| `swr_driver_unregister` | 9 |
| `get_boot_mode` | 8 |
| `tp_shutdown` | 8 |
| `tp_powercontrol_avdd` | 8 |
| `tp_powercontrol_vddi` | 8 |

### CRC-mismatched symbols (boot-loaded)

Symbols our kernel exports but at a different CRC. Indicates struct-layout / header divergence between OEM's build and ours. Cannot be fixed by whitelist extension; needs source-side alignment (header convergence) OR source-build of the consuming module against our kernel.

**`module_layout`: 312 boot modules** (the veto symbol — single source of the catastrophic failure; see veto section above). Listed separately so subsequent rows show the second-most-leveraged CRC gaps.

### Top 20 non-`module_layout` CRC mismatches

| Symbol | Boot modules referencing |
|---|---:|
| `__stack_chk_fail` | 277 |
| `_printk` | 264 |
| `mem_alloc_profiling_key` | 200 |
| `kfree` | 196 |
| `mutex_lock` | 185 |
| `mutex_unlock` | 185 |
| `kmalloc_caches` | 170 |
| `__kmalloc_cache_noprof` | 170 |
| `devm_kmalloc` | 167 |
| `__platform_driver_register` | 163 |
| `_dev_err` | 158 |
| `platform_driver_unregister` | 153 |
| `__mutex_init` | 152 |
| `__fortify_panic` | 147 |
| `of_property_read_variable_u32_array` | 145 |
| `memset` | 143 |
| `memcpy` | 139 |
| `of_find_property` | 117 |
| `__list_add_valid_or_report` | 116 |
| `__kmalloc_noprof` | 115 |

## Bucket C scope recommendation

Subsystems ranked by load-fail count in boot-loaded set (higher = more Bucket-C-source-build pressure):

| Subsystem | Load-fail count |
|---|---:|
| misc | 148 |
| audio | 29 |
| touch | 25 |
| usb | 21 |
| network | 17 |
| regulator-pmic | 12 |
| secure | 9 |
| rproc-glink | 9 |
| wlan | 8 |
| firmware-virt | 6 |
| mm-driver | 5 |
| bt | 4 |
| dfr | 4 |
| charger | 3 |
| camera | 2 |
| graphics-video | 2 |
| mm | 2 |
| thermal | 2 |
| display | 1 |
| gpu | 1 |
| fingerprint | 1 |
| haptic | 1 |

Interpretation guidance:

- If a subsystem is 100% load-clean → already Phase-6-ready.
- If load-fail is concentrated on a few high-leverage symbols → extending canonicalization (whitelist + maybe a one-line EXPORT) is cheaper than source-build.
- If load-fail-crc dominates → header/struct divergence; source-build is the only path (canonicalization can't fix CRC).
- If load-fail-missing dominates with diffuse symbols → vendor-heavy subsystem; full source-build required.


---

## Delta vs baseline

Baseline rows: **652**, new rows: **652**, in common: **652** (new-only: 0, baseline-only: 0).

### Aggregate flip counts

| Transition | Modules |
|---|---:|
| flipped: load-fail → load-clean (UNLOCK) | **0** |
| flipped: load-clean → load-fail (REGRESSION) | 0 |
| changed verdict within load-fail-* | 0 |
| unchanged load-clean | 95 |
| unchanged load-fail-* | 557 |

### Per-subsystem delta (boot-relevant transitions)

Captures the partial-convergence-with-subsystem-stratification case: which subsystems converged and which didn't. The post-change Bucket C scope is the union of `unchanged_fail` columns (subsystems still requiring source-build) plus any new `to_fail` regressions.

| Subsystem | to_clean | to_fail | within_fail | unchanged_clean | unchanged_fail |
|---|---:|---:|---:|---:|---:|
| audio | 0 | 0 | 0 | 0 | 29 |
| boot-deviceinfo | 0 | 0 | 0 | 0 | 1 |
| bt | 0 | 0 | 0 | 4 | 4 |
| camera | 0 | 0 | 0 | 0 | 2 |
| charger | 0 | 0 | 0 | 0 | 3 |
| dfr | 0 | 0 | 0 | 0 | 21 |
| dft | 0 | 0 | 0 | 0 | 2 |
| display | 0 | 0 | 0 | 0 | 1 |
| fingerprint | 0 | 0 | 0 | 0 | 1 |
| firmware-virt | 0 | 0 | 0 | 0 | 16 |
| gpu | 0 | 0 | 0 | 0 | 2 |
| graphics-video | 0 | 0 | 0 | 0 | 2 |
| haptic | 0 | 0 | 0 | 0 | 1 |
| misc | 0 | 0 | 0 | 91 | 320 |
| mm | 0 | 0 | 0 | 0 | 3 |
| mm-driver | 0 | 0 | 0 | 0 | 6 |
| network | 0 | 0 | 0 | 0 | 39 |
| regulator-pmic | 0 | 0 | 0 | 0 | 22 |
| rproc-glink | 0 | 0 | 0 | 0 | 9 |
| sched-pm | 0 | 0 | 0 | 0 | 2 |
| secure | 0 | 0 | 0 | 0 | 10 |
| thermal | 0 | 0 | 0 | 0 | 3 |
| touch | 0 | 0 | 0 | 0 | 27 |
| usb | 0 | 0 | 0 | 0 | 21 |
| wlan | 0 | 0 | 0 | 0 | 10 |

