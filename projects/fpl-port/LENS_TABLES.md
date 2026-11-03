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

## Three more takes (2026-11-03): focus × aperture

`tools/match_dng_lens.py` against the same dump:

| take | frame | aperture | fit | result |
|---|---|---|---|---|
| A001_100 | FHD 1936 × 1090 | F2.8 | block 0, nodes 6–7, t 0.62275 | exact (1.7e-16), s = 0.993564 |
| A001_102 | 4K 3856 × 2170 | F2.8 | block 0, nodes 4–5, t 0.21442 | exact (1.3e-16), **s = 0.993564** |
| A001_101 | FHD 1936 × 1090 | F4 | blocks 0–1, u 0.8655 × nodes 5–6, t 0.7513 | exact (4e-9) |
| A001_103 | 4K 3856 × 2170 | F5.6 | blocks 1–2, u 0.455078 × nodes 8–9, t 0.496223, **s fitted free: 0.993564** | exact (5.6e-16) |

- **s is a constant (0.993564)**: the same for FHD and 4K (different crops, 9552 vs 8208 columns). It is
  not a frame-size normalisation. Its source is still to find (a constant of this lens or of the camera).
- **The blocks are apertures**, interpolated linearly: the table is 2D, focus distance × aperture.
- Block apertures, very likely: **3504, 4188, 6236** at focal+0x3CC (0xC307BDA0, three u32, nothing else
  in the gap). F4 between blocks 0 and 1 at u 0.8655 → 3504 + 0.8655 × 684 = **4096.0**. That is F4 in two
  readings: **F × 1024** (blocks F3.42 / F4.09 / F6.09) or **APEX Av × 1024** (≈F3.3 / F4.1 / F8.2). F2.8
  takes are below block 0 and clamp to it in both. **A take at F5.6 separates them**: F×1024 predicts 5734,
  Av×1024 predicts 5094.
- Node count: each axis row holds 12 (0x30 bytes); this lens fills all 12. Likely rule: entries before
  0x7FFFFFFF. To confirm with a lens with fewer nodes.

## Second lens: SIGMA 28-70mm F2.8 DG DN (zoom), 2026-11-03

Same block, same address, one more dimension. Dumps (not committed):
`private/lensram_0xC3079000-0xC3084000_28-70mm_at28_20261103.bin` (read at 28 mm).
**What the block is** (`tools/lens_block.py` decodes it), from F = 0xC307B9D4:

| offset | content | 45mm prime | 28-70 zoom |
|---|---|---|---|
| +0x000 | zoom positions, u32 tenths of mm, until 0xFFFF (up to 15) | 1: 45.0 | **9: 28.9 32.7 36.5 38.6 40.9 43.0 45.3 52.0 67.7** |
| +0x03C | focus axis, one row per zoom × aperture, Nn u32 each | 3 × 12 | 27 × 8 (last node per zoom: close focus 170 → 338 mm) |
| +0x3CC | apertures, Av × 1024, per zoom × aperture | 3 | 27 (≈ Av 3.09 / 4.07 / 5.06, drifting slightly with zoom) |
| +0x480 | [zoom][aperture][node][plane] × 4 f64 | 108 records | **648** = 9 × 3 × 8 × 3 |

Counts: Nz = entries before 0xFFFF in the zoom list; Na = aperture entries / Nz; Nn = axis entries before the
fill / (Nz × Na). Both lenses fit. **"The focal the data was measured at" (fp DIST_FOCAL, distfit's
pg_dist_focal) is just the first zoom position**: with a zoom it is always the wide end. Fix in the new code
(and worth noting for the fp).

Model (`lens_block.py` + a per-row fit): one focus distance and one Av per take; in each zoom row, t from
that row's own axis and u from its own apertures (both clamped); blend the two zoom rows linearly in focal
length; then kr_j × s^(2j).

| take | DNG | fit | error |
|---|---|---|---|
| A001_104 | 28 mm F2.8, 4K | 28.000 mm (below 28.9 → clamped), Av 2.9709 (= F2.8, clamped to block 0), s 0.993564 | 2.2e-14 |
| A001_105 | 28 mm F5.6, 4K | 28.000 mm, **Av 5.0000**, s 0.993564 | 6.3e-14 |
| A001_106 | 50 mm F2.8, 4K | 50.05 mm, Av 2.9709, s 0.99324 | **2.9e-5, not exact** |

Between zoom positions the camera blends in some way not reproduced yet (not linear in mm on the
coefficients, or after a conversion). It is **sub-pixel**: ≤ 0.26 px at the corners of a 4K frame worst case
(~0.06 px realistic). Good enough for Gyroflow; exactness open.

## Not known yet (needed before the camera can write distortion on the fp L)

1. ~~Node count~~: derived from the data (see the 28-70 section). distfit.inc.S hard-codes 5.
2. ~~What blocks 1–2 are~~: apertures, **in APEX Av × 1024** (settled by A001_103: 4188 + 0.455078 × 2048 =
   **5120.0 = Av 5.0** = F5.657, the true "F5.6"; F×1024 would be 5734; F4 gave 4096 = Av 4.0). The blocks are
   Av 3.42 / 4.09 / 6.09 (≈ F3.3 / F4.1 / F8.2). F2.8 (Av 2.97) is below block 0 and clamps to it, which is
   why both F2.8 takes matched block 0 exactly. The camera's correction for this lens is fully described:
   interpolate focus along the axis, aperture (Av × 1024) between blocks with clamping, then kr_j × s^(2j).
3. ~~The radius reference~~: a constant s = 0.993564, not frame geometry (above). **Lead:** s ≈ the still
   image's half-diagonal in mm / the 36 × 24 mm half-diagonal (21.633 mm): 9520 × 6328 px at 3.76 µm gives
   21.491 mm → 0.99341; s exactly needs a pitch of 3.76057 µm (2×10⁻⁵ off at 3.76). So the lens data are
   likely normalised to the full-frame image circle and the camera rescales to its own sensor, the same for
   every crop. A crop-dependent cap cannot remove s (identical for FHD and 4K). If confirmed, the code can
   derive s from the sensor facts instead of hard-coding it. **A001_103 (4K F5.6) fitted s freely: 0.993564
   again**, a constant across FHD/4K and three apertures.
4. ~~Whether the addresses stay put with another lens~~: yes for the 28-70 (same F, same offsets).
7. **Zoom interpolation** between zoom positions: sub-pixel with linear-in-mm, not exact (A001_106).
5. **The fp L's distfit**: it would need the node count, the block choice and the normalisation; the fp's
   version reads 5 nodes at fixed addresses.
6. **The current aperture and focus at run time**, from the camera (the fp uses F_FOCUS_POS / F_FOCUS_DIST
   for focus; an aperture getter is still to find).
