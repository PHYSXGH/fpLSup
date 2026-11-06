# fp L port: open issues

Things to fix or check. The history and the evidence for each are in RESCUSTOM_PORT.md (res-custom)
and LOADER_V4.md (loader); each entry names the card it was seen on. Newest first within a section.

## RES-Custom

1. **The custom resolution names are not loaded at boot** (the user, 2026-11-06, card r19).
   Reported as a separate issue; details still to collect (which names: the menu row, the Quick Set
   tile, the live-view label; and whether they appear after a resolution change or a menu visit).

2. **UHDC: the live view while recording is squeezed horizontally** (things look too tall).
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
   - Next: dynamic. At record start, snapshot what the canvas is copied into, for stock FHD
     (p2100: the same 6288x2174 read, a correct preview) and for UHDC, diff, and find the field
     the preview's source area comes from.

3. **W48K: no letterboxed live view** (parked 2026-11-05). Rows that are not a stock live-view
   profile's break the LV pipeline. Workaround: a custom 2.81:1 frame guide.

4. **The frame guide does not show in the 3:2 formats** (OG4K, OG48K). It does show in the 16:9 ones
   (U48K, W48K, UHDC). Probably tied to the core's 3:2 display box change. Not traced.

5. **W48K's recording preview:** r16 made it even (1616x572). Whether it now looks right while
   recording has not been checked.

6. **Recording to an SSD is untested** with RES-Custom formats. The 1:1 formats need more than the SD
   card can write (OG48K ~365 MB/s at 23.98, W48K ~490 MB/s at 59.94, U48K ~385 MB/s at 29.97,
   UHDC ~500 MB/s at 59.94); clips on the SD card stop after a second or two.

## Loader v4 / USB shell

7. **The USB shell does not answer after a Fast Start restart** (power switch); it does after a
   battery-pull cold boot. Seen since card r4.

8. **LOAD.LOG stays empty after some boots** (2026-11-04, card r7): the core clearly loaded, so the
   log path probably differs on the Fast Start boot. Check together with 7.

## Build environment (not bugs, but needed)

- Byte-identical cores need Fedora 44's clang 22.1.8 first on PATH
  (`export PATH=$HOME/.local/opt/clang22/bin:$PATH`) and the project venv on Python 3.14
  (projects/fpl-port/.venv). With clang 23 the cores build and work but differ.
