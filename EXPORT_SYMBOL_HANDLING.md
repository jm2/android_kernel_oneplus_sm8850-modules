# EXPORT_SYMBOL handling discipline

Phase 5+ wave wire-up will surface dozens (estimate: 50–150) of cases
where a consumer module references a kernel-internal symbol that isn't
currently `EXPORT_SYMBOL`'d. The fix is usually a one-line addition in
the in-tree kernel source. This doc captures how to do that
sustainably so we don't accumulate cruft, miss upstream submissions,
or duplicate stablelist entries.

This is referenced by `WIRE_UP_RECIPE.md` and is part of the
allowed-scope-expansion rule from `IMPLEMENTATION_PLAN.md` §12.

---

## When to add an EXPORT_SYMBOL

When `kmod_validate.py` reports `fail-unresolved-imports` AND the
unresolved symbol exists in our kernel source but isn't currently
exported, that's the trigger. Workflow:

1. Find where the symbol is defined in the kernel source
   (`grep -rn 'static.*<symbol>(' kernel/oneplus/sm8850/`).
2. If it's `static` — promote to non-static AND add `EXPORT_SYMBOL` /
   `EXPORT_SYMBOL_GPL`.
3. If it's already non-static — just add the export.
4. Confirm the symbol is NOT already on the AOSP stablelist
   (`grep -E "^  <symbol>$" kernel/oneplus/sm8850/gki/aarch64/symbols/*` —
   should return nothing for additions; if it returns a hit, the
   stablelist is supposed to bring it through; check whether it's
   actually being exported).

---

## Anti-patterns

- ❌ **Don't bundle EXPORT additions with module wire-up commits.**
  Each addition gets its own commit. Reasons: makes upstream
  cherry-picking trivial; trivializes reverts if a wave gets dropped;
  keeps the wave wire-up's diff scoped to "bazel-to-kbuild translation."
- ❌ **Don't add EXPORT for a symbol already on the qcom/oplus
  stablelist.** If KMI-strict trim removed it from `Module.symvers`,
  the right fix is checking that it's in our whitelist file
  (`android/abi_gki_aarch64_oneplus_15`), not adding a redundant
  EXPORT. wave_gate.py asserts this.
- ❌ **Don't EXPORT functions that should be `static inline` in a
  header.** Many "private" helpers belong in headers, not in the
  exported surface. Check whether the consumer should `#include` a
  header instead.

---

## Per-addition commit format

```
kernel: export <symbol> for <consumer> (Phase 5 wave N)

<consumer>.ko (vendor/<path>/<file>.c) imports <symbol> at modprobe
time but <kernel-source-path>/<file>.c only defines it as a
file-local function. Promote to non-static and add EXPORT_SYMBOL
(or EXPORT_SYMBOL_GPL if GPL surface).

This is a candidate for upstream stablelist addition — see
~/android/lineage/kernel/oneplus/sm8850-modules/kernel_export_additions.md
for the running list awaiting batch upstream submission.

Co-Authored-By: ...
```

---

## Bookkeeping file

`kernel_export_additions.md` (lives in this repo, top-level) tracks
the running list. Schema:

```
| symbol | type | consumer module | wave | upstream status |
|---|---|---|---|---|
| keyevent_register_notifier | EXPORT_SYMBOL_GPL | (already exported by oplus_bsp_dfr_keyevent_handler) | wave 3 | n/a — module-side export |
| <new_symbol> | EXPORT_SYMBOL_GPL | <consumer>.ko | wave N | pending / submitted / merged / rejected |
```

When AOSP accepts an upstream stablelist addition, mark the
`upstream status` and the symbol can drop out of our local
`abi_gki_aarch64_oneplus_15_extras` (since it'll be on the
all-vendor union directly).

---

## Periodic cleanup

After each wave completes, sweep for dead exports:

1. List every EXPORT_SYMBOL we added in this wave's commits
2. For each, confirm there's still a consumer referencing it via
   `grep -rn '<symbol>' kernel/oneplus/sm8850-modules/vendor/ \
                       | grep -v EXPORT_SYMBOL`
3. If no consumer, the export is cruft from a since-revised wave —
   revert.

`wave_gate.py` does NOT enforce this; it's a periodic manual sweep.

---

## Upstream submission cadence

Batch upstream submissions every 4–6 wave landings. Aim for
clean-history series: rebase squash any fixup commits, write a cover
letter that references the consumer modules. Targets:

1. AOSP common kernel (linux/kernel/git/torvalds for general-purpose
   exports; Android Common Kernel for vendor-hook tracepoints)
2. Qualcomm CAF (for qcom-internal exports we add to
   `drivers/clk/qcom/`, `drivers/soc/qcom/`, etc.)
3. OnePlus OSS (`OnePlusOSS/android_kernel_common_oneplus_sm8850`
   accepts upstream-aligned PRs for sm8850-specific exports)

If upstream rejects, the export stays in our jm2 fork indefinitely.
That's fine; the bookkeeping just records the rejection so we don't
re-attempt without new context.

---

## Phase 4.5 will start populating this

The proof-point (`oplus_bsp_dfr_keyevent_handler`) didn't need any
EXPORT additions — it only used AOSP-stablelist symbols. Phase 4.5's
harder cases (`gcc_canoe`, `cnss2`) almost certainly will. The first
real entries land there.
