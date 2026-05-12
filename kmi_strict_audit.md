# KMI-strict audit — 2026-05-11

Per Phase 2.5 of IMPLEMENTATION_PLAN.md. Measures, per OEM-prebuilt `.ko`, whether it loads against our post-Phase-1 KMI-canonicalized kernel, and aggregates into a Phase-6 boot prediction.

Audit inputs:
- Kernel Module.symvers: `/home/jmulesa/android/lineage/out/target/product/infiniti/obj/KERNEL_OBJ/Module.symvers`
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
| `oplus_is_daemon_event_id` | 7 |

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

## Interpretation (manual, 2026-05-11) — what the data means

### Finding 1: module_layout VETO holds for 557/557 vendor_dlkm

Every OEM-prebuilt `.ko` in `device/oneplus/infiniti-kernel/` carries
`__versions[module_layout] = 0xe976b219`. Our post-Phase-1 kernel exports
`module_layout = 0x21d0f8b0`. This single-symbol mismatch is sufficient
to prevent any vendor module from loading on our kernel.

This explains the 0508 BOARD_PREBUILT_KERNEL=true ROM flash failure
without needing any other diagnosis: the OEM-kernel-fallback path is
structurally broken (OEM modules don't load against our kernel — they'd
need to be flashed with OEM's vmlinux to work, but our boot.img carries
our vmlinux). The "fastboot wipe-super" path that the user attempted
during recovery was orthogonal mechanics; the underlying load-pipeline
was DOA regardless.

### Finding 2: module_layout is NOT the lone problem — the divergence is systemic

The secondary verdict (post-module_layout-fix) is *identical* to the
primary: **312/389 vendor modules in boot-load remain load-fail-crc**
even ignoring module_layout. The CRC mismatch isn't a single struct;
it's hundreds of symbols spanning the entire kernel API surface:

| Symbol class | Example | Affected boot modules |
|---|---|---:|
| Compiler/sanitizer | `__stack_chk_fail`, `__fortify_panic` | 277, 147 |
| printk / debug | `_printk`, `_dev_err` | 264, 158 |
| Memory profiling | `mem_alloc_profiling_key` | 200 |
| Slab allocator | `kfree`, `kmalloc_caches`, `__kmalloc_cache_noprof`, `__kmalloc_noprof`, `devm_kmalloc` | 196, 170, 170, 115, 167 |
| Mutex API | `mutex_lock`, `mutex_unlock`, `__mutex_init` | 185, 185, 152 |
| Platform driver | `__platform_driver_register`, `platform_driver_unregister` | 163, 153 |
| Device tree | `of_property_read_variable_u32_array`, `of_find_property` | 145, 117 |
| String/list | `memset`, `memcpy`, `__list_add_valid_or_report` | 143, 139, 116 |

Every one of these is a foundational kernel API. Our kernel's CRCs for
them don't match OEM's. This is not a small-vendor-extension problem;
it's **wholesale header/config divergence** between our build and OEM's.

Likely root causes (in decreasing probability):

1. **CONFIG-driven struct-layout divergence.** Many of the listed
   symbols' CRCs are sensitive to widely-included headers whose content
   varies by Kconfig. `mem_alloc_profiling_key`'s presence indicates
   `CONFIG_MEM_ALLOC_PROFILING=y`; `__kmalloc_cache_noprof` (the
   `_noprof` suffix) is a profiling-aware variant of `kmalloc`. If our
   `.config` enables these while OEM's didn't (or vice versa), every
   slab allocator user sees a different CRC. Same logic for
   `__fortify_panic` (FORTIFY_SOURCE level) and `__stack_chk_fail`
   (CC_STACKPROTECTOR_STRONG vs ALL).
2. **Kernel-version skew at the patch level.** Our kernel SHA may have
   merged ACK fixes that changed a struct definition (e.g., adding a
   field to `struct mutex`, `struct platform_driver`, `struct module`,
   `struct kmem_cache`). OEM's kernel snapshot is at a different ACK
   point.
3. **CC compiler version influencing genksyms output.** Less likely
   given genksyms parses preprocessed C, but possible if our preproc
   pipeline produces slightly different token streams.

### Finding 3: system_dlkm is fully Phase-6-ready

All **95** modules from `system_dlkm/lib/modules/` load clean. These are
the AOSP-canonical GKI modules. They were built against AOSP's KMI
surface, which matches ours by construction (Phase 1 Track A
canonicalized to that exact surface). This validates that the KMI
canonicalization DID work — it just didn't extend to vendor modules
because vendor modules consume vastly more kernel API than GKI exposes.

### Finding 4: 73 of 221 "misc" cluster modules load clean

In the `misc` cluster (modules whose names didn't match our subsystem
regex), 73 load-clean entries exist. These are likely AOSP / upstream-
aligned modules that ship from vendor_dlkm but use only GKI-canonical
symbols. Worth a follow-up grep to enumerate (they're the "free wins"
of the OEM corpus — no source-build needed). The remaining 148 are
vendor-implementation-heavy.

### Finding 5: Vendor-internal "missing" cohort is dominated by 3 frameworks

The top-30 missing-symbols list clusters into:

1. **`ipc_log_*` (3 symbols × 31–39 modules)** — the qcom IPC logging
   framework. Our kernel.mk pipeline references
   `kernel/trace/qcom_ipc_logging` as a producer; this is in-tree but
   may not be source-built in our current configuration. Wiring it
   would unlock ~40 modules' missing-import counts (though their CRC
   failures persist).
2. **`tp_*`, `common_touch_*` (~10 symbols × 8–18 modules each)** — the
   oplus touch framework. The `oplus_hbp_core` module already wired in
   2D should provide these, but the consuming OEM prebuilts can't see
   it because OEM was built against OEM's hbp_core not ours. Source-
   building the touch consumers (2D-style continuation) replaces the
   problem.
3. **`swr_*`, `msm_cdc_pinctrl_*` (~5 symbols × 9–11 modules each)** —
   soundwire and codec-pinctrl framework. Source-building the
   `audio-kernel` consumers replaces the issue.

These are all "source-build the consumers" answers, not "extend the
whitelist" answers — the symbols don't exist in our kernel surface at
all, and adding them would require building+EXPORT'ing producers we
don't currently surface.

---

## Recommendation

### Strategic call: Path B per IMPLEMENTATION_PLAN.md §2.5.4

The data unambiguously points to **Path B (audit shows mostly load-fail
→ Bucket C source-build is genuinely required before Phase 6)**.
Specifically:

- The OEM-prebuilt fallback is dead. 0508 ROM was structurally
  unflashable; this was inevitable, not bad luck. There is no `BOARD_
  PREBUILT_KERNEL=true` rescue path until OEM-kernel-on-our-stack is
  reconstructed (out of scope).
- "Targeted canonicalization extensions" do not address the dominant
  failure mode. The top mismatched symbols (`__stack_chk_fail`,
  `_printk`, `mem_alloc_profiling_key`, slab/mutex APIs) cannot be
  fixed by extending the whitelist — they're exported by our kernel
  already, just at different CRCs. Whitelist extensions help only the
  `load-fail-missing` cohort, not `load-fail-crc`.
- The only durable solution is **source-build every module in
  `modules.load`**. This converges 100% of the divergence by building
  against our kernel's struct/header set. This is the comprehensive
  close-out the user asked for; the data confirms it's load-bearing,
  not just stretch.

### Tactical sequence

1. **Wave 2 closeout (2E batch 2 cascade + 2G msm graphics/video +
   optionally 2F.3 retry)** — proceed. ~10–12 modules + the cascade.
   Pre-flight done; the work is shovel-ready.
2. **Wave 5 — WLAN platform + driver** — was deferred from Wave 2.
   Source-build cnss2 + cnss_utils + icnss2 + qcacld-3.0. Plan §5.1
   calls this hairiest single subsystem.
3. **Wave 3 — DFR completion** (oplus DFR cluster — modules.load
   has 4 DFR entries already source-built in Wave 1; verify rest of
   the cluster).
4. **Wave 4 — qcom audio extension** (the missing `swr_*` /
   `msm_cdc_pinctrl_*` producers; the 2C audio wave laid groundwork).
5. **Wave 6 — Touch framework completion** (the missing `tp_*` /
   `common_touch_*` symbols). 2D source-built the consumers; the
   `oplus_hbp_core` producer is wired but the AOSP-flavored consumers
   aren't picking up our hbp_core's exports for the reason analyzed
   above. Likely needs depmod-bridge / synth_symvers tooling.
6. **Wave 7 — Adreno GPU + video + camera + display** (the remaining
   large QCOM subsystems). Plan §8 Wave 5/6/7 scope.
7. **Wave 8 — Misc tail** (the 148-module misc-vendor cohort,
   subsystem-by-subsystem until exhausted).

### Investigation findings (2026-05-11)

Root-cause check completed during audit. Three sources of divergence
confirmed:

**Source 1: Debug-config divergence between our kernel and OEM's.**

Inspection of our build's `.config`:

| Config | Our build | OEM (inferred) | CRC effect |
|---|---|---|---|
| `CONFIG_SLUB_DEBUG` | `=y` | not in vermagic; likely off | Adds redzone + freelist debug to `struct kmem_cache` → affects `kmalloc_caches`, `__kmalloc_*`, `kfree`, `devm_kmalloc` CRCs |
| `CONFIG_UBSAN` | `=y` (incl. `UBSAN_TRAP`, `UBSAN_BOUNDS`, `UBSAN_ARRAY_BOUNDS`, `UBSAN_LOCAL_BOUNDS`) | not in vermagic; likely off | UBSAN attribute annotations affect signatures of instrumented symbols |
| `CONFIG_KASAN` | `=y` (`KASAN_HW_TAGS`, `KASAN_VMALLOC`) | not in vermagic; likely off | Affects compiler attributes; less struct-layout impact under HW_TAGS than GENERIC but still measurable |
| `CONFIG_RANDOMIZE_KSTACK_OFFSET` | `=y` | unknown | Stack-canary placement affects `__stack_chk_fail` CRC |
| `CONFIG_FORTIFY_SOURCE` | `=y` | likely `=y` (OEM uses `__fortify_panic`) | Same on both — not divergent |
| `CONFIG_MEM_ALLOC_PROFILING` | `=y` | likely `=y` (OEM uses `mem_alloc_profiling_key`) | Same on both — not divergent |
| `CONFIG_RANDSTRUCT_NONE` | `=y` | likely `=y` | Same — not divergent |

The `SLUB_DEBUG` + `UBSAN` + `KASAN_HW_TAGS` triad is the strongest
hypothesis for the kernel-core CRC drift (`_printk`,
`__stack_chk_fail`, `kfree`, `mutex_lock`, etc.). Our build is
configured for *kernel development* (debug-on); OEM ships a
*production-config* kernel.

**Source 2: Kernel patch-level skew.**

- OEM vermagic: `6.12.23-android16-5-o-g362117606264-4k`
- Ours: based on `android16-6.12-2025-06_r8` (Phase 0 confirmed)

Both 6.12.23 base, but different ACK patch levels. ACK patches can
add struct fields, refactor inline helpers, or move EXPORT_SYMBOLs
between TUs. Some CRC drift is inevitable from this alone.

**Source 3: Concrete sample CRCs (sanity check).**

| Symbol | Our CRC | OEM CRC | Match? |
|---|---|---|---|
| `module_layout` | `0x21d0f8b0` | `0xe976b219` | ✗ |
| `_printk` | `0x92997ed8` | `0x16b5b21d` | ✗ |
| `__stack_chk_fail` | (varies) | `0xd272d446` | ✗ |
| `mem_alloc_profiling_key` | (varies) | `0x8ee1928d` | ✗ |
| `__kmalloc_cache_noprof` | (varies) | `0x6cc46e45` | ✗ |
| `mutex_lock` | (varies) | `0x995658e3` | ✗ |

Audit's data is correct; the divergence is real and systematic.

### What this implies for the source-build decision

The investigation slightly opens an alternative path:

**Path B' — converge debug-configs, re-audit, then decide.**

If we flip `CONFIG_SLUB_DEBUG=n`, `CONFIG_UBSAN=n`, `CONFIG_KASAN=n`
(matching OEM's likely production profile), rebuild the kernel, and
re-run the audit, a meaningful fraction of OEM modules may flip from
`load-fail-crc` to `load-clean`. Cost: half a day (config edit +
rebuild + re-audit). Benefit: hard data on what's left after debug-
config convergence — vs the kernel-patch-skew baseline.

The remaining mismatches after this convergence are then
patch-skew-driven, and source-build remains the only fix for those.
But the source-build scope might be materially smaller — e.g., if
debug-config flips converge 200 of the 312 mismatches, we'd only need
to source-build the ~110-module patch-skew tail, not the full corpus.

**Recommendation: do Path B' before committing to full source-build.**
The audit-driven decision tree this enables is the high-value next
step. If Path B' shows little convergence → we know full source-build
is the answer, no time lost. If Path B' shows major convergence → we
save weeks.

### Tradeoff: shipping kernel debug-off vs debug-on

Two considerations on disabling KASAN/UBSAN/SLUB_DEBUG:

1. **Debugging visibility.** These features catch memory-safety bugs
   at runtime. Disabling them ships a "less safe" kernel in the
   functional sense — bugs that would have been caught early instead
   manifest as silent corruption.
2. **OEM ships debug-off in production.** OxygenOS doesn't have
   KASAN/UBSAN enabled; OEM rebuilds the kernel with these off for
   release. We're effectively choosing whether to track OEM's release
   profile (debug-off) vs an AOSP-userdebug-like profile (debug-on).
3. **CONFIG_KASAN_HW_TAGS** specifically: this requires ARMv8.5 MTE
   hardware support. Even when set `=y`, runtime activation depends
   on the platform; on canoe (SM8850) it may or may not be wired.
   Worth checking whether KASAN_HW_TAGS=y actually does anything at
   runtime on canoe before keeping it.

Acceptable resolution: disable all three for the Phase-6 boot test;
re-enable for development builds. Two .config profiles, one
codebase.

### What this audit doesn't decide

- **Whether each Wave-2-deferred OEM prebuilt becomes Bucket-C or
  Bucket-D.** That's a per-module disposition decision based on
  source availability + per-feature importance. The audit gives us
  the prioritization (subsystem table) but not the verdict.
- **Whether to skip non-critical OEM modules entirely.** Some boot-
  loaded modules may bind to canoe-disabled DT nodes (per
  `noop_modules.md`); those are runtime-effective-no-ops and could
  drop from `modules.load` rather than be source-built.
- **The post-build verification gate.** Phase 6 still needs the
  actual hardware boot to confirm the source-built ROM brings up
  display, touch, WiFi, etc. The audit predicts WILL-IT-LOAD; not
  WILL-IT-WORK.

### Re-run protocol

Re-run this audit after each meaningful change:
- Kernel `.config` adjustment (`CONFIG_MEM_ALLOC_PROFILING` etc.) →
  re-run, diff CSV against today's baseline, measure delta.
- Kernel source change touching exported struct → re-run.
- Each Wave-N source-build landing → re-run to mark the affected OEM
  prebuilts as `excluded-source-built-override` (currently 0 because
  source-built-corpus wasn't passed; fix in next re-run by passing
  `--source-built-corpus $OUT/.../updates`).

The CSV diff is the durable progress metric.

---

## Path B' empirical verdict (2026-05-11, executed)

**Hypothesis tested:** disabling KASAN, UBSAN, SLUB_DEBUG, and
RANDOMIZE_KSTACK_OFFSET (a "production profile" fragment) converges our
kernel's CRCs with OEM's, allowing a meaningful fraction of the 557
OEM-prebuilt vendor modules to load on our kernel without source-build.

**Method:**
1. Authored
   `kernel/oneplus/sm8850/arch/arm64/configs/production_profile.config`
   disabling the four targeted CONFIGs.
2. Patched a source-tree #ifdef hole in
   `drivers/soc/qcom/minidump_memory.c` (calls to
   `md_dump_slabinfo()` / `slab_owner_handles_size` referenced
   unconditionally despite definitions gated on `CONFIG_SLUB_DEBUG`;
   added `__maybe_unused` to the three affected static variables).
3. Merged the fragment into TARGET_KERNEL_CONFIG; verified the .config
   reflected all four flips; rebuilt the kernel (`mka kernel`).
4. Confirmed the rebuild was genuine: vmlinux mtime fresh, 194 MB;
   Module.symvers fresh, 9992 → 9988 lines (4 KASAN-only symbols
   correctly trimmed); `kasan_flag_enabled` no longer in
   `Module.symvers`.
5. Re-ran `kmi_audit.py` with `--baseline-csv` against the pre-flip
   baseline. Output:
   `kernel/oneplus/sm8850-modules/kmi_strict_audit_path_b_prime.md` +
   `kmi_audit_20260511_path_b_prime.csv`.

**Empirical result: ZERO convergence.**

| Transition | Modules |
|---|---:|
| flipped: load-fail → load-clean (UNLOCK) | **0** |
| flipped: load-clean → load-fail (REGRESSION) | 0 |
| changed verdict within load-fail-* | 0 |
| unchanged load-clean | 95 (system_dlkm — already clean) |
| unchanged load-fail-* | 557 (full vendor_dlkm corpus — unchanged) |

CRCs of the most-consumed OEM symbols **did not change**:
- `module_layout`: `0x21d0f8b0` (pre-flip and post-flip) vs OEM `0xe976b219` — still divergent.
- `_printk`: `0x92997ed8` (unchanged) vs OEM `0x16b5b21d`.
- `mutex_lock`: `0xd5977bfb` (unchanged) vs OEM `0x995658e3`.
- `kfree`, `__kmalloc_cache_noprof`, `__platform_driver_register`,
  `__fortify_panic`, `memcpy`, `memset` — all unchanged.

**Interpretation:** the Source-1 hypothesis (debug-config divergence)
was wrong. KASAN/UBSAN/SLUB_DEBUG/RANDOMIZE_KSTACK_OFFSET affect
instrumentation symbols (kasan_flag_enabled and friends) but **not the
struct-layout / signature hashing** that genksyms uses. Confirmed by
counting OEM-side dependencies: only 24 of 32,882 consumed-symbol
entries reference KASAN/UBSAN symbols (0.07%).

**Real cause: Source-2 — ACK patch-level skew** (`android16-5-o-g362117606264`
vs `android16-6.12-2025-06_r8`). Cannot be addressed by config flips.

### Decision: commit to Path B

The data is decisive. The only path to a flashable Phase-6 ROM that
loads OEM-prebuilt vendor modules is one of:

1. **Path B — Full source-build of the OEM corpus.** Source-build
   every module in `modules.load` against our kernel; their CRCs
   match by construction. Multi-week effort; subsumes Wave 2 closeout
   + Wave 5 WLAN + dsp/spu/oplus tail + Bucket D residual handling
   per IMPLEMENTATION_PLAN.md §2.5 Wave 2 closeout direction.
2. **Path C (alternative, not yet evaluated)** — rebase our kernel
   onto OEM's exact ACK snapshot (`android16-5-o-g362117606264`).
   This would attempt direct CRC parity rather than source-build.
   Cost: kernel-rebase merge risk, potential KMI breaks against Phase
   1 Track A canonicalization, and loss of any newer ACK fixes we've
   merged. Likely *higher* effort than Path B with worse durability.

Path B is the recommended sequence. Path C noted for completeness.

### Reverted Path B' artifacts

- BoardConfigCommon.mk wiring: REMOVED. The build is back to the
  development-profile defaults.
- `production_profile.config` fragment: KEPT IN TREE. Docstring now
  notes the empirical zero-convergence result so future agents don't
  re-test the same hypothesis. Available for non-KMI use cases
  (production-build perf measurement, KASAN-overhead-zero builds).
- `minidump_memory.c` source patches: KEPT IN TREE. The #ifdef holes
  the patches fixed are real bugs that would trip any build with
  `CONFIG_SLUB_DEBUG=n`, regardless of motivation. Net-positive
  source-tree improvement.

### Note on patch-level skew investigation

If a future session wants to investigate Path C (kernel rebase to
OEM's snapshot), the key inputs are:
- Our base: `android16-6.12-2025-06_r8` (Phase 0 confirmed via
  `kernel/oneplus/sm8850/android/ACK_SHA`).
- OEM base: vermagic `g362117606264` → first 12 chars of an ACK SHA.
  Likely on the `android16-6.12-2025-XX_rN` branch but the specific
  `_rN` indices and merges aren't published. Would need vendor source
  cooperation OR diffing a vendor source dump against ACK snapshots.

Recommendation: don't pursue Path C unless Path B encounters a
blocker. Path B is well-mapped (Wave 2 closeout + Phase 7+) and
gradually-shippable; Path C is a single large rebase with unknown
KMI consequences.

