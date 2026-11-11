# fp L port: open issues

Things to fix or check. The history and the evidence for each are in RESCUSTOM_PORT.md (res-custom)
and LOADER_V4.md (loader); each entry names the card it was seen on. Newest first within a section.

## RES-Custom

1. **The custom resolution names are not loaded at boot** (the user, 2026-11-06, card r19).
   Reported as a separate issue; details still to collect (which names: the menu row, the Quick Set
   tile, the live-view label; and whether they appear after a resolution change or a menu visit).
   - Card r30 (2026-11-11, the user; noted, not acted on): after boot the **live-view screen's
     resolution name reads "UHD"** although the custom resolution set before is still selected
     (W48K: the view is letterboxed, so the row is live). Going into the menu and changing the custom
     resolution fixes the name. So the live-view label is not re-published at boot (the core's lvpub
     re-post / LV_Resolution) until a selection change.

2. **UHDC: the live view while recording is squeezed horizontally** -- **fixed (card r29, 2026-11-06)**:
   the canvas +0xD8 / +0xE0 window, see the end of this entry.
   Recording itself is fine (A001_168 .. 172). The preview seems to take the whole 6288-wide read
   instead of the middle 3856 columns (a 1.63x squeeze matches what the user sees).
   - r17: p2061's preview (1288x724): flashing pink garbage.
   - r18: the stock UHD crop step's fields (p2079: +0x0C/+0x10 1296x730, +0xA4 42, +0xD8/+0xE0
     1296/2190): froze on a garbage frame (+0xE0 2190 is taller than the read's 2174 lines).
   - r19: U48K's preview 1616x908 / 1608x904: a flashing band ~30-50 px at the top and bottom,
     the picture squeezed.
   - r20, tuned live (RAM, between short recordings, the user watching):

     | test | change | result |
     |---|---|---|
     | 1 | +0xA4 = 42 | no visible change |
     | 2 | + +0xD8 = 1616, +0xE0 = 2174 | **bands gone**, still squeezed |
     | 3 | +0xD8 = 3856 | froze, pink garbage: +0xD8 must be the preview's width |
     | 4 | +0xD0/+0xD4 = 2443/2447 (+0x60/+0x64 kept 1023) | froze, pink lines |
     | 5 | +0x58 = 0 (stock crop steps 1, FHD from this read p2100 0) | more squeezed: +0x58 changes how the preview takes the read |

   - Card r21 bakes in test 2 (+0xA4 42, +0xD8 1616, +0xE0 2174): a stable live view, squeezed.
   - UHDC's effective canvas (p2061 + its pairs) now equals stock's 1:1 crop step p2079 in every
     field but the read size, the preview size and +0xD8/+0xE0 -- so the preview takes its source
     area from the read in a way the crop steps' 8208x4320 read happens to suit.
   - Static trace (2026-11-06): searching for functions that read +0x58 with +0xD8/+0xE0 (on the
     canvas, or on the profile object at +0xB4/+0x134/+0x13C) found only bulk copies
     (FUN_c02d8c10 / c02d9008, settings snapshots) and a still-capture routine (FUN_c037b500).
     The canvas is copied into other structures before the preview is set up, so the consumer
     does not use these offsets: a static search by offset does not reach it.
   - Dynamic diff (2026-11-06, tools/probe/recdump.py: RAM dumped through the uncached alias the
     moment the movie-recording flag 0xC347ED4C+0x157 sets): UHDC (card r21) vs stock UHD in Crop
     Mode's largest step (p2079-like, 1:1 3856x2170 from 8208x4320, correct preview). The recording
     set-up at 0xC31DD95C.. holds +0xD0/+0xD4, +0xD8/+0xE0, the preview sizes, the read size --
     identical layout, our values -- and two words that differ in kind:

     | | UHDC | stock crop |
     |---|---|---|
     | 0xC31DD95C | -3232 = 6288 - 9520 | 4368 = 8208 - 3840 |
     | 0xC31DD960 | -4154 = 2174 - 6328 | 1768 = 4320 - 2552 |

     The subtracted size is a still-photo size from the table at 0xC0B85048.. ({size class 0..4,
     aspect 1..8, w, h}; FUN_c02df5d0 / c02df7e0): class 3 3:2 (3840x2552) for the stock crop step,
     class 0 3:2 (9520x6328) for UHDC -- by the crop factor (9520 / 2.48 = 3840). UHDC is a 2.48x
     crop the camera believes is 1.00, so the preview window offsets go negative: the squeeze.
   - Next: the core writes a format's declared crop factor (UHDC: 248) into the recording request
     (+0x48, crop x 100, which the picker hooks already read) after picking the entry, so the
     firmware derives class 3 as for its own crop step. A hypothesis: to test on the camera.
   - Built (card r22, `cards/20261106-rescustom-uhdccropf-r22`): RCD section SEC_CROP = 14
     (required, u32 crop x 100, 100..1000; fp L only), ROW.CROP100 (+0x7C, fp L rows 0x80); the
     pick shims pass the request (r6) and ogc_pick writes the row's factor to +0x48 after a pick.
     UHDC declares 248. Core `2d6f1198…`, UHDC.RCD `a107d75f…`; the other formats unchanged; fp
     core 7b575c72. Tests: decoding, an emulated boot accepting UHDC.RCD (mutation: a broken
     section check refuses it).
   - **r22 on the camera (2026-11-06): no garbage, still squeezed;** recording unchanged
     (A001_185 .. 187). Next: dump at record again (recdump.py) -- if 0xC31DD95C/960 now read
     6288 - 3840 / ..., the factor reaches the computation and something else is off; if still
     -3232 / -4154, the size class does not come from the request's +0x48 (or is taken earlier).
   - Dump with r22: the offsets are now **2448 / -378** (6288 - 3840, 2174 - 2552): the crop factor
     does reach the computation. The subtracted size looks like the full photo size divided by the
     crop factor (9520 / 2.48 = 3840, 6328 / 2.48 = 2552), always 3:2. With the camera's still
     aspect set to 16:9: unchanged (2448 / -378), still squeezed -- the still setting does not feed it.
   - The user: things look about **1.2x too tall**. 2552 / 2174 = 1.17: the preview seems to take the
     2174 lines it gets as a 2552-line (3:2) window and stretch them. No crop factor fits both axes
     (3840 wide needs 2.48; 2174 lines needs >= 2.91, i.e. 3271 wide).
   - **Parked (the user, 2026-11-06).** Card r22 stays (recording unchanged, saner offsets). Ideas
     for later: find where the window height is taken from (the 2552) and give it the read's height;
     or a UHDC read that is 3:2-shaped around the crop.
   - **Resumed 2026-11-06 (cards r26/r27), the window offsets ruled out:**
     - The still-size table's entries are {w, h, class, aspect}; the classes are fixed crop factors
       (1.00, 1.53, 2.00, 2.48, 4.96). r27's UHDC.RCD with crop 2.93 (`8b6de09f`): not a class, the
       camera fell back to 1.00 (offsets -3232 / -4154 again); still squeezed. Class 3 has a 16:9
       entry of exactly 3840x2160; 2.48 picks its 3:2 entry (3840x2552).
     - The offsets are globals: `0xC01D4CD0` computes [0xC31DD95C] = read - window (window from
       `0xC015D100`) once at record start when [0xC31DD958] == 1; their one reader, `0xC01BE5A6`,
       adds them to two sizes right away (the getter `0xC01D4E40`).
     - Camera, RAM only (tools/probe/winpoke.py, recdump.py `quick`): offsets overwritten with
       2448 / 14 from +0.2 s for a whole 7 s take -- no change; [C31DD958] cleared before a take --
       the firmware sets it again at record start; the setter patched in RAM (`0xC01D4C98`
       movs r0,#1 -> #0) so the offsets stayed 0 / 0 for a whole take -- **no change**. The squeeze
       does not come from this path. Patch undone.
     - UHDC is the only RES-Custom format whose raster (3856x2170) is smaller than its read
       (6288x2174): next suspect, the preview scaling the whole read instead of the cropped raster.
     - Takes at 59.94 on SD stop after ~1 s (status: RAW error), 23.98 with Lossless ON ~7 s.
   - **The sensor read ruled out too (2026-11-06, RAM only, tools/probe/sensorwin.py):** the
     user sees the picture get ~1.6x narrower the moment recording starts. The IMX455 register
     record (0x460 B per mode, REGDESC 0xC0B98DE8) holds the read width at +0xB0/+0xB4 (and
     +0xB8/+0xBC) = width + 16, low / high byte; rows read at +0x24/+0x28, first row at
     +0x1C/+0x20; +0x10 is 16 / 32 for the 8224 / 6304 windows. RES-Custom clones mode 196's record
     at record start. With the record, mode 196's size rows (0xC0B93338..), its row in the 0x3C-byte
     table at 0xC0BB33xx (6287 / 6287 / 6288) and RES-Custom's copies set to a 3872-wide read, UHDC
     recorded 3856x2170 from a left-aligned 3872 read (A001_210 against A001_209, same scene: same
     scale, colours right, framing shifted) -- **and the live view was squeezed exactly as before**.
     Without the 0xC0BB33xx row: pink live view, right third black. +0x10 = 52: pink, right third
     black. So the ~1.6x does not come from the read's width or shape.
   - ~1.6 is close to 5/3, live view's own 3x5 binning (mode 9). The record-start canvas copy has
     binning 1.0 / 1.0 (+0xFC / +0x100) for UHDC and the stock crop step alike (live view: 3 / 5),
     but the display may keep live view's aspect compensation. U48K, whose recording view is right,
     sets +0xFC / +0x100 / +0x104 explicitly; UHDC inherits p2061's (+0x104 = 0).
   - Card r28 (`cards/20261106-uhdcbin1-r28`, UHDC.RCD `6483bd36` = r26's crop 2.48 + canvas
     +0xFC / +0x100 / +0x104 = 1.0f): **still ~1.6x narrower when recording starts**; no tint, the
     whole picture. Binning fields ruled out. (r28 stays on the card: as good as r26.)
   - Ruled out so far: the crop factor, the window offsets (and their flag), the sensor read's
     width and shape, the canvas binning fields. Next: diff U48K (right) against UHDC (squeezed)
     -- both p2061-based with the same 1616x908 preview -- in the canvas fields UHDC does not set
     (U48K: raster +0x00/+0x04, active +0x24/+0x2C, +0xDC/+0xE4) and in RES-Custom's live-view
     pairing; a record-start dump of U48K is the missing reference.
   - **Found: the live view's box (2026-11-06, `recdump.py early`, same boot U48K / UHDC):** the
     globals at 0xC31DBF30.. hold the box the recording live view is drawn into: +0x10/+0x14
     (0xC31DBF40/44) = U48K 897 x 1586 (1.77:1), UHDC 710 x 2088 (**2.94:1**: 1.66x against 16:9 =
     the squeeze). Copied by `0xC01BEE18` from the display-path table 0xC302439C (0x58 per path,
     +0x08/+0x0C), which `0xC01BA608` fills: box = ((read / binning) - 1) * 1024 / scale + 1 minus a
     margin (c014e370), with binning +0x4E0/+0x4E4 = 3/3 and scale +0x94/+0x98 (>= 0x400) of the
     display object -- UHDC 6288/3 - 8 = 2088, 2174/3 - 14 = 710; the stock crop step 8208x4320 ->
     2720x1426 (1.91:1, close to 16:9: its live view also shows the whole read). The read comes from
     `0xC01D0BC0` / `0xC01D0BE0` (or `0xC0188F20`), not from the tables sensorwin.py changed -- which
     is why the narrowed read left the box alone.
   - The function has a crop: when object +0x4C4 == 1 the width / height are scaled by +0x4C8 /
     +0x4CC (/ 100) and centred with +0x4D0 / +0x4D4. The object (0xC31F6610 on this boot: +0x4C0 1,
     +0x4C4 0, +0x4C8/+0x4CC 3840/2160, +0x4E0/+0x4E4 3/3) is refilled at record start by
     `0xC01C7A5C` from getters on the settings block 0xC31DDCD8, whose +0x4C4.. `0xC01D22E0` reads
     from `0xC017E0D8(1, ...)` -- image-processor registers (0x30182110..). A RAM write to the object
     before a take is overwritten (no change on the camera).
   - **Next:** a RES-Custom hook for UHDC on the box: after `0xC01BA608` (or in `0xC01D0BC0` for
     the display path), give the box the recorded area -- 3856/3 x 2170/3 -> ~1277 x 709 (1.80:1)
     -- and centre it ((2088 - 1277) / 2); or set +0x4C4/+0x4C8/+0x4CC in the object after
     `0xC01C7A5C` and before `0xC01BA608`. Either needs a core build; the read is untouched.
   - **The cause and the fix (2026-11-06):** the display-path table entry (0xC302439C) holds, after
     the box, the window the view shows: +0x2C / +0x30 = canvas +0xD8 - 8 (box columns) x +0xE0 / 3
     - 14, centred (+0x34 = (box - window) / 2). The stock crop step: box 2720 x 1426, window
     1288 x 716 (1.80:1). UHDC with r20's test-2 values (+0xD8 1616, +0xE0 2174): window 1608 x 710,
     2.26:1 -- too wide, the squeeze. (A RAM hook forcing the box to 3856 x 2170 via the settings
     override +0x33C/+0x340, tools/probe/viewbox.py, removed the squeeze but left that 1608 window
     overrunning the box: pink edge, shifted.) +0xD8 alone = 1288: froze (as r20's 3856): +0xD8 must
     equal the preview width +0x0C and +0xE0 three times its height, as stock's crop steps (1296 x
     730 / 1296 / 2190). UHDC now: preview 1288 x 724, active 1280 x 720, +0xD8 1288, +0xE0 2172 ->
     window 1280 x 710 centred in 2088 x 710 = the recorded 3840 columns. **Camera (RAM): "it seems
     to work".** Card r29 (`cards/20261106-uhdcview-r29`, UHDC.RCD `bd31bdcd`; the other RCDs
     unchanged). The window offsets, crop factor, sensor read and binning were not it.

3. **W48K: no letterboxed live view** (parked 2026-11-05) -- **fix built, card r30 (2026-11-11)**.
   Rows that are not a stock live-view profile's break the LV pipeline; a custom 2.81:1 frame guide
   was the workaround.
   - The recording view: W48K's box is its read / 3 (1586 x 563, 2.82:1) with no window
     (+0xD8/+0xE0 0), drawn into the 1616 x 572 preview and stretched to 16:9 (the user: stretched
     vertically). RAM tests: a 16:9 buffer (1616 x 908, active 1608 x 568) -- still stretched; a
     window taller than the box (+0xD8 1616, +0xE0 2724) -- froze, pink-white garbage (as UHDC's
     overrun); the screen size (0xC31DF1E8 + 0x324/0x328, 1620 x 911 in live view, from the
     display manager's plane via 0xC04288A8 / 0xC01D3250) -- rebuilt continuously.
   - **The aspect code:** the core's two aspect sites (0xC0306EA0 / 0xC0306EEC, stock `mov r0,#3`)
     return the row's aspect. RAM: W48K's row aspect and S.ASPECT := 5 (the still-size table's
     9520x4080, the widest) -> the recording view letterboxed and right ("it's fine during
     recording"), and live view letterboxed after the take (not after a format switch alone).
   - Build: the core accepts aspect 5 on the fp L only (ogc.c, `#ifdef OGC_FPL`), rcd.py likewise,
     W48K's row aspect 5. fp L core `ca8b5861`, W48K.RCD `8fdf0fdc` (the other RCDs unchanged); fp
     core unchanged `7b575c72`. Tests 24/24; mutation: without the core line it refuses W48K.RCD.
   - To check on the card: live view letterboxed from boot / format selection; the band's shape
     (5 is 2.33:1 for stills -- does the view show W48K's 2.81:1 or 2.33:1?); the frame guide.
   - **r30 on the camera (2026-11-11):** letterboxed from the start (boot, before any take). But the
     live view while NOT recording looks **squashed vertically** inside the letterbox (the user;
     noted, not acted on). Likely the stock live view's picture (mode 9, 3184x1276, 16:9 of the
     sensor) drawn into the wider aspect-5 area instead of a 2.8:1 cut of it. The recording view's
     shape on r30 is still to be confirmed.
   - **Fixed (card r31):** live view's profile p51 shows a window of its 1920-wide picture: stock
     +0x28 1071 / +0x10 1081 / +0xE0 1081 (16:9). RAM (p51's canvas, 0xC0C66C34 etc.): 683 / 693 /
     693 = 2.81:1 -- "seems to be okay now". 683 / 1266 of live view's rows is the 3400-row band
     W48K records (mode 188). The focus / half-press views (the other LV_TWINS: p1551, p1516, p1481,
     p1586, p1621..p1726) were still squashed; each window height x 0.637 in RAM -- "it works now".
     Baked in as five W48K standby groups (fpl_formats.W48K_LV, like the OG formats' LV32): W48K.RCD
     `f73b5ea7`, core unchanged `ca8b5861`.

4. **The frame guide does not show in the 3:2 formats** (OG4K, OG48K). It does show in the 16:9 ones
   (U48K, W48K, UHDC). Probably tied to the core's 3:2 display box change. Not traced.

5. **Grid-line overlays cover only the 16:9 area in the 3:2 formats** (the user, 2026-11-06, card
   r22; noted, not acted on). The camera's ratio grid-line overlay draws over the 16:9 part of the
   live view when OG4K / OG48K is selected, not over the whole 3:2 picture. Likely the same cause as
   4 (the overlays still use the 16:9 display box while the core's 3:2 box is shown).

6. **W48K's recording preview:** stretched to 16:9 (checked 2026-11-11) -- see 3, card r30.

7. **Recording to an SSD is untested** with RES-Custom formats. The 1:1 formats need more than the SD
   card can write (OG48K ~365 MB/s at 23.98, W48K ~490 MB/s at 59.94, U48K ~385 MB/s at 29.97,
   UHDC ~500 MB/s at 59.94); clips on the SD card stop after a second or two.

## Loader v4 / USB shell

8. **The USB shell does not answer after a Fast Start restart** (power switch); it does after a
   battery-pull cold boot. Seen since card r4.

9. **LOAD.LOG stays empty after some boots** (2026-11-04, card r7): the core clearly loaded, so the
   log path probably differs on the Fast Start boot. Check together with 8.

## Build environment (not bugs, but needed)

- Byte-identical cores need Fedora 44's clang 22.1.8 first on PATH
  (`export PATH=$HOME/.local/opt/clang22/bin:$PATH`) and the project venv on Python 3.14
  (projects/fpl-port/.venv). With clang 23 the cores build and work but differ.
