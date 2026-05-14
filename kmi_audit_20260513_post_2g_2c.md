# KMI-strict audit — 2026-05-13

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
| `load-fail-module-layout` | 293 | 118 |
| `no-versions` | 0 | 0 |
| `excluded-source-built-override` | 264 | 194 |
| **TOTAL** | **652** | **389** |

**Phase 6 boot prediction (today):** 271/389 modules in modules.load resolve cleanly (69.7%).

## Secondary verdict — assuming `module_layout` canonicalized

If we canonicalize `module_layout` (by source-building all modules against our kernel, OR by aligning kernel headers with OEM's), what fails next? This is the planning view for post-veto cleanup.

| Verdict | Boot-loaded count |
|---|---:|
| `load-clean` | 77 |
| `load-fail-missing` | 0 |
| `load-fail-crc` | 118 |
| `no-versions` | 0 |
| `excluded-source-built-override` | 194 |

**Phase 6 boot prediction (after `module_layout` fix):** 271/389 = 69.7%. The delta between 69.7% (today) and 69.7% (post-fix) is the leverage of the single-symbol fix.

## Per-subsystem breakdown (boot-loaded only)

Primary verdicts (today, with `module_layout` veto active):

| Subsystem | Total | clean | fail-missing | fail-crc | fail-module-layout | no-versions | src-built |
|---|---:|---:|---:|---:|---:|---:|---:|
| audio | 29 | 0 | 0 | 0 | 6 | 0 | 23 |
| bt | 8 | 4 | 0 | 0 | 0 | 0 | 4 |
| camera | 2 | 0 | 0 | 0 | 1 | 0 | 1 |
| charger | 3 | 0 | 0 | 0 | 3 | 0 | 0 |
| dfr | 4 | 0 | 0 | 0 | 0 | 0 | 4 |
| display | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| fingerprint | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| firmware-virt | 6 | 0 | 0 | 0 | 1 | 0 | 5 |
| gpu | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| graphics-video | 2 | 0 | 0 | 0 | 0 | 0 | 2 |
| haptic | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| misc | 221 | 73 | 0 | 0 | 82 | 0 | 66 |
| mm | 2 | 0 | 0 | 0 | 0 | 0 | 2 |
| mm-driver | 5 | 0 | 0 | 0 | 0 | 0 | 5 |
| network | 17 | 0 | 0 | 0 | 2 | 0 | 15 |
| regulator-pmic | 12 | 0 | 0 | 0 | 6 | 0 | 6 |
| rproc-glink | 9 | 0 | 0 | 0 | 0 | 0 | 9 |
| secure | 9 | 0 | 0 | 0 | 1 | 0 | 8 |
| thermal | 2 | 0 | 0 | 0 | 1 | 0 | 1 |
| touch | 25 | 0 | 0 | 0 | 0 | 0 | 25 |
| usb | 21 | 0 | 0 | 0 | 7 | 0 | 14 |
| wlan | 8 | 0 | 0 | 0 | 8 | 0 | 0 |

Secondary verdicts (after `module_layout` canonicalization):

| Subsystem | Total | clean | fail-missing | fail-crc | no-versions | src-built |
|---|---:|---:|---:|---:|---:|---:|
| audio | 29 | 0 | 0 | 6 | 0 | 23 |
| bt | 8 | 4 | 0 | 0 | 0 | 4 |
| camera | 2 | 0 | 0 | 1 | 0 | 1 |
| charger | 3 | 0 | 0 | 3 | 0 | 0 |
| dfr | 4 | 0 | 0 | 0 | 0 | 4 |
| display | 1 | 0 | 0 | 0 | 0 | 1 |
| fingerprint | 1 | 0 | 0 | 0 | 0 | 1 |
| firmware-virt | 6 | 0 | 0 | 1 | 0 | 5 |
| gpu | 1 | 0 | 0 | 0 | 0 | 1 |
| graphics-video | 2 | 0 | 0 | 0 | 0 | 2 |
| haptic | 1 | 0 | 0 | 0 | 0 | 1 |
| misc | 221 | 73 | 0 | 82 | 0 | 66 |
| mm | 2 | 0 | 0 | 0 | 0 | 2 |
| mm-driver | 5 | 0 | 0 | 0 | 0 | 5 |
| network | 17 | 0 | 0 | 2 | 0 | 15 |
| regulator-pmic | 12 | 0 | 0 | 6 | 0 | 6 |
| rproc-glink | 9 | 0 | 0 | 0 | 0 | 9 |
| secure | 9 | 0 | 0 | 1 | 0 | 8 |
| thermal | 2 | 0 | 0 | 1 | 0 | 1 |
| touch | 25 | 0 | 0 | 0 | 0 | 25 |
| usb | 21 | 0 | 0 | 7 | 0 | 14 |
| wlan | 8 | 0 | 0 | 8 | 0 | 0 |

## High-leverage canonicalization extensions

Missing vendor-internal symbols ranked by how many boot-loaded OEM modules reference them. Adding the top N to our union whitelist + EXPORT_SYMBOL'ing the producer (where available in our kernel source) unlocks all listed modules.

### Top 30 missing symbols (boot-loaded modules only)

| Symbol | Boot modules referencing |
|---|---:|
| `ipc_log_string` | 24 |
| `ipc_log_context_create` | 23 |
| `ipc_log_context_destroy` | 20 |
| `get_qcom_scmi_device` | 6 |
| `get_boot_mode` | 3 |
| `msm_cdc_pinctrl_select_active_state` | 3 |
| `msm_cdc_pinctrl_select_sleep_state` | 3 |
| `swr_get_logical_dev_num` | 3 |
| `qcom_dcvs_register_voter` | 2 |
| `qcom_dcvs_hw_minmax_get` | 2 |
| `qcom_dcvs_kobject_get` | 2 |
| `qcom_dcvs_update_votes` | 2 |
| `get_eng_version` | 2 |
| `cnss_initialize_prealloc_pool` | 2 |
| `cnss_deinitialize_prealloc_pool` | 2 |
| `wlfw_cap_resp_msg_v01_ei` | 2 |
| `wlfw_cap_req_msg_v01_ei` | 2 |
| `get_Operator_Version` | 2 |
| `wlfw_bdf_download_resp_msg_v01_ei` | 2 |
| `wlfw_bdf_download_req_msg_v01_ei` | 2 |
| `wlfw_m3_info_resp_msg_v01_ei` | 2 |
| `wlfw_m3_info_req_msg_v01_ei` | 2 |
| `wlfw_aux_uc_info_resp_msg_v01_ei` | 2 |
| `wlfw_aux_uc_info_req_msg_v01_ei` | 2 |
| `wlfw_mac_addr_resp_msg_v01_ei` | 2 |
| `wlfw_mac_addr_req_msg_v01_ei` | 2 |
| `wlfw_qdss_trace_data_resp_msg_v01_ei` | 2 |
| `wlfw_qdss_trace_data_req_msg_v01_ei` | 2 |
| `wlfw_qdss_trace_config_download_resp_msg_v01_ei` | 2 |
| `wlfw_qdss_trace_config_download_req_msg_v01_ei` | 2 |

### CRC-mismatched symbols (boot-loaded)

Symbols our kernel exports but at a different CRC. Indicates struct-layout / header divergence between OEM's build and ours. Cannot be fixed by whitelist extension; needs source-side alignment (header convergence) OR source-build of the consuming module against our kernel.

**`module_layout`: 118 boot modules** (the veto symbol — single source of the catastrophic failure; see veto section above). Listed separately so subsequent rows show the second-most-leveraged CRC gaps.

### Top 20 non-`module_layout` CRC mismatches

| Symbol | Boot modules referencing |
|---|---:|
| `__stack_chk_fail` | 106 |
| `_printk` | 98 |
| `__platform_driver_register` | 77 |
| `platform_driver_unregister` | 74 |
| `devm_kmalloc` | 69 |
| `_dev_err` | 63 |
| `mem_alloc_profiling_key` | 63 |
| `mutex_lock` | 62 |
| `mutex_unlock` | 62 |
| `kfree` | 61 |
| `of_property_read_variable_u32_array` | 54 |
| `kmalloc_caches` | 53 |
| `__kmalloc_cache_noprof` | 53 |
| `scnprintf` | 53 |
| `__mutex_init` | 52 |
| `memcpy` | 47 |
| `memset` | 44 |
| `of_find_property` | 43 |
| `__list_add_valid_or_report` | 41 |
| `__fortify_panic` | 41 |

## Bucket C scope recommendation

Subsystems ranked by load-fail count in boot-loaded set (higher = more Bucket-C-source-build pressure):

| Subsystem | Load-fail count |
|---|---:|
| misc | 82 |
| wlan | 8 |
| usb | 7 |
| audio | 6 |
| regulator-pmic | 6 |
| charger | 3 |
| network | 2 |
| camera | 1 |
| firmware-virt | 1 |
| secure | 1 |
| thermal | 1 |

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
| unchanged load-fail-* | 293 |

### Per-subsystem delta (boot-relevant transitions)

Captures the partial-convergence-with-subsystem-stratification case: which subsystems converged and which didn't. The post-change Bucket C scope is the union of `unchanged_fail` columns (subsystems still requiring source-build) plus any new `to_fail` regressions.

| Subsystem | to_clean | to_fail | within_fail | unchanged_clean | unchanged_fail |
|---|---:|---:|---:|---:|---:|
| audio | 0 | 0 | 0 | 0 | 6 |
| bt | 0 | 0 | 0 | 4 | 0 |
| camera | 0 | 0 | 0 | 0 | 1 |
| charger | 0 | 0 | 0 | 0 | 3 |
| dfr | 0 | 0 | 0 | 0 | 17 |
| firmware-virt | 0 | 0 | 0 | 0 | 3 |
| misc | 0 | 0 | 0 | 91 | 201 |
| mm | 0 | 0 | 0 | 0 | 1 |
| network | 0 | 0 | 0 | 0 | 24 |
| regulator-pmic | 0 | 0 | 0 | 0 | 13 |
| sched-pm | 0 | 0 | 0 | 0 | 2 |
| secure | 0 | 0 | 0 | 0 | 1 |
| thermal | 0 | 0 | 0 | 0 | 2 |
| touch | 0 | 0 | 0 | 0 | 2 |
| usb | 0 | 0 | 0 | 0 | 7 |
| wlan | 0 | 0 | 0 | 0 | 10 |

