#!/usr/bin/env bash
# validate_module.sh — wrapper around kmod_validate.py with all the canonical
# args pre-supplied. Designed for fast per-module post-build validation.
#
# Usage:   tools/jm2/validate_module.sh <ko-path> [<ko-path> ...]
# Output:  CSV row(s) on stdout (with header). Exit 0 if all pass, 1 otherwise.

set -euo pipefail

LINEAGE_ROOT="${LINEAGE_ROOT:-/home/jmulesa/android/lineage}"
KMOD="$LINEAGE_ROOT/kernel/oneplus/sm8850-modules/tools/jm2/kmod_validate.py"
KERNEL_SYMVERS="$LINEAGE_ROOT/out/target/product/infiniti/obj/KERNEL_OBJ/Module.symvers"
STABLELIST="$LINEAGE_ROOT/kernel/oneplus/sm8850/android/abi_gki_aarch64_oneplus_15"

# Build --symvers args: kernel + every external module's Module.symvers
SYMVERS_ARGS=(--symvers "$KERNEL_SYMVERS")
while IFS= read -r f; do
    SYMVERS_ARGS+=(--symvers "$f")
done < <(find "$LINEAGE_ROOT/kernel/oneplus/sm8850-modules" -name "Module.symvers" 2>/dev/null)

if [ $# -eq 0 ]; then
    echo "usage: $(basename "$0") <ko-path> [<ko-path> ...]" >&2
    exit 2
fi

# Run validator and capture
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
python3 "$KMOD" "${SYMVERS_ARGS[@]}" --stablelist "$STABLELIST" --header -o "$TMP" "$@"
cat "$TMP"

# Exit non-zero if any verdict isn't `pass`
if awk -F, 'NR>1 && $18 != "pass" {found=1} END {exit !found}' "$TMP"; then
    echo "FAIL: at least one module did not pass validation" >&2
    exit 1
fi
exit 0
