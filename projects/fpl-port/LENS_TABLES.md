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

## Run-time values: what the camera knows at the moment of a take (offline, 2026-11-03)

From the `lens` shell commands (`src/shell/src/cmd/xc_shellCmdLens.cpp`); table entries (name, help, handler):

| value | shell | getter fp | getter fp L |
|---|---|---|---|
| aperture, **APEX Av × 1024** (the firmware's own help: `setav (av=4096(AVx1024))`) | `lens getav` (handler fp L 0xC03F8408) | 0xC0362158 | **0xC0362370** (identical) |
| focus position | `lens getfpos` (handler 0xC03F6A58) | 0xC035FD48 | 0xC035FF60 |
| focus position → distance in mm | `lens cnvfdist` | 0xC035FE08 | 0xC0360020 |
| current focal length (zoom), tenths of a mm | — (what the DNG's FocalLength uses: producer fp L 0xC0364AA0, ÷10) | 0xC03629D8 | **0xC0362BF0** (identical) |

No `lens` command for the zoom position. The focal getter is a lens-object method (vtable +0xAC, fp L
0xC0330DE8): for the mount types other than 5 it returns word +0x18 of `[lens object +0xC] + 4`. The lens
object is at fp L 0xC343C5E0 (accessor 0xC032FEA8); live, that puts the current focal at **0xC347ED68**
(heap; read through the pointers, not as a fixed address).

**The lens singleton's +0x68 (the gyro's `O_LENS_FOCAL`) is not the current focal.** On the 28-70 it read
280 at every zoom setting, and +0x6C read 700: they are the **wide and tele ends**. On a prime both are the
one focal, which is why the fp code never noticed.

### Live check (fp L, SIGMA 28-70mm F2.8 DG DN, 2026-11-03)

| state | getav | getfpos | cnvfdist | singleton +0x68 | current focal (0xC347ED68) |
|---|---|---|---|---|---|
| start, F2.8, AF | 3072 (Av 3 = F2.8) | 3435 | 271 mm | 280 | — |
| F5.6 | 5120 (Av 5 = F5.6) | 3532 | 264 mm | 280 | — |
| MF, focused at infinity | 5120 | 0 | **2147483647** (0x7FFFFFFF) | 280 | — |
| zoom 50 mm | 5120 | 0 | 2147483647 | 280 (wide end) | **500** = 50.0 mm |
| zoom 70 mm | 5120 | 0 | 2147483647 | 280 (wide end; +0x6C = 700, tele end) | **700** = 70.0 mm |

Mount type (`[0xC347D97C + 0x24]`) read 11, so the method took the path above. Infinity is 0x7FFFFFFF on the
fp L; the fp's gyro code checks 0x07FFFFFF.

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
   derive s from the sensor facts instead of hard-coding it. **Found (2026-11-03):** the fp L image holds
   s's two halves as doubles: **21.49079172691411 at 0xC02D7D08** (one entry of a table of half-diagonals
   from 0xC02D7CE8: 18.35, 19.33, 15.64, 17.40, 21.49, 14.08 … mm) and **21.63 at 0xC0044528** (also
   0xC0042E24, 0xC0043F28). The lens module divides a stored half-diagonal by 21.63 (0xC0044374). The quotient
   is **0.993564111**, the fitted s to every digit the fits give. **A001_103 (4K F5.6) fitted s freely: 0.993564
   again**, a constant across FHD/4K and three apertures.
4. ~~Whether the addresses stay put with another lens~~: yes for the 28-70 (same F, same offsets).
7. ~~Zoom interpolation~~: **log focal** fits best. On A001_106 one zoom weight v = 0.71643 reproduces all four
   coefficients to 4e-7; with the focal the camera reports (500), log gives v 0.7157 → 1.2e-5, 1/f 1.98e-4,
   linear in mm 2.26e-4. One take only: a second take between zoom positions (e.g. 35 mm) would confirm it.
   The remaining 1.2e-5 would vanish at 50.006 mm, so the camera may know the zoom finer than tenths.
5. ~~The fp L's distfit~~: written (2026-11-03), see below.
6. ~~The current aperture, focus and zoom at run time~~: found and confirmed live (section above).

## The fp L's distfit (2026-11-03)

`fpSup/gyro/distfit.inc.S`, `#ifdef FPSUP_CAMERA_FPL`: a `pg_dist_kr` that reads the whole block, with the
sizes taken from the lens (Nz zoom positions, Na apertures, Nn nodes; the lists end at 0xFFFF / 0x7FFFFFFF /
0xFFFFFFFF and the counts must divide exactly). It uses the run-time getters above: current focal, getav,
getfpos → cnvfdist, where both 0x07FFFFFF and up and ≤ 0 mean infinity. It blends up to eight records: zoom
in log focal, then each zoom row's own apertures, then each row's own focus axis, all held at the ends. Then
kr_j × s^(2j) with s read from the two firmware doubles (`fwtarget.SENSOR['fpl']`, defines
`FPSUP_DIST_HALFDIAG_AT` / `FPSUP_DIST_REF_AT`). The fp keeps its own 5-node routine.

The focal: `gcsv_json.S j_lens` now asks the current-focal getter (fp 0xC03629D8, fp L 0xC0362BF0) and keeps
the singleton's +0x68 only as the fallback. On a zoom that was the wide end. This fixes the profile's focal
for zooms on both cameras, and `pg_dist_focal`'s zoom branch (b1a98fad) now gets the real focal.

`gyro/test_distfit.py FpLBlock` runs the assembled routine under unicorn against the fp L image and the two
lens dumps (skipped without `private/`). The getters are stubbed with each take's DNG values: focal, getav
nominal (3072 / 4096 / 5120) and the subject distance in mm.

| take | lens | worst coefficient error |
|---|---|---|
| A001_100 | 45mm F2.8 | 4.0e-8 |
| A001_101 | 45mm F4 | 4.2e-9 |
| A001_102 | 45mm F2.8 4K | 6.4e-8 |
| A001_103 | 45mm F5.6 4K | 4.8e-8 |
| A001_104 | 28-70 at 28, F2.8 | 2.2e-8 |
| A001_105 | 28-70 at 28, F5.6 | 1.4e-8 |
| A001_106 | 28-70 at 50, F2.8 | 1.2e-5 |

The 1e-8 level is the whole-mm subject distance (the DNG rounds it the way cnvfdist does). Mutations checked:
dropping the s scaling fails all seven; dropping the log blend fails A001_106. Also tested: infinity in both
spellings, and an empty or zeroed block is refused. Not yet run on the camera.
