# fpLossless on the fp L (started 2026-11-06)

The lossless module (`fpSup/lossless`, Loader v4 sup `Lossless_v0.3.1.BIN`) built for the fp L with
`FPSUP_CAMERA=fpl`. Not on the camera yet.

## What it took to build

- **Addresses.** 44 fp addresses lossless uses were not in `fpl302.tsv`. AddrMap (as `gen_table.py`,
  appended, not regenerated): 39 exact byte matches, including all 13 hook sites -- the CinemaDNG
  writer / REC preparation / stop / final flush / player code is the same code. `0xC2EF6E00` (the
  image end = SEG1 base, the NBU reader's bound) is `0xC2F06A00` on the fp L (both images' lengths;
  AddrMap guessed 0x70 off). Four RAM words of the menu event table (only `menu/verify_recipe.py`, a
  host evidence tool, uses them) are `verify` at +0xFF48.
- **Hook sites and stock words.** `build_card.SITES` (13 sites, fp stock words) is mapped through
  `fwtarget.fw()` for another camera; each stock word is read from that image and accepted only as
  the same instruction -- identical, or a BL to the mapped target (a BL's word encodes the distance).
  `card.S`'s three BL stock words (`STOCK_REC`, `STOCK_FLUSH`, `STOCK_DISCARD`) take the verified
  words as `*_W` defines; `WANT_KIND` is mapped. The fp build is unchanged (`a03d2dc1…`).
- **The firmware version.** `control.c` refused anything but 502 and `producer_facts.c` stamped 502;
  both use `FPSUP_FIRMWARE` (default 502; the fp L build passes 302).

## The memory map (camera, 2026-11-06)

MMU registers (USB, `tools/probe/vec/readmmu.S`): TTBR0 0x44300040, TTBCR 0 (TTBR0 only), DACR
0x55555555, SCTLR 0x00C51C7D (TRE = 0: no TEX remap), PRRR 0x00098AA4, NMRR 0x44E048E0. The
first-level table at PA 0x44300000 is all 16 MB supersections:

| VA | PA | memory type |
|---|---|---|
| 0x40000000-0xBFFFFFFF | = VA (2 GB) | normal, inner/outer **non-cacheable** |
| 0xC0000000-0xFFFFFFFF | 0x40000000-0x7FFFFFFF (the first GB) | normal, inner/outer write-back write-allocate |

So: any RAM address in 0x4.. - 0xB.. is already uncached; a cached 0xC.. address is uncached at
-0x80000000; the second gigabyte has no cached view. The fp's lossless code took an uncached view as
`a + 0x40000000` (the fp's mirror) -- on the fp L that is other memory. `frame_hold.c` and
`flush_site.c` use, under `FPSUP_CAMERA_FPL`: `a >= 0xC0000000 ? a - 0x80000000 : a`.
`card.S`'s own relocation (a USER block in 0x4.. - 0x7.. runs from +0x80000000, cached) stays right;
a block in the second gigabyte would simply stay uncached.

## Tests

The fp's suites, clang 22 (the sanitizer runs need the system clang 23: the private clang 22 has no
compiler-rt): control 33, native modules 187 + per module, v3/v4/card emulation 65 -- the same
results as the unmodified tree (test_native_variable 25 and test_header_tag 2 errors on both: a
loader quirk and no `rawpy`; test_codec_job flaky).

## STOPFX (2026-11-06)

The stop-queue release LOSS's camera tests ran with (`fpSup/stopfix`, one patched word). Both
functions compared instruction by instruction: identical modulo the mapped BLs and data (+0x2624C).
`fpl302.tsv`: the site `0xC0377118 -> 0xC0377330` and the target `0xC03776A0 -> 0xC03778B8`, both
`checked`; the distance is the same, so the patch word is still `0xEA000160`. `stopfix_fixture.py`
maps both through `fwtarget.fw()`, checks the stock word (`0xE92D4030`) and computes the branch; the
fp keeps its hash assert. Loader v4 module (`ports.stopfx()`): fp v3 `f9f26a09` unchanged, v4
`253536ca`; fp L v4 `36505cc3`, `Stop-FX_v0.1.0.BIN` 340 B (differs from the fp's only in the site
word). Emulated v4 boot with RES-Custom r22 + Lossless + Stop-FX: both add-ons LOADED, no error.
(`test_ports_v4`'s ULWR released-bytes test fails with and without this change.)

## r23: froze at boot (2026-11-06)

Card r23 (RES-Custom r22 + Lossless `65c2ea28` + Stop-FX): the boot screen's fourth square never
filled, live view ran, the UI and USB were dead; a battery pull to switch off. LOAD.LOG was not
written. Cause: `build_card.compile_c` compiled the C **without** the fp -> fp L translation (only
`card.S` went through armasm's); 27 fp-only addresses were in the binary as movw/movt pairs (the
earlier "no fp address left" scan read only data words). Among them `tk_dly_tsk`, so the
priority-12 codec task never slept and starved the UI; and the IRQ helpers and the Subject list.
The emulated boot passed it: the harness stubs the firmware.

Fix: `compile_c` preprocesses, `fwtarget.translate_c`, compiles (`build_v4.py`'s rule; an unmapped
address is fatal). 35 more rows in `fpl302.tsv`: 26 code exact; the codec init `0xC05A6890 ->
0xC05A2A70` and its flag `0xC062F441 -> 0xC062B8A9` (instruction-compared, AddrMap had a gap / a
wrong guess); six RAM objects by every matched movw/movt reference; the 0xC8000000 bound const.
fp L Lossless `de825bd0` (scan incl. movw/movt: no fp-only address); fp unchanged `a03d2dc1`.
Card r24 = r23 with it.

## r24: boots, every take refused (2026-11-06)

r24 boots (all modules LOADED), the row is installed (ON by default: the saved record), the codec
task runs (id 120), the hooks fire (46 frames, writer, observer) -- but A001_191..194 are all
uncompressed. Status over USB (`card_status.py`, now with this camera's cave): the take refused
with `FPL_UNSUPPORTED` after the firmware's own preparation (native 1); the facts read was fine
(1936x1090, format 0 = 12-bit packed, rate code 1, 24000/1001). Cause: `build_card.unity()`
`#undef`s every macro a unit defines after it -- `control.c`'s fallback `#define FPSUP_FIRMWARE
502` included -- so `producer_facts.c` stamped 502 while `control.c` checked 302. The unity now
leaves command-line (-D) macros alone. fp L Lossless `de9be650` (stamp and check both 302); fp
unchanged `a03d2dc1`. Card r25 = r24 with it. The fp L FHD producer is 1936x1090 (fp: see its notes).

## r25: compressed (2026-11-06)

Card r25 (Lossless `de9be650`, written over USB with putfile.py, read back with getfile.py). Take
A001_195, stock FHD 23.98 12-bit: status over USB -- admitted, second lane on, 45 frames, 44
compressed (the first left stock by design), 0 refused / faults / stalls, codec 13.5 ms per frame
(12 tiles of 512x368), clean stop. On the card: 45 DNGs, no gaps; frame 1 3,245,568 B
(uncompressed), frames 2..45 0.96-1.01 MB (~31 %). `check_take.py` on frames 2, 3, 23, 45:
Compression 7, 12 tiles each SOI..EOI inside the file, root IFD at 16728 (the fp's is at
0x13400: `verify_compressed_dng.py`'s fixed layout rejects the fp L's frames); all 45 decode with
LibRaw 0.22 (rawpy, temporary venv) to 1936x1090, max 4095. Differences between frames are
scene/noise-sized (stock A001_193: consecutive 13-14, 20 frames apart 38; compressed consecutive
4-31). Bit-exactness against the source frame is not proven on the fp L (no source copy taken).

## Open

- On the camera: the codec calls, the lossless menu row, the frame sizes past FHD / UHD.
