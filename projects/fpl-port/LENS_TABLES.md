# Lens correction tables on the fp L (found 2026-11-03)

Read from camera RAM with the SIGMA 45mm F2.8 DG DN | Contemporary mounted (r/o, `mem get`); raw dump in
`private/lensram_0xC3079000_45mmF2.8DGDN_20261103.bin` (not committed). Background on the fp:
`research/lens/notes/LENS_CALIBRATION.md`, `LENS_DISTORTION_TABLE.md`, `fpSup/gyro/distfit.inc.S`.

## Where

Same internal offsets as the fp's block, which sits 0x141C lower on the fp L (not the −0x140C the module's
named globals moved by: the lens-module code around fp 0xC0044C30..0xC0045B18 differs, and so did the
prediction).

| what | fp | fp L | format seen on the fp L |
|---|---|---|---|
| focal the data was measured at | 0xC307CDF0 | **0xC307B9D4** | u32 tenths: 450 |
| focus axis | 0xC307CE2C (+0x3C) | **0xC307BA10** (+0x3C) | **3 rows × 12 u32**, row stride 0x30; 2^24 / distance mm; then 0x7FFFFFFF |
| coefficient table | 0xC307D270 (+0x480) | **0xC307BE54** (+0x480) | **3 blocks × 12 nodes × 3 planes × 4 f64**: record 0x20, node 0x60, block 0x480; 108 records |

Axis (all three rows identical for this lens): 0, 3679, 14717, 22075, 33091, 40427, 47798, 51464, 55188,
62602, 71090, 76260 = ∞, 4.56 m, 1.14 m, 760, 507, 415, 351, 326, 304, 268, 236, 220 mm.
The fp research saw 5 nodes and 15 records with a LUMIX S 40mm. The node count comes from the lens.

## Verified against a DNG

Take A001_100 (FHD 23.976, same lens): the DNG's WarpRectilinear (3 planes) =
**block 0**, nodes 6–7, **t = 0.6227 for all three planes** (one focus position: ~335 mm), then each
coefficient rescaled for radius: **kr_j × s^(2j), s = 0.99356**. kr2 and kr3 then agree to ≤ 2×10⁻⁹ on every
plane, the fp research's precision. Blocks 1 and 2 do not fit (≈10⁻³).

## Not known yet (needed before the camera can write distortion on the fp L)

1. **Node count**: 12 here, 5 on the fp's lens. Where does the firmware keep it? (Look near the focal word
   at 0xC307B9D0 = 61189 / the 0xFFFF fill, or in DistConverter's code.) distfit.inc.S hard-codes 5.
2. **What blocks 1–2 are**: aperture? another correction? Which block does the camera pick, and when?
   (Repeat with another aperture and compare which block a DNG matches.)
3. **The radius reference**: s = 0.99356 for a 1936 × 1090 FHD frame. Which radius is the table normalised
   to? (The 16:9-vs-3:2 geometry gives 0.9547, so not simply the sensor's half-diagonal.) Check against
   DISTCONVERTER_MATH.md and with a second frame size.
4. **Whether the addresses stay put with another lens** (also open on the fp).
5. **The fp L's distfit**: it would need the node count, the block choice and the normalisation; the fp's
   version reads 5 nodes at fixed addresses.
