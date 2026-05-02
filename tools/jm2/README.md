# tools/jm2/ — Phase 2 validation infrastructure

Three scripts that turn "did the build succeed?" into "is this module
structurally and ABI-correct against this kernel?"

## kmod_validate.py — per-module ABI validator

Inputs: a `.ko`, the kernel's `Module.symvers` (and optionally one or
more external module trees' Module.symvers for intermodule resolution),
and a stablelist for KMI-cleanliness scoring.

Outputs: one CSV row per `.ko` capturing vermagic, presence/count of
`__versions`, CRC match rate, KMI-cleanliness percentage, unresolved
imports, and a verdict in `{pass, fail-no-vermagic,
fail-vermagic-mismatch, fail-crc-mismatch, fail-crc-unknown-symbol,
fail-unresolved-imports}`.

```bash
KMOD=tools/jm2/kmod_validate.py
SYMVERS=$OUT/obj/KERNEL_OBJ/Module.symvers
EXT_SYMVERS=$(find $MODULES_TREE -name Module.symvers)
STABLELIST=$KERNEL/android/abi_gki_aarch64_oneplus_15
find $KERNEL_MODULES_DIR -name '*.ko' -print0 \
  | xargs -0 python3 $KMOD \
      --symvers $SYMVERS \
      $(printf -- '--symvers %s ' $EXT_SYMVERS) \
      --stablelist $STABLELIST \
      -o /tmp/baseline.csv
```

## bazel_kbuild_diff.py — translation correctness check

Inputs: a BUILD.bazel (plus any *.bzl files referenced) defining
`define_oplus_ddk_module(...)` calls, and a hand-written Kbuild that
should consume the same modules.

Outputs: per-module discrepancy report:
- `error`: missing `obj-m` target or missing source object
- `warn`: extra targets, missing local_defines or include path in ccflags
- `info`: ko_deps that need an explicit `KBUILD_EXTRA_SYMBOLS` entry

Limitation: Starlark is regex-parsed, not interpreted. Conditional
constructs and string-formatting in Bazel produce best-effort matches.
Designed to flag-rather-than-silently-accept.

```bash
python3 tools/jm2/bazel_kbuild_diff.py \
    --bazel vendor/oplus/kernel/dfr/oplus_local_modules.bzl \
    --kbuild vendor/oplus/kernel/dfr/Kbuild
```

## wave_gate.py — per-wave hard gate

Inputs: a wave manifest (one module name per line) and a
`kmod_validate.py` CSV covering at least those modules.

Outputs: pass/fail with itemized list of failing modules + sample
verdicts. Exit non-zero if anything fails.

```bash
python3 tools/jm2/wave_gate.py \
    --wave waves/03-dfr.list \
    --csv /tmp/baseline.csv
```

## Initial baseline

`~/android/baseline_csv/` (outside this repo, regenerable) has three
CSVs from a fresh post-Phase-1 build:

| File | Modules | Verdict distribution |
|------|--------:|----------------------|
| `oem_prebuilts.csv` | 557 | 557 fail-vermagic-mismatch |
| `source_externals.csv` | 36 | 36 pass |
| `intree_modules.csv` | 228 | 228 pass |

The all-OEM-fail-vermagic-mismatch result is the empirical confirmation
of the Phase 1 finding (CRCs and vermagic don't canonicalize between
OEM's genksyms output and ours). This drives Phase 5+'s expanded scope:
source-build every module in `modules.load`, not just the K3 subset.
