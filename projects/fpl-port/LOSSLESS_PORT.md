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

## Open

- On the camera: the codec calls, the lossless menu row, the frame sizes past FHD / UHD.
