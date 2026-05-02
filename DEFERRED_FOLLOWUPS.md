# Deferred follow-ups

Tracker for work items that surface during Phase 5+ wire-up but are
out-of-scope for the current wave. Per `IMPLEMENTATION_PLAN.md` §12,
"anything that isn't strictly necessary to get the 360 modules
building with matching CRCs goes into a deferred backlog. Land
Bucket C, validate against hardware with the source-built kernel,
*then* decide whether the deferred items are worth pursuing."

Format: each entry has trigger context + concrete tasks + rationale
for deferring. Items move out of this file when they're either
landed (commit hash) or explicitly accepted as won't-do.

---

## Wire `BOARD_PREBUILT_KERNEL=true` build switch

**Surfaced:** 2026-05-02 (Wave 1 close-out review).

**Context:**
`IMPLEMENTATION_PLAN.md` §5.3 says each wave must keep both build
paths green:
1. Source-built kernel + waves 1..N source-built modules
2. OEM kernel + full prebuilt module set (the Option-3 fallback)

We don't have a one-line switch to toggle path 2. Verifying it would
currently require manual boot.img surgery (replace source kernel
`Image` with OEM `Image`, re-pack, re-flash). What we DO verify is
that the OEM prebuilt corpus at `device/oneplus/infiniti-kernel/` is
untouched and that `BOARD_VENDOR_KERNEL_MODULES` wildcard still
references it, so the fallback is *structurally* intact even if not
exercised end-to-end per wave.

**Concrete tasks:**

1. Add `TARGET_PREBUILT_KERNEL := $(LOCAL_PATH)/../infiniti-kernel/Image`
   guarded by a build flag in
   `device/oneplus/sm8850-common/BoardConfigCommon.mk`:

   ```makefile
   ifeq ($(BOARD_PREBUILT_KERNEL),true)
   TARGET_PREBUILT_KERNEL := $(LOCAL_PATH)/../infiniti-kernel/Image
   # disable kernel-source build path
   TARGET_KERNEL_EXT_MODULES :=
   else
   # ... existing source-build wiring
   endif
   ```

2. Confirm the OEM kernel binary exists at the assumed path
   (`device/oneplus/infiniti-kernel/Image`). If only `boot.img` is
   shipped, add a build-time unpack step to extract Image from it.

3. Add a wrapper `~/android/iter_brunch_fallback.sh` that runs
   `brunch` with `BOARD_PREBUILT_KERNEL=true`.

4. Update `wave_<N>_status.md` template to require BOTH builds green
   before marking a wave complete.

5. Optionally: add a CI-like `tools/jm2/verify_both_paths.sh` that
   runs both builds and asserts both produce flashable
   `lineage-...zip` files.

**Effort estimate:** 1–2 days. The `TARGET_PREBUILT_KERNEL` plumbing
in LineageOS device builds is well-documented; the harder part is
ensuring the resulting boot.img has correct GKI ABI metadata + that
the prebuilt module set's vermagic still matches.

**Rationale for deferring:** The structural fallback path (OEM
prebuilts in `BOARD_VENDOR_KERNEL_MODULES` wildcard) is intact and
the source-built path is what matters for MVB. The "both paths
green" requirement is a defensive posture that's most valuable when
we approach hardware test time and want a cheap retreat. Doing the
plumbing now would slow Phase 5 wire-up without immediate payoff.

**When to revisit:** Right before Phase 6 hardware test, OR if a
Phase 5 wave introduces a regression that we suspect breaks the
fallback (then the switch is the diagnostic tool that confirms).

---

## Make Phase 3 classifier handle hyphen/underscore normalization

**Surfaced:** 2026-05-02 (Wave 1 prep — the "76 unmapped" triage
found the Phase 3 classifier didn't normalize `-`↔`_` between
modules.load names and the canonical-CSV `MODULE_NAME` field, leading
to 66 false-positive "unmapped" entries that were actually mapped).

**Concrete task:**
Update `tools/jm2/kmod_validate.py` (or a new helper) to canonicalize
module names by `.replace("-", "_")` when joining modules.load
entries against built-module CSVs. Re-run baseline classification.

**Rationale for deferring:** The triage already produced the
correct 217-modules-needing-wire-up scope number. The classifier
inconsistency is cosmetic for the rest of Phase 5 — we have the
right list. Worth fixing for accuracy of any future re-runs but
not blocking.

**When to revisit:** Anytime kmod_validate.py is touched, or before
generating any future baseline CSV.

---

## EXPORT_SYMBOL upstream submission cadence

**Surfaced:** 2026-05-02 (EXPORT_SYMBOL_HANDLING.md authoring).

**Context:**
Phase 5+ will generate kernel-side EXPORT_SYMBOL additions
(estimated 50–150 over the full wire-up). The handling doc says
"Batch upstream submissions every 4–6 wave landings" but currently
no upstream submission process is set up — no contact with AOSP /
Qualcomm CAF / OnePlus OSS maintainers, no submission template, no
review cadence.

**Concrete tasks:**

1. Identify upstream maintainer contacts for the relevant trees
   (AOSP Common Kernel, Qualcomm CAF, OnePlus OSS).
2. Draft a submission template (cover letter, per-symbol commit body
   format).
3. After ~4 waves of EXPORT additions accumulate, do a first batch
   submission as a test of the pipeline.
4. Track upstream-status in `kernel_export_additions.md` (file
   referenced by EXPORT_SYMBOL_HANDLING.md but not yet created;
   creates itself organically when the first wave needs an export).

**Rationale for deferring:** Phase 5 wire-up generates the export
backlog that motivates the submission pipeline. Setting up the
pipeline before we have anything to submit is premature. Wave 1
landed with zero EXPORT additions; the file isn't needed yet.

**When to revisit:** Either when the first wave generates a
non-trivial EXPORT addition (creates `kernel_export_additions.md`
organically), OR after 4 waves accumulate (whichever comes first).

---

## Format

To add new entries:

```
## <One-line title>

**Surfaced:** YYYY-MM-DD (where/when).

**Context:** ...

**Concrete tasks:** ...

**Rationale for deferring:** ...

**When to revisit:** ...
```

When an item moves out (landed or accepted as won't-do), strike it
through with `~~`-markers and prepend a "RESOLVED YYYY-MM-DD: ..."
line. Don't delete — historical record matters.
