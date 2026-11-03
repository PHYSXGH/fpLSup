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

- **s is a constant (0.993564)**: the same for FHD and 4K. Its source is still to find (a constant of this
  lens or of the camera). *Corrected 2026-11-03:* this said the two cover different crops (9552 vs 8208
  columns). They do not: the 4K takes are mode 161 (9568 × 5382, 1:1) and the FHD takes mode 173
  (3184 × 1796, bin 3 = 9552 columns), the same width within 16 columns (`imx455_modes.csv`). So these
  takes cannot tell a frame-size normalisation from a constant; the firmware's own two doubles (item 3)
  are what settle it.
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
   every crop. (FHD and 4K agreeing says little here: both cover the full width, see above.) If confirmed, the code can
   derive s from the sensor facts instead of hard-coding it. **Found (2026-11-03):** the fp L image holds
   s's two halves as doubles: **21.49079172691411 at 0xC02D7D08** (one entry of a table of half-diagonals
   from 0xC02D7CE8: 18.35, 19.33, 15.64, 17.40, 21.49, 14.08 … mm) and **21.63 at 0xC0044528** (also
   0xC0042E24, 0xC0043F28). The lens module divides a stored half-diagonal by 21.63 (0xC0044374). The quotient
   is **0.993564111**, the fitted s to every digit the fits give. **A001_103 (4K F5.6) fitted s freely: 0.993564
   again**, a constant across FHD/4K (both full width) and three apertures. Not yet checked on a cropped
   mode (e.g. 184–187 at 8208 columns, or the 1.5× crop at 6288); a take in one would show whether s
   stays put when the frame covers less of the sensor.
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

### dist3 on the camera, and a zoom sweep (2026-11-03)

**A001_114 (28 mm) and A001_115 (30 mm), 4K, F5.6, MF ~0.33 m, card dist3.** Each .json has four fitted
coefficients. They equal the fit of the model at the reported focal and a focus of **329 mm / 330 mm**
**exactly (0.000 px)**; the DNGs record 331 mm all take long. So the camera computed the right thing from
the focus it read at take start, 1–2 mm off the DNG's figure. At ~330 mm one millimetre of focus moves
the 28 mm profile by ~0.07 px at the 4K corner, so the .json is 0.14 / 0.09 px off the DNG's warp, all of
it from that focus reading. A001_116 (the sweep's .json, FHD, 28 mm): 0.07 px.

**A001_116, zoom sweep 28 → 70 → 28, FHD, F5.6, MF, 237 frames.** The DNG's FocalLength and coefficients
change every frame (145 distinct focals in tenths). The subject distance drifts 327–331 mm with zoom.
Per frame, the search was over focal (0.01 mm steps, ±3 mm) and focus (0.1 mm steps):
- 23 of 152 frames between zoom positions fit one (focal, focus) point exactly. Their focal against the
  reported one: **+0.00 in 15, +0.10 in 6, −0.10 in 2**. The tenth goes both ways, so it is not a fixed
  offset.
- The other 129 fit no single point (residual 1e-6 … 2e-3, growing with zoom speed). That looks like the
  camera mixing two lens states (zoom and focus read at different moments, or blended over time): a mix
  of two states with different focus is not a point of the bilinear model.

Reading: while the lens is still, the camera's correction uses the reported focal, or one tenth either
side when the lens sits near a tenth's edge. During zooming it mixes states. The gyro profile is computed
once at take start from the getters, so it carries at most that tenth (≤ ~1–2 px at the 4K corner on the
wide end, usually less). No finer zoom value was found. Left as is.

## Crop: the video crop menu, and what s really is (2026-11-03)

Clips A001_117–120, 28-70 at 28 mm, F5.6, ∞, 4K 23.976, crop menu 1.0 / 1.53 / 2.0 / 2.5×:

| clip | menu | sensor mode | s from the DNG | camera crop (s ratio) | DNG FocalPlaneXResolution |
|---|---|---|---|---|---|
| A001_117 | 1.0× | 161 (9568 read) | 0.993564 | 1.0000 | 2724.83 |
| A001_118 | 1.53× | **187** (8208 read) | 0.651063 | 1.5261 | 4157.12 (× 1.52564) |
| A001_119 | 2.0× | **187** | 0.497554 | 1.9969 | 5440.53 (× 1.99665) |
| A001_120 | 2.5× | **187** | 0.400743 | 2.4793 | 6755.32 (× 2.47917) |

Each DNG is the block at the lens state × s^(2j) exactly (≤ 1e-18) with **s = frame half-diagonal / 21.63**.
So s is not a constant: the earlier takes were all full width. The crops past 1.53× are digital: mode 187
reads 8208 columns for all three.

The camera's crop steps: RAM table 0xC2F28BB4 (filled at boot by fp L 0xC02D7BC0 from the doubles at
0xC02D7CE8), 24 records of 24 bytes: u32 crop×100, u32 100, u32 width, u32 height, f64 half-diagonal mm.
1.00× 9520×6328 21.4908 … 1.53× 6240×4144 14.0825 … 2.00× 4768×3168 10.7621 … 2.48× (menu "2.5") 3840×2552
8.6681 … 3.18× 2992×1992 6.7576; half-diagonal = diagonal/2 × 3.76 µm. **The current one** is at
**0xC308EA60** (object 0xC308A670, FUN_c00530f0, +0x4268 via vt+0x3C, +0xC via vt+0x18, +0x17C; the lens
module copies it at 0xC00442A8 and divides its half-diagonal by 21.63 at 0xC0044374). Read live: 2.48 →
1.00 → 1.53× followed the menu.

The DNG's FocalPlaneXResolution scales by 9520 / record width exactly, so in a crop the frame covers the
record's width of the sensor: 6240 / 4768 / 3840 columns, not mode 187's 8208.

**The profile before the fix** used mode 187's 8208 for all three: crop 1.159 and focal 3496 px at 28 mm,
where the camera's numbers give ~4577 / 5989 / 7436 px (31–113 % off), and the full-frame s.

**Fixed (fp L, `FPSUP_CROP_RECORD_AT`):** `gcsv_json.S j_crop_cols`: above 1.00× the covered width is the
record's (crop factor and focal); `distfit.inc.S`: s = record half-diagonal / 21.63 (the firmware's 1.00×
double if the record looks wrong). 1.00× is unchanged. Tests: `FpLBlock` (A001_117–120 exact, 0.0) and
`CropProfile` (focal ratio against the DNGs' FocalPlaneXResolution within 5e-4); mutations of either part
fail them. Card `…-dist4`.

**For the focal cap (`FOCAL_CAP.md`):** at 1.00× the camera's own record is the still area, 9520 wide, and the
crop ratios in the DNGs come out exactly against 9520 (9520/6240 = 1.52564, the FocalPlaneXResolution
ratio), not against 9568 or 9552. The camera's optics math treats the full-width video frame as the
9520-column still image, i.e. it caps. The profile still leaves 1.00× uncapped (your choice, pending the
test).

### In-between crop steps (zoom step "normal"), card dist4, 2026-11-03

All 24 records (1.00 … 3.18×) are menu steps; "skip" visits only some (1.53, 2.00, 2.48). Clips at 28 mm,
F5.6, ∞, 4K 23.976:

| clip | step | sensor mode | s: DNG vs record | DNG = block × record s | FocalPlaneXRes / 1.0× vs 9520 / width | .json vs DNG warp |
|---|---|---|---|---|---|---|
| A001_121 | 1.05× (9024) | **161** | 0.941880 = 0.941880 | 7.7e-15 | 1.05496 = 1.05496 | 0.050 px |
| A001_122 | 1.17× (8128) | **161** | 0.848155 = 0.848155 | 6.4e-14 | 1.17126 = 1.17126 | 0.018 px |
| A001_123 | 1.37× (6928) | **187** | 0.723188 = 0.723188 | 1.5e-13 | 1.37414 = 1.37413 | 0.004 px |

The record rules every step, whichever sensor mode is underneath (1.17× is narrower than mode 187's 8208
columns and still reads mode 161). The profile's crop factor, focal and distortion followed it on the
camera. The one inconsistency left is 1.00×: the profile uses mode 161's 9568 columns (uncapped), the camera
9520, so the profile's focal at 1.05× / 1.00× is 9568 / 9024 = 1.0603 where the camera's is 1.0550.
**Resolved the same day:** the fp L caps at 9520 again (`FOCAL_CAP.md`), so 1.00× → 1.05× is 9520 / 9024 =
1.05496 like the camera. Test `FullFrameWidth`. Card `…-dist5`.

### dist5 on the camera (2026-11-03)

A001_124, 1.0×, 28 mm F5.6 ∞, 4K: focal 3014.368 px = 3856 × 28 / 35.8 × kr0 (0.999504) exactly; the step to
the 1.05× clip (A001_121, 3180.052) is 1.05496, the camera's FocalPlaneXResolution ratio 2874.60 / 2724.83 to
five places. Distortion: 0.084 px from the DNG's warp over the whole frame.
