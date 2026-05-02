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

`kmod_validate.py` reporting `fail-unresolved-imports` is the entry
signal — but it's NOT automatically a trigger to add a kernel-side
export. Triage the unresolved symbol through this ladder; reach for
EXPORT_SYMBOL only at the bottom:

1. **Is the symbol already exported by another external module?**
   ```
   grep -rn 'EXPORT_SYMBOL.*<symbol>' kernel/oneplus/sm8850-modules/vendor/
   ```
   If yes → the consumer module is missing a `KBUILD_EXTRA_SYMBOLS`
   pointer at the producer's `Module.symvers`. Fix the
   external-module Makefile, not the kernel. **Don't add a redundant
   kernel export.**

2. **Is the symbol on the AOSP qcom/oplus/base stablelist?**
   ```
   grep -E "^  <symbol>$" kernel/oneplus/sm8850/gki/aarch64/symbols/*
   ```
   If yes → it's supposed to come through the GKI mechanism. Trim
   removed it because our local whitelist file
   (`android/abi_gki_aarch64_oneplus_15`) is missing it. Add it to
   the union (or the `_extras` file if the AOSP file misses it for
   our particular config). **Don't add a redundant kernel export.**

3. **Could this be a `static inline` in a shared header instead?**
   For small private helpers (one-liner getters, predicate functions,
   bit-manipulation utilities), the right answer is to move the
   definition to a header in `include/linux/<module>/` (or the
   subsystem's local include dir) as `static inline`. The consumer
   `#include`s it directly; no kernel export added. This is the
   preferred answer when the symbol is small and clearly auxiliary.
   **Don't EXPORT what should be a header inline.**

4. **Only after 1–3 are ruled out** — promote to non-static and add
   `EXPORT_SYMBOL` (or `EXPORT_SYMBOL_GPL` if GPL surface). Workflow:
   - Find where the symbol is defined in the kernel source
     (`grep -rn 'static.*<symbol>(' kernel/oneplus/sm8850/`).
   - **Read the function carefully before promoting** (see ABI
     commitment caveat below).
   - If `static` → drop `static` AND add the export.
   - If already non-static → just add the export.
   - Add an entry to `kernel_export_additions.md` (see Bookkeeping).

---

## ABI commitment caveat (read before promoting any `static`)

When you drop `static` and add `EXPORT_SYMBOL`, you commit to the
function's current signature as ABI:

- For Lineage-private exports (those that stay in our jm2 fork), this
  is mostly fine — we control both producer and consumers.
- For exports we submit upstream, the signature you submit becomes
  the long-term contract. Future kernel updates that would otherwise
  freely refactor the static helper now have to preserve compat.

Before promoting, read the function and ask:
- **Was it intentionally static?** Tell-tale signs: it takes opaque
  internal pointers (e.g., `struct fs_struct *`), exposes
  implementation details that aren't part of any external API
  surface, or has a comment hinting at internals (`/* internal use
  only */`, `/* helper for foo() */`).
- **Does its signature look refactor-vulnerable?** If it takes many
  internal-struct pointers or returns an internal type, the
  signature will likely change in future upstream churn.
- **Is there a more stable wrapper above it?** Often the static
  helper is below a non-static API that's already exported.
  Consumer should call the wrapper, not the helper.

If any of these hold, prefer the header-inline path (item 3 in the
trigger ladder) or pursue an upstream refactor that exposes a
stable-by-design wrapper, rather than promoting the internal
helper as-is.

When you do promote, document the rationale in the per-export
commit message (Per-addition commit format below).

## Anti-patterns

- ❌ **Don't bundle EXPORT additions with module wire-up commits.**
  Each addition gets its own commit. Reasons: makes upstream
  cherry-picking trivial; trivializes reverts if a wave gets dropped;
  keeps the wave wire-up's diff scoped to "bazel-to-kbuild translation."
  Treat this rule as non-negotiable; an agent should reject its own
  work if it bundles an EXPORT into a wire-up commit.
- ❌ **Don't add EXPORT for a symbol already on the qcom/oplus
  stablelist.** If KMI-strict trim removed it from `Module.symvers`,
  the right fix is checking that it's in our whitelist file
  (`android/abi_gki_aarch64_oneplus_15`), not adding a redundant
  EXPORT. wave_gate.py asserts this.
- ❌ **Don't add EXPORT for a symbol already exported by another
  external module** (the re-export case). Fix the consumer's
  `KBUILD_EXTRA_SYMBOLS` instead.
- ❌ **Don't EXPORT functions that should be `static inline` in a
  header.** Many "private" helpers belong in headers, not in the
  exported surface. Check whether the consumer should `#include` a
  header instead.
- ❌ **Don't promote a `static` to exported without reading the
  function for ABI-stability signals.** See "ABI commitment caveat"
  above.

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
