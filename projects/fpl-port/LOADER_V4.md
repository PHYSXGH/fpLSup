# Loader v4 on the fp L (phase 1 of the res-custom port, started 2026-11-03)

## Memory map (read live, read-only, 2026-11-03)

The fp L uses the firmware's built-in MMU region table (the boot-stage pointer at 0xC2F06B60 reads
0xFFFFFFFF; the default table at fp L 0xC0723A78 is the same as the fp's at 0xC0725F38). TTBR0 = 0x44300000.

| VA | L1 descriptor | meaning |
|---|---|---|
| 0x00000000 | `0x0004D806` | as on the fp |
| 0x2E000000 | `0x2E044C02` | as on the fp |
| 0x40000000 … 0xBFFFFFFF | `0x..044C02` | PA = VA, Normal **non-cacheable** (TEX=4, C=B=0): both gigabytes |
| 0xC0000000 … 0xFFFFFFFF | `0x40045C06` … `0x7F045C06` | PA 0x40000000 … 0x7FFFFFFF, **write-back** (TEX=5, B=1) |

0x4307B9D4 and 0xC307B9D4 read the same live data (the lens block), as do 0x4343C5E0 / 0xC343C5E0.

So Loader v4's cached execution (load through 0x4…, run at +0x80000000) works on the fp L as on the fp for
any block in 0x40000000–0x7FFFFFFF. A block in the second gigabyte (0x80000000–0xBFFFFFFF) has no cached
alias; `sloader4.c cached()` already leaves those alone, so it runs uncached (slower, correct). This differs
from the USB worker's problem: its "+0x40000000" was meant as an uncached mirror and lands in that second
gigabyte on the fp L.

## Build (`FPSUP_CAMERA=fpl python3 -B fpSup/loader-v4/build_v4.py --out OUT --no-ui`)

- C sources are preprocessed and their fp addresses mapped (`fwtarget.translate_c`); -D values that are
  already this camera's go in as decimal (`fwtarget.c_defines`). Unmapped = build error.
- New table rows (`fpl302.tsv`, "(Loader v4)"): the directory API, the power-off objects (debug logs:
  `verify`), the fpSup page / fpsup-ui sites, the UI app word 0xC37B7048 → 0xC37B6B10 (singleton base
  moved −0x538, from FUN_c055f0f0 → 0xC055B208).
- fp builds byte-identical (core, SupManager, shell).
- Not yet: the fpSup page (`--ui`): its builder needs `out/seg0_c0000000.bin`, which this checkout does not
  have (fails at HEAD too).

## Emulator (`FPSUP_CAMERA=fpl`, fp L image)

| test | fp L |
|---|---|
| test_v4 | 26/26 |
| test_boot_card_v4 (slow, Fast Start 2, Fast Start 3, markers) | 8/8 |
| test_boot_slim_v4 | 7/7 |
| test_pwroff_log_v4, test_pwroff_file_v4 | 8/8, 7/7 |
| `test_v4.py --mutate` | 20/20 caught |

The harnesses (`fp_usb_shell/v3/test_v3.py`, the v4 tests) now load the target camera's image and map
their addresses with `fw()`. Loader v3's own tests still fail on the fp L: its C build (`build_v3.py`) is
not ported, and v4 does not need it.

## Card r1 on the camera (2026-11-03)

`cards/20261103-loader-v4-r1`: AutoRun.txt (`6ddd8a03…`), `fpSup\LOADER.BIN` (`3f6b6aa3…`),
`fpSup\SUPMGR.BIN` (`d8d6ad93…`), `fpSup\USB-Shell_v3.4.0.BIN` (`37232689…`). Normal boot only (no Fast
Start, no splash, no fpSup page; the text progress bar shows in red).

Boot ~3 s, the USB shell answered at once. LOAD.LOG, both boots (battery pull, then power switch):

```
01 <boot id>          START
11 00000002           LISTED: 2 sups
0A C534F640 0 SUPMGR.BIN           LOADED at the cached alias, 64-aligned
0C C0D03A24 4 USB-Shell_v3.4.0.BIN REPAIRED
0C C003178C 4 USB-Shell_v3.4.0.BIN REPAIRED
0C C01E3F84 4 USB-Shell_v3.4.0.BIN REPAIRED
0A 45351D40 4 USB-Shell_v3.4.0.BIN LOADED (uncached: not SL_F_CACHED_OK), 4 patches
0E 2 2                DONE
```

**The bug:** REPAIRED on every boot, including after a power-off. The shell's patch table declares each
site's stock word, and `fp_usb_shell/v3/build_v3.py` took those from `out/` (the **fp's** image) for every
camera. The fp L shell declared the fp's words at fp L addresses, so the loader wrote them into the fp L
code at boot ("repair") and again at power-off (restore). Short-lived (the shell's patch follows at once,
and power-off is the end), but wrong. **Fixed:** `build_v3.IMAGE` is the target camera's image. New test
`test_v4 test_shell_declares_this_cameras_stock_words`: no REPAIRED on a fresh image and every journaled
word equals the image's; with the fp image it fails on exactly these three sites.

## Card r2

`cards/20261103-loader-v4-r2`: r1 with the fixed shell (`USB-Shell_v3.4.0.BIN` `d434f228…`; the other three
files identical). Expected: no REPAIRED lines on any boot.

**r2 on the camera (2026-11-03):** battery-pull boot, then a power-switch off/on; LOAD.LOG of the second boot:

```
01 002BF224           START
11 00000002           LISTED
0A C534F640 0 SUPMGR.BIN           LOADED (cached alias)
0A 45351D40 4 USB-Shell_v3.4.0.BIN LOADED, 4 patches
0E 2 2                DONE
```

No REPAIRED: after a normal power-off every shell site held its fp L stock word again, so the core's
power-off write-back restored them. Loader v4 (core, SupManager, shell) works on the fp L.

Still to do in phase 1: the fpSup page (`--ui`, needs `out/seg0_c0000000.bin` for its builder), the
splash and Fast Start options on this loader.

## Card r3: four-box splash, Fast Start 2 and 3 (2026-11-03)

`cards/20261103-loader-v4-r3-fast` (`build_v4.py --card --no-ui`): AutoRun `1c8794ce…`, LOADER `db3f7834…`, SUPMGR
and shell as r2, `fpSup\UI\0..4.BIN` (the splash). With the user's OK to use the settings store.

On the camera: cold boot (battery pull) about 10 s with the four boxes; power-switch restart almost instant.
LOAD.LOG of the fast restart:

```
01 0011C54D           START (boot id: the loader starts ~1.2 s in, against ~2.9 s on the normal path)
11 00000002           LISTED
0A C52D4A00 0 SUPMGR.BIN           LOADED (cached alias)
0A 452D7100 4 USB-Shell_v3.4.0.BIN LOADED, 4 patches
0E 2 2                DONE
```

No REPAIRED: the power-off write-back and the fast path both leave the firmware clean.

## The fpSup page (`--ui`), 2026-11-04

The page builders read the camera's own UI resources. On the fp L those are the fp's byte for byte:
**one 34.4 MB block, 0xC0D223E9 … 0xC2DEAB88 (the stock NBR container, the NBU UI container, all 221
resource sets, the string pool), identical at +0xFD40**. Added as one `range` row. The UI code moved −0x3E20
(per-address rows, bytes checked), the property descriptor tables +0xFC50 (pointer tables: every field
name checked by the builder), and the two GUI page tables (60 and 13 entries, same names and ids, MainY5 =
21) are checked rows.

Made camera-aware (image, index and addresses from FPSUP_CAMERA):
- `research/ui/tools/nbu_probe` (the emulator index tool; pinned to each camera's image) and `nbr_stock.py`;
  the fp L index is `research/ui/nbu_sets_fpl.json` (221 of 221 sets, pool 0x2B018 bytes at 0xC18D01B4);
- `fpSup/uishare/tab` (`build_ft6`, `build_fp4`, `manager_logo`), `projects/open-gate/build` (`sl_pages`,
  `sl_b25_page`, `sl_size_page`, `sl_wh_page`, `imx410_rate_ui`), `fpSup/lossless/menu/build_menu_candidate`;
- tests: `uishare/tab` 18/18 and `loader-v4/test_ui_v4` 38/38 on both cameras (through the camera's own UI
  interpreter and state-machine matcher on the fp L image); `nbu_probe` 43/43 on the fp.

The page files (`UI\FPSUP.BIN` `968f9eb7…`, `UI\SUPMGR.BIN` `2fbeabc1…`) come out the same for both cameras, as
the identical UI data predicts; the core differs (its page hooks are at fp L addresses). Environment: the
image is also linked as `out*/seg0_c0000000.bin`; Pillow and lz4 in `projects/fpl-port/.venv`.

**Card r4** `cards/20261104-loader-v4-r4-page` (`build_v4.py --card`): r3 plus the page. AutoRun identical
to r3's (`1c8794ce…`), LOADER `07628179…`, `UI\FPSUP.BIN`, `UI\SUPMGR.BIN`. The page: SYSTEM menu, page 6.

**r4 on the camera (2026-11-04):** the fpSup page shows on SYSTEM page 6 and is usable (user). LOAD.LOG:

```
01 0025436A           START
11 00000002           LISTED
32 00000000 0 LOADER.BIN           UI: page hooks installed
0A C5353A80 0 SUPMGR.BIN           LOADED (cached alias)
0A 453716C0 4 USB-Shell_v3.4.0.BIN LOADED, 4 patches
32 00000100 1 LOADER.BIN           UI: page 0 with 1 row (SupManager)
0E 3 3                DONE
```

No REPAIRED. Phase 1 (Loader v4 on the fp L: core, SupManager, shell, splash, Fast Start 2/3, the fpSup
page) is done.
