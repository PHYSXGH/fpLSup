# fp L port: open issues

Things to fix or check. The history and the evidence for each are in RESCUSTOM_PORT.md (res-custom)
and LOADER_V4.md (loader); each entry names the card it was seen on. Newest first within a section.

## RES-Custom

1. **The custom resolution names are not loaded at boot** (the user, 2026-11-06, card r19).
   Reported as a separate issue; details still to collect (which names: the menu row, the Quick Set
   tile, the live-view label; and whether they appear after a resolution change or a menu visit).

2. **UHDC: the live view while recording is squeezed horizontally** (things look ~1.2x too tall). Parked.
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

3. **W48K: no letterboxed live view** (parked 2026-11-05). Rows that are not a stock live-view
   profile's break the LV pipeline. Workaround: a custom 2.81:1 frame guide.

4. **The frame guide does not show in the 3:2 formats** (OG4K, OG48K). It does show in the 16:9 ones
   (U48K, W48K, UHDC). Probably tied to the core's 3:2 display box change. Not traced.

5. **Grid-line overlays cover only the 16:9 area in the 3:2 formats** (the user, 2026-11-06, card
   r22; noted, not acted on). The camera's ratio grid-line overlay draws over the 16:9 part of the
   live view when OG4K / OG48K is selected, not over the whole 3:2 picture. Likely the same cause as
   4 (the overlays still use the 16:9 display box while the core's 3:2 box is shown).

6. **W48K's recording preview:** r16 made it even (1616x572). Whether it now looks right while
   recording has not been checked.

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
