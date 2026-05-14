# Phase 6 flash-prep — OnePlus 15 (infiniti) LineageOS 23.2

**Status:** Authored 2026-05-13 at Wave 2 close, before the first
Phase 6 hardware flash attempt with the source-built MVB ROM.

**Purpose:** Treat flash as Phase 6 prep, not Phase 6 ancillary. The
May 7 recovery experience surfaced a class of bugs that nobody
documented before the first flash attempt and that bit hard. The
floor for any flash attempt is this doc — verified-working tooling,
documented command matrix, EDL recovery on hand.

## Threat model & rationale

Phase 6 is the first runtime test of every Wave 2 deliverable. The
audit's static prediction is 69.7%; that's a static prediction, not
a runtime measurement. Some modules statically appear load-clean
but fail at probe time (regulator-not-found, GPIO-not-available,
init-ordering / DT compatible-match races, IOMMU mapping mismatches,
suspend/resume code paths). Some statically-predicted-fail modules
may have graceful-degradation paths that don't actually break boot.
We don't know which until we boot.

Cost of a botched flash with no recovery plan: the device gets
stuck in fastboot-only state with all dynamic partitions blown out,
basic fastboot can't see them, fastbootd doesn't work on this
hardware, and you spend a day reconstructing a working super.img
from extracted images while the device sits paperweight'd. We've
done this exactly once (May 7); we don't repeat it.

## Pre-flash floor — verify ALL of these before any fastboot command

1. **Pre-built complete `super.img` available locally.**
   `/tmp/stock_super.img` from the May 8 reconstruction proves the
   pipeline; build a fresh one for any flash attempt. NOT
   `super_empty.img` — that's the partition metadata layout only,
   not the dynamic partitions' content. Basic fastboot cannot
   re-populate the dynamic partitions; once `super_empty.img` is
   flashed, dynamic partitions exist but with zero-size extents
   until something writes them. Only fastbootd or
   `fastboot flash <dyn-partition>` (which requires fastbootd
   handover) repopulates. On this hardware fastbootd is not
   available; we cannot recover from `super_empty.img` alone.

   **Build the complete super.img with the Lineage ROM's per-
   partition images via `lpmake`.**

   Note: `system.img`, `system_ext.img`, and `product.img` are Android
   sparse images (their on-disk byte count is the compressed size, not
   the partition size). lpmake's `--partition <name>:readonly:<size>:<group>`
   requires the UNSPARSED size. `vendor.img`, `vendor_dlkm.img`,
   `odm.img`, and `system_dlkm.img` are raw EROFS; their on-disk size
   IS the partition size. The `img_size` shell helper below auto-
   detects + emits the correct size for either case.

   First-time build verified 2026-05-14 against the post-2G-c MVB
   ROM (kernel `6.12.23-4k-gf3f146a669fc`). Output landed at
   `out/target/product/infiniti/super.img` so it ships alongside
   the boot stack for the basic-fastboot flash sequence.

   ```bash
   cd /home/jmulesa/android/lineage/out/target/product/infiniti

   img_size() {
     local f="$1"
     if file "$f" | grep -q "Android sparse"; then
       /home/jmulesa/android/lineage/out/host/linux-x86/bin/simg2img "$f" /tmp/__s.img 2>/dev/null
       stat -c %s /tmp/__s.img
       rm -f /tmp/__s.img
     else
       stat -c %s "$f"
     fi
   }

   /home/jmulesa/android/lineage/out/host/linux-x86/bin/lpmake \
     --device-size 15032385536 \
     --metadata-size 65536 \
     --metadata-slots 3 \
     --group oneplus_dynamic_partitions_a:7515999232 \
     --group oneplus_dynamic_partitions_b:7515999232 \
     --partition system_a:readonly:$(img_size system.img):oneplus_dynamic_partitions_a --image system_a=system.img \
     --partition system_ext_a:readonly:$(img_size system_ext.img):oneplus_dynamic_partitions_a --image system_ext_a=system_ext.img \
     --partition product_a:readonly:$(img_size product.img):oneplus_dynamic_partitions_a --image product_a=product.img \
     --partition vendor_a:readonly:$(img_size vendor.img):oneplus_dynamic_partitions_a --image vendor_a=vendor.img \
     --partition vendor_dlkm_a:readonly:$(img_size vendor_dlkm.img):oneplus_dynamic_partitions_a --image vendor_dlkm_a=vendor_dlkm.img \
     --partition odm_a:readonly:$(img_size odm.img):oneplus_dynamic_partitions_a --image odm_a=odm.img \
     --partition system_dlkm_a:readonly:$(img_size system_dlkm.img):oneplus_dynamic_partitions_a --image system_dlkm_a=system_dlkm.img \
     --partition system_b:readonly:0:oneplus_dynamic_partitions_b \
     --partition system_ext_b:readonly:0:oneplus_dynamic_partitions_b \
     --partition product_b:readonly:0:oneplus_dynamic_partitions_b \
     --partition vendor_b:readonly:0:oneplus_dynamic_partitions_b \
     --partition vendor_dlkm_b:readonly:0:oneplus_dynamic_partitions_b \
     --partition odm_b:readonly:0:oneplus_dynamic_partitions_b \
     --partition system_dlkm_b:readonly:0:oneplus_dynamic_partitions_b \
     --virtual-ab \
     --sparse \
     --output super.img
   ```

   Expected stdout: per-partition "resize from 0 bytes to <N> bytes"
   info lines (one per partition_a). The "Invalid sparse file format
   at header magic" messages are informational — lpmake probes each
   `--image` for sparse-ness and falls through to raw read; the EROFS
   images legitimately aren't sparse.

   **Verify with `lpdump`** (super.img is sparse so unsparse first):

   ```bash
   /home/jmulesa/android/lineage/out/host/linux-x86/bin/simg2img \
     super.img /tmp/super_unsparsed.img
   /home/jmulesa/android/lineage/out/host/linux-x86/bin/lpdump \
     /tmp/super_unsparsed.img
   rm /tmp/super_unsparsed.img
   ```

   Expected lpdump output:
   - `Metadata version: 10.2`
   - `Metadata slot count: 3`
   - `Header flags: virtual_ab_device`
   - All 7 partitions (system, system_ext, product, vendor,
     vendor_dlkm, odm, system_dlkm) present as `<name>_a` with
     non-zero `Extents` lines and `Group: oneplus_dynamic_partitions_a`
   - Mirror partitions `<name>_b` present, empty extents (slot _b
     placeholders for the A/B-OTA mechanism)

2. **Verified-working LineageOS recovery.**
   Recovery image (`recovery.img`) from the same build artifact set.
   Confirm:
   - Sideloads via `adb sideload` work from recovery
   - "Wipe data/factory reset" works
   - "Mount system R/W" can mount system as RO at least (no
     filesystem-corrupt error)
   - The recovery's vendor_boot dependency is satisfied by the
     same build's vendor_boot.img

   Cold-test path before relying on recovery: flash recovery.img,
   reboot to recovery, sideload a NOOP / dummy zip, verify no
   "vendor_boot has different version" or "kernel version mismatch"
   errors.

3. **Stock super.img on hand as recovery floor.**
   `/tmp/stock_super.img` from the May 8 reconstruction is the
   guaranteed-bootable fallback. Keep it; do not delete after Phase 6
   even if Phase 6 succeeds. The full super (14 GB unsparsed,
   ~10 GB sparse) is the recovery floor for any future bricked-by-
   misflash situation.

4. **EDL (Emergency Download) tooling on hand.**
   The hardware-level floor. If fastboot is unrecoverable,
   EDL is the next-level fallback. Required:
   - **MSM Download Tool** (`MSMDownloadTool`) — Qualcomm's
     proprietary EDL flasher. Look for the OnePlus 15 / canoe
     variant. Mirror it locally, do not rely on first-time download
     during a brick scenario.
   - **OnePlus 15 firmware package** (the .mbn / .elf files for
     canoe). Mirror locally.
   - **EDL cable** or **EDL test point procedure** for OnePlus 15.
     Confirm the test point location vs hardware revision before
     a brick scenario occurs.
   - Verify ahead of time that the host machine has the right USB
     drivers (Qualcomm QDLoader 9008 driver on Windows; on Linux,
     `qdl` or `xqcom` open-source equivalents).

   EDL is a one-way path; it reflashes everything from scratch via
   the firehose protocol. Slow but unbrickable.

## bootloader-fastboot vs fastbootd command matrix

The May 7 recovery's specific failure mode: `fastboot wipe-super`
succeeded but every subsequent `fastboot flash <dynamic-partition>`
returned "Partition not found" because basic fastboot can only see
**physical** partitions, not the **dynamic** partitions inside
super. Dynamic partitions require fastbootd. On this hardware
fastbootd is not available (confirmed via failed `fastboot reboot
fastboot`).

**This means:** any flash plan that depends on a fastbootd path
**cannot complete** on this device. Plan accordingly.

### Physical partitions (flashable from bootloader fastboot)

These are real eMMC partitions outside super:

| Partition | Notes |
|---|---|
| `boot` | Kernel + DTB |
| `init_boot` | First-stage init ramdisk |
| `vendor_boot` | Vendor ramdisk (modules.list early-init load) |
| `dtbo` | Device-tree overlays |
| `recovery` | Recovery ramdisk |
| `vbmeta` / `vbmeta_system` / `vbmeta_vendor` | Verified-boot metadata |
| `super` | The whole super image (replaceable via flash) |

**All of these flash via basic fastboot.** Commands:

```
fastboot flash boot          out/target/product/infiniti/boot.img
fastboot flash init_boot     out/target/product/infiniti/init_boot.img
fastboot flash vendor_boot   out/target/product/infiniti/vendor_boot.img
fastboot flash dtbo          out/target/product/infiniti/dtbo.img
fastboot flash recovery      out/target/product/infiniti/recovery.img
fastboot flash super         /tmp/lineage_super_<date>.img
fastboot --disable-verity --disable-verification flash vbmeta vbmeta.img
fastboot --disable-verity --disable-verification flash vbmeta_system vbmeta_system.img
fastboot --disable-verity --disable-verification flash vbmeta_vendor vbmeta_vendor.img
```

The `--disable-verity --disable-verification` flags on vbmetas
are mandatory for source-built kernels (our kernel's SHA doesn't
match OEM-signed dm-verity tree). Without them the device refuses
to boot.

### Dynamic partitions (require fastbootd; NOT AVAILABLE on this device)

These live inside super:

| Partition | Notes |
|---|---|
| `system`, `system_ext`, `product` | OS userspace |
| `vendor`, `vendor_dlkm`, `odm` | Vendor blobs + DLKM |
| `system_dlkm` | GKI DLKM |

**These cannot be flashed individually via basic fastboot** on
canoe. The only way to update them is to flash the full
`super.img` (which contains all of them).

### Commands that DO NOT WORK on this device (avoid)

- `fastboot reboot fastboot` — supposed to reboot into fastbootd;
  on canoe this either does nothing or reboots into normal
  fastboot (the May 7 attempt confirmed). Do NOT rely on it.
- `fastboot flash <any dynamic-partition>` from basic fastboot —
  returns "Partition not found". Use `fastboot flash super
  <full-super.img>` instead.
- `fastboot wipe-super` — destructive and bottoms out at the
  May 7 failure mode (super metadata wiped but no way to repopulate
  without fastbootd). Avoid; flash full super.img instead.

## Method B flash procedure (recommended for first Phase 6 flash)

A staged, recoverable flash sequence:

1. **Pre-flash verification:**
   ```
   adb reboot bootloader
   fastboot getvar all 2>&1 | head -30
   ```
   Confirm: `current-slot:_a` (or `_b`), `unlocked:yes`, expected
   product name (`product:infiniti` or similar).

2. **Boot stack (physical partitions, basic fastboot):**
   ```
   fastboot flash boot         out/target/product/infiniti/boot.img
   fastboot flash init_boot    out/target/product/infiniti/init_boot.img
   fastboot flash vendor_boot  out/target/product/infiniti/vendor_boot.img
   fastboot flash dtbo         out/target/product/infiniti/dtbo.img
   ```

3. **vbmetas (verified-boot disable for source-built kernel):**
   ```
   fastboot --disable-verity --disable-verification \
     flash vbmeta out/target/product/infiniti/vbmeta.img
   fastboot --disable-verity --disable-verification \
     flash vbmeta_system out/target/product/infiniti/vbmeta_system.img
   fastboot --disable-verity --disable-verification \
     flash vbmeta_vendor out/target/product/infiniti/vbmeta_vendor.img
   ```

4. **super (single full-image flash — covers all dynamic partitions):**
   ```
   fastboot flash super out/target/product/infiniti/super.img
   ```

   This is THE step that requires the pre-built super.img. Without
   it, no path to dynamic-partition content works.

5. **Wipe user data (only if testing first-flash; skip if upgrading
   in place):**
   ```
   fastboot -w
   ```

6. **Reboot to OS:**
   ```
   fastboot reboot
   ```

7. **Post-boot triage:**
   - `adb logcat -d > /tmp/phase6_logcat_<date>.txt`
   - `adb shell dmesg > /tmp/phase6_dmesg_<date>.txt`
   - Functional spot-checks per `IMPLEMENTATION_PLAN.md` §9.3:
     launcher, display, touch, WiFi, cellular, audio, camera,
     fingerprint, NFC, GPS, charging, vibration, USB.
   - Diff dmesg against expected; identify modules that failed
     to load.

## Recovery procedures (in order of severity)

### Soft recovery — boot stack issue

If device boots into a broken state but ADB or fastboot still
works:

1. `adb reboot bootloader` (or hold Vol↓+Power for fastboot)
2. Reflash boot/init_boot/vendor_boot/dtbo from a known-good
   build (or stock images).
3. Reboot.

### Medium recovery — vbmeta or super issue

If the device bootloops at the verified-boot stage:

1. Boot to bootloader fastboot.
2. Reflash vbmetas with `--disable-verity --disable-verification`.
3. If super may have been corrupted, reflash `/tmp/stock_super.img`
   (the May 8 reconstruction) to restore OxygenOS as a baseline.
4. Reboot.

### Hard recovery — fastboot unrecoverable

EDL is the floor:

1. Boot to EDL mode (test point or `adb reboot edl` if available).
2. Use MSM Download Tool with the OnePlus 15 firmware package to
   reflash the full device.
3. Re-pair the device with stock first; verify it boots; then
   re-attempt Phase 6 once root cause of the prior failure is
   identified.

EDL is one-way and slow but always works. Do not attempt Phase 6
without EDL tooling already on hand.

## Pre-flash discipline checklist

Run through this checklist before issuing any `fastboot flash`
command:

- [ ] Complete `lineage_super_<date>.img` built and verified via
      `lpdump`
- [ ] `/tmp/stock_super.img` recovery floor still present and
      validated
- [ ] Recovery image cold-tested with a sideload of a NOOP zip
- [ ] MSM Download Tool + OnePlus 15 firmware mirrored locally;
      USB drivers installed; EDL cable / test point procedure
      confirmed
- [ ] Bootloader unlocked (`fastboot getvar unlocked` returns
      `yes`)
- [ ] Build's `boot.img` + `init_boot.img` + `vendor_boot.img` +
      `dtbo.img` + `recovery.img` + `vbmeta*.img` all present at
      expected paths
- [ ] `out/host/linux-x86/bin/lpmake` ready (verify with
      `--help`)
- [ ] Adequate USB cable + computer with stable connection
      (intermittent USB during a flash sequence is a top-10
      cause of flash failure)
- [ ] dmesg + logcat capture commands ready for post-boot triage

If any item is unchecked, stop and resolve before proceeding.

## Anti-patterns documented (do NOT do these)

- ❌ `fastboot wipe-super` followed by per-dynamic-partition
  flashes. **This is the May 7 failure mode.** fastbootd not
  available on canoe; super metadata gets wiped with no way to
  rebuild without lpmake + new super.img. Use `fastboot flash super
  <complete.img>` instead.
- ❌ `fastboot reboot fastboot` and waiting for fastbootd to
  appear. fastbootd is not available on canoe; the command
  either no-ops or returns to basic fastboot. Plan around basic
  fastboot only.
- ❌ Flashing source-built vbmetas without `--disable-verity
  --disable-verification`. Source kernel ≠ OEM-signed dm-verity
  tree; without the flags the device refuses to boot.
- ❌ Flashing without a recovery floor (`/tmp/stock_super.img`)
  on hand. If the source-built ROM is unbootable, the device
  is paperweight until you reconstruct stock super.img — which
  is what May 8 did, and which takes several hours.
- ❌ Flashing without EDL tooling on hand. If fastboot itself is
  broken, you need EDL to recover; "I'll get the tool when I need
  it" is the wrong sequencing.

## Phase 6 success criteria (Plan §9.3)

Per `IMPLEMENTATION_PLAN.md`. The MVB is "working" if all of:

- Device cold-boots to launcher
- Display + touch functional
- WiFi connects (may fail if WLAN modules don't load — that's
  expected Phase 7+ work)
- Cellular registers (may fail similarly)
- Audio plays through speaker
- Camera previews (may fail similarly)
- Fingerprint enrolls + unlocks (may fail similarly)
- NFC + GPS responsive
- Charging works (charger v2 ships as OEM prebuilt per 2F.3
  disposition; should work)
- Vibration + USB function

**Each "may fail" is acceptable for a first MVB flash** and
classifies that subsystem as Phase 7+ work. Hard-required for
Phase 6 success:
- Device boots to launcher
- Display + touch + ADB
- No bootloop / no dm-verity-blocked-boot

Anything beyond that is Phase 7+ scoping data, not Phase 6 blocker.

## After Phase 6

Update `~/android/mvb_boot_report.md` (or peer doc) with:
- Boot succeeded? Yes / No / partial
- Which modules failed to load (from dmesg)
- Functional spot-check results
- Subsystem categorization: load-bearing-for-boot /
  degraded-gracefully / not-relevant-on-this-device
- Phase 7+ priority list based on which load-fails are
  load-bearing

That data drives 2J / Wave 5 / dsp-kernel / spu-kernel / oplus-tail
prioritization. Phase 6 is the validator that converts Wave 2's
static prediction into runtime data.
