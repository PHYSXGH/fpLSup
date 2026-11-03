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
7. **Zoom interpolation**: **linear in mm**, but with a focal **finer than the camera reports**. Three takes
   between zoom positions, each fitted by one weight for all four coefficients:
   A001_106 says 50.0 → v 0.71643 = (50.1 − 45.3)/6.7; A001_107 says 35.0 → v 0.63158 = (35.1 − 32.7)/3.8;
   A001_108 says 60.0 → v 0.50955 = (60.0 − 52.0)/15.7 (exact, 1.5e-7). The log blend tried first fitted
   A001_106 by chance and was wrong for 35 and 60 mm. **Still open: where the finer focal is** (the DNG
   FocalLength getter returns 350 / 500). No firmware code addresses the block directly (it is reached
   through a pointer).

   Live search (2026-11-03, 28-70 at 28.2 then 35.0, read-only): snapshots of the lens module RAM
   (0xC3079000..F), the lens object (0xC347ED00, 1 KB), the singleton and 0xC347D97C, diffed. Words that move
   with zoom: obj +0x50 (3852 → 5413; 22913 at 50 mm), +0x70 (191 → 217; 299), +0x74 (108 → 97; 82), +0x78,
   plus per-zoom tables at 0xC307A3B0..0xC307A568 (correction curves for the current zoom; no doubles).
   None of them, against any 9-entry table in the lens RAM, gives the takes' weights, and no value between
   35.01 and 35.09 (hundredths, thousandths, f32, f64) is there. The fitted focals are 35.100 ± 0.002,
   50.100 and 60.000: exactly one tenth or none, which suggests two roundings of a finer value (the getter
   truncating, the correction rounding) rather than noise. The block builders (fp L 0xC00508A8,
   0xC0051628) fill the zoom list from u16 tenths in the lens data, so the list itself is not finer. The
   reader is upstream of the OpcodeList3 writer (fp 0xC02CE918, which serialises finished doubles).

   Cost: a 0.1 mm focal error is 1.1 px of shape at the 4K corner at 35 mm, 2.0 px at worst (29 mm, where
   the distortion changes fastest), plus a focal scale of ≤ 6e-5.
5. ~~The fp L's distfit~~: written (2026-11-03), see below.
6. ~~The current aperture, focus and zoom at run time~~: found and confirmed live (section above).

## The fp L's distfit (2026-11-03)

`fpSup/gyro/distfit.inc.S`, `#ifdef FPSUP_CAMERA_FPL`: a `pg_dist_kr` that reads the whole block, with the
sizes taken from the lens (Nz zoom positions, Na apertures, Nn nodes; the lists end at 0xFFFF / 0x7FFFFFFF /
0xFFFFFFFF and the counts must divide exactly). It uses the run-time getters above: current focal, getav,
getfpos → cnvfdist, where both 0x07FFFFFF and up and ≤ 0 mean infinity. It blends up to eight records: zoom
linearly in mm, then each zoom row's own apertures, then each row's own focus axis, all held at the ends. Then
kr_j × s^(2j) with s read from the two firmware doubles (`fwtarget.SENSOR['fpl']`, defines
`FPSUP_DIST_HALFDIAG_AT` / `FPSUP_DIST_REF_AT`). The fp keeps its own 5-node routine.

The focal: `gcsv_json.S j_lens` now asks the current-focal getter (fp 0xC03629D8, fp L 0xC0362BF0) and keeps
the singleton's +0x68 only as the fallback. On a zoom that was the wide end. This fixes the profile's focal
for zooms on both cameras, and `pg_dist_focal`'s zoom branch (b1a98fad) now gets the real focal.

`gyro/test_distfit.py FpLBlock` runs the assembled routine under unicorn against the fp L image and the two
lens dumps (skipped without `private/`), with the getters stubbed to each take's values: getav nominal
(3072 / 3413 / 4096 / 5120 for F2.8 / 3.2 / 4 / 5.6), subject distance in mm, and **the focal the camera
blended with** (501 and 351 where the camera reports 500 and 350; see item 7).

| take | lens | worst coefficient error |
|---|---|---|
| A001_100 | 45mm F2.8 | 4.0e-8 |
| A001_101 | 45mm F4 | 4.2e-9 |
| A001_102 | 45mm F2.8 4K | 6.4e-8 |
| A001_103 | 45mm F5.6 4K | 4.8e-8 |
| A001_104 | 28-70 at 28, F2.8 | 2.2e-8 |
| A001_105 | 28-70 at 28, F5.6 | 1.4e-8 |
| A001_106 | 28-70 at "50" (50.1), F2.8 | 1.4e-7 |
| A001_107 | 28-70 at "35" (35.1), F5.6, ∞ | 1.7e-7 |
| A001_108 | 28-70 at 60, F5.6, ∞ | 1.5e-7 |
| A001_109 | 45mm F3.2, ∞ | 0 |

### On the camera (card `20261103-fast3-gyro-debug-noptp-dist`, 2026-11-03)

Takes A001_107 (35), A001_108 (60), A001_109 (45mm), 4K 23.976, recorded with the log-blend build:

- focal_length in the .json: **35.000, 60.000, 45.000** (the old code wrote 28.0 for every zoom setting).
- 45mm: the .json's three coefficients equal the fit to the take's own DNG to **7e-7**, so the camera ran the
  routine and got the camera's coefficients.
- Zooms: 5e-3 (35 mm) and 1.8e-2 (60 mm) off in Gyroflow's coefficients. That was the log blend, now
  replaced. With linear-in-mm and the reported focal, 60 mm is exact; 35 mm stays off by 8e-4 in the lens
  coefficients (≈ 1 px radially at the 4K corner, mostly in kr0, i.e. the focal scale) until the finer focal
  is found.

Rebuilt with the linear blend: card `20261103-fast3-gyro-debug-noptp-dist2`.

### On the camera, card dist2 (linear blend), 2026-11-03

Takes A001_110 (30 mm), A001_111 (28), A001_112 (70), A001_113 (42), 28-70 at F5.6, focus ∞, 4K. In each,
the model at the **reported** focal reproduces the DNG's coefficients exactly (≤ 2e-18): 30.000 and 42.000
between zoom positions, 28 and 70 held at 28.9 and 67.7. The +0.1 mm of A001_106/107 did not recur here.

In pixels at the 4K frame (whole radius range):

| take | .json vs the fit of its own DNG | .json model vs the DNG's warp |
|---|---|---|
| A001_110, 30 mm | 0.027 | 0.54 |
| A001_111, 28 mm | 0.000 | 0.70 |
| A001_112, 70 mm | 0.017 | 0.015 |
| A001_113, 42 mm | 0.000 | 0.05 |
| A001_109, 45mm (dist build) | 0.000 | 0.11 |
| A001_107 / 108 (log-blend build) | 0.61 / 0.58 | 0.61 / 0.56 |

The first column checks the camera's run: it computed the camera's own coefficients. The second is the
limit of Gyroflow's three-coefficient fit (k4 written as 0): up to 0.7 px at the wide end of the 28-70.

### Four fitted coefficients (2026-11-03)

`pg_dist_fit` now fits k1..k4 by collocation at four radii (0.40, 0.70, 0.90, 1.00 of the corner) and
solves the 4×4 system with Gaussian elimination (`pg_solve4`). It used to fit k1..k3 at 0.55 / 0.85 / 1.00
and write k4 as 0.0. This is shared code, so the fp gets it too. Worst error over the whole frame against
each take's own DNG warp (Python, chosen radii vs alternatives):

| radii | worst over 14 takes | 28-70 at 28 mm |
|---|---|---|
| 3: 0.55 0.85 1 (old) | 0.70 px | 0.70 |
| **4: 0.40 0.70 0.90 1** | **0.086 px** | 0.086 |
| 4: 0.35 0.65 0.88 1 | 0.107 | 0.107 |
| 4: 0.50 0.75 0.92 1 | 0.107 | 0.107 |
| 4: 0.30 0.60 0.85 1 | 0.173 | 0.173 |

`test_distfit.py FitOnArm` runs the assembled fit under unicorn on the 14 takes and the LUMIX nodes: the
result matches the Python mirror to 1e-9 (1.7e-10 seen), and the profile is within 0.1 px of the DNG warp
everywhere. Mutations (no back substitution, a moved radius) fail it. Removing the pivot choice does not:
this matrix solves the same either way, though every fit does swap rows. Card `…-dist3`.
