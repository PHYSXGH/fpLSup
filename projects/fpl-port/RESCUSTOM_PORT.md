# res-custom on the fp L (phase 2, started 2026-11-04)

Source: `projects/open-gate/build/res-custom-v4` (Loader v4 build of v0.1.4test). Loader v4 runs on the fp L
(`LOADER_V4.md`).

## Hook sites (54, `ogc_layout.HOOKS`)

Compared against the fp L image (fp site mapped; the same word, or a branch with the same condition whose
target maps to the fp L target):

- **42 identical** at their mapped sites.
- **fps1–fps4** (0xC02092CC, 0xC0218AEC, 0xC0219260, 0xC03AA568): the same calls; their target fp
  0xC032C750 is fp L **0xC032C820** (54 of its 55 fp callers map to calls of it). Fine.
- **canvas** 0xC043A19C → **0xC0439934**, **vpro** 0xC043A18C → **0xC0439924**, **save** 0xC0088C60 →
  **0xC00862D4**: unique pattern matches (13 / 13 / 9 instructions, branch offsets and constants masked).
  Rows `verify`: confirm by reading each function before use.
- **angtv** 0xC052DCFC → 0xC052A3B4: same instruction, different constant (`movw r2, #0x2400` on the fp,
  `#0x2930` on the fp L). To read: what the constant is (a shutter/angle limit?) and whether the shim
  depends on it.
- **picker** 0xC043CCF8 (the recording-resolution picker entry) and **mag** 0xC043B6A4 (`movw r1, #0x46F0`,
  "MAG4"): no pattern match, no mapped caller. To find in the fp L's recording-settings code.
- **v32** 0xC03249A0 and **binpath** 0xC0325228: methods of `XC_ImageSensorIMX410` (vtable fp 0xC0B5FC80,
  slots +0xC8 and +0xDC). The fp L's sensor vtable is at **0xC0B90DF4** (slots +0x90, +0x94, +0xE0..+0x120
  hold the mapped fp functions). Its slot +0xC8 is 0xC0326210 and +0xDC is 0xC0326268, and **both are
  empty stubs** (`return`). Many other IMX410-specific slots hold one shared default (0xC01F1F24) on the
  fp L. So the IMX455 driver does not serve a mode's row through v32, nor adjust binning through binpath:
  res-custom's virtual modes need the IMX455's own path for these. Next: find who calls slots +0xC8 / +0xDC
  on the fp and what the fp L does at the same call sites.

The generic table accessors res-custom hooks (`lk_tim`, `lk_meta`, `lk_r28`, `lk_r38`, `lk_r14`, `lk_r68`,
`lk_reg`, `lk_r10`; FUN_c0320xxx / c0326db8 / c031ffa0) are identical on the fp L.

## Which sensor routines the fp L really calls (camera, 2026-11-04)

Call counters in RAM only (`cave.claim` block, three stubs; each entry's first word branched to its stub,
the camera's own D/I-cache routines run through the borrowed `echo`; removed and read back afterwards).
Card r4, cold boot. The user changed resolution, frame rate and crop, and recorded a clip:

| entry | calls |
|---|---|
| IMX455 v32 (vtable 0xC0B90DF4 +0xC8, 0xC0326210, an empty stub) | **0** |
| IMX455 binpath (+0xDC, 0xC0326268, an empty stub) | **0** |
| generic geometry lookup F_GEOM (0xC0325140) | **42,129** |

The fp L never calls v32 or binpath: mode rows come through the generic lookups, which res-custom also hooks
(`lk_*`, identical code on the fp L). **On the fp L the v32 and binpath hooks are left out**; the virtual
modes go through the generic hooks. Binning on the IMX455: start from `binkernel1/2` (mapped exactly).

Also seen: the USB shell does not answer after a Fast Start restart with Loader v4 (card r4), though
LOAD.LOG says it loaded; after a cold boot it answers. Open (Loader v4).

## picker, mag (static, 2026-11-04)

**mag** (fp 0xC043B6A4, `movw/movt r1` of "MAG4" at 0xC0BE46F0): the fp has two MAG4/MAG8 copies,
loaded at 0xC043B2A4 (first) and the hook site (second). The fp L has its copies at 0xC0CBE118 / 0xC0CBE16C,
loaded at 0xC043B618 (first) and **0xC043B8E8** (second): the hook site by that correspondence (the function
changed: 12 of 120 masked words agree). `verify`. ogc.c's G_MAG returns the fp's MAG8 low half (0x46F8)
as a constant: on the fp L it must be the fp L's (MAG8 = MAG4 + 8 in both: return v + 8).

**picker** (fp 0xC043CCF8): a loop over a table of 16-byte entries (key at +0xC, strncmp 15) returning the
match. The fp has **ten** such functions, one per table (26, 32, 48, 28, 16, 8, 4, 36, 18, 6 entries,
0xC043CCF8 … 0xC0441358). The fp L has **one** (0xC043D5B8, 6 entries, = the fp's 0xC0441358), and right after
it a **generic** lookup (0xC043D618) that takes each table's base and count from a descriptor
(`[obj + 0x588 + index × 4]`, +0x18 base, +0x1C count). So on the fp L the recording-resolution picker res-custom
hooks is not a function of its own: the hook belongs on the generic lookup, gated on which table is
searched, and ogc_pick's `table == TAB1/2/3` test needs the fp L's tables. Next: the fp L's callers of the
generic lookup for the 8/10/12-bit recording tables, and those tables' entry layout.

**angtv** still to read.

## angtv and the picker's data (static, 2026-11-04)

**angtv** (fp 0xC052DCFC): the hooked word is the `movw` of a `movw/movt r2` pair loading fp 0xC0D02400 = fp L
**0xC0D12930** (site fp L 0xC052A3B4; the code around it is identical). The shim's replay writes the fp's
low half as a bare `movw r2, #0x2400`, which no address rewrite sees: it must be
`#:lower16:0xC0D02400`. Rows added.

**The picker's tables.** The fp's recording-resolution tables (TAB1/2/3 = 0xC0BE5810 / 59B0 / 5B50, 8/10/12-bit,
26 entries of {5, sensor mode, id, key*}, keys "UHD30" … "FHD100CROP") have no counterpart of the same shape on
the fp L. The fp L's entries (around 0xC0CBE7F0..0xC0CBED80) are {**key*** first, a type 1/3/5 (likely 8/10/12-bit),
an id, …}, keys composed differently ("UHD23_98FPS", "FHD119_88FPS", plus "8B/10B/12B", "PINP", "MAG4" parts),
in several runs per type, searched by the generic lookup (descriptor base +0x18, count +0x1C). res-custom's
picker returns entries in the fp's layout, so on the fp L it is a **redesign**, not a re-address: understand the
fp L's key composition and the meaning of the id, then serve our formats' entries in the fp L's layout.

## Where the 54 hooks stand

| state | hooks |
|---|---|
| identical, or the same call via a mapped target | 46 (42 + fps1..4) |
| found by pattern / correspondence (`verify`) | canvas, vpro, save, mag |
| found, needs a shim change | angtv (`#:lower16:`) |
| not needed on the fp L (never called) | v32, binpath |
| redesigned: three `bl` hooks pick8 / pick10 / pick12 | picker |

Code changes for the fp L besides addresses: angtv's replay; ogc.c's G_MAG constant (return v + 8); leave out
v32/binpath; the picker.

## The picker on the fp L (static, 2026-11-04)

The fp's chain: FUN_c043b828 copies a 16-byte key template, two vtable calls (+0xC, +0x10) append the
resolution and rate, "CROP" is appended in Crop Mode, then by raw bit type `[r6+0x20]` (4 → TAB1 8-bit,
3 → TAB2 10-bit, else TAB3 12-bit) the picker 0xC043CCF8 walks that table's 16-byte entries {.., .., .., key*}.

The fp L's counterpart is **0xC043BA20** (reached from the dispatcher 0xC043C0B8): the same template copy and
the same two vtable calls, **no CROP append**, then:

- `index = FUN_c043ccf8(r6 + 0x48)`: looks the value up in a 33-entry list at 0xC0CBE3A4 = **the crop
  factors × 100** (100, 105, 111, 117 … 318 … 496), i.e. the crop step;
- `desc = [obj + 0x588 + index × 4]`: one descriptor per crop step, with {base, count} pairs: +0x48 the 8-bit
  table, +0x50 presumably 10-bit, +0x58 the 12-bit table (also +0x10, +0x18, +0x28 used by neighbours);
- by bit type: **0xC043D0A8** (8-bit), **0xC043D108** (10-bit), **0xC043CE68** (12-bit), each the fp's picker
  loop over {base, count} of 16-byte entries, **key at +0xC as on the fp**, returning the entry or 0.

So the entry layout is the fp's; what changed is the table choice: per crop step instead of a "…CROP" key.
Plan for res-custom on the fp L: hook the three lookups (r0 = the descriptor slot, r1 = the key), call
ogc_pick with the bit depth the hooked lookup stands for, and return our entry in the same layout; the
crop test moves from the key suffix to the crop step. Next: read a live descriptor (capture r0/r1 at one
lookup on the camera) to see its tables' contents (sensor modes per crop step).

## The live tables (camera, 2026-11-04)

A RAM-only capture on the three lookups (cold boot, card r4; removed and read back): the 8-bit lookup
0xC043D0A8 ran 1,018 times with key "FHD23_98FPS", descriptor slot 0xC375F82C (= obj + 0x588, obj 0xC375F2A4),
descriptor 0xC375F918; the 10/12-bit ones not at all (the camera's current setting).

Each entry is **{type (1 stills/LV, 3 and 5 CinemaDNG), profile id, IMX455 sensor mode, key*}**: the third field
is the sensor mode of `imx455_modes.csv` (UHD23_98FPS = 161, FHD23_98FPS = 173 at 1.00×, as the takes' profiles
said). All 33 crop steps' descriptors, read once: `imx455_recording_tables.txt`. In short:

| crop step | UHD 23.98 | FHD 23.98 | FHD 59.94 |
|---|---|---|---|
| 1.00, 1.05 … | 161 | 173 | 166 |
| 1.37, 1.53 … | 187 | 173 | 166 |
| 2.00, 2.48 … | 187 | 187 | 188 |
| 3.18 and up (FHD only) | — | 187 | 196 |

This is also the menu-setting → sensor-mode map asked for earlier (`imx455_modes.csv`). EIS variants have their
own keys ("…EIS"); DCI4K has its own table (+0x40).

For res-custom: the picker hook goes on the three lookups (each with its bit depth), returns entries in this
layout (sensor mode in the third word: the virtual mode's id), and the "crop" test becomes the crop step.

## The build (2026-11-04)

`FPSUP_CAMERA=fpl python3 -B build_v4_rescustom.py --out DIR` builds the core for the fp L
(RES-Custom_v0.1.5.BIN, 321,728 B, no format files); the fp build is unchanged (sha 7b575c72…).

- C: preprocessed, then `fwtarget.translate_c` maps the 0xC… constants; `-D` hex values go in decimal so
  nothing is mapped twice; LAYOUT0 / S_COORD (our own coordinates) are written in decimal for the same reason.
- Shims: armasm maps them; `OGC_FPL` leaves out binpath, picker, v32 and switches mag / angtv.
- Claims: 62 = the fp's 62 less picker, v32, binpath, plus pick8 / pick10 / pick12; each at fw(fp site) (the picks
  at their own fp L sites, `ogc_layout.NATIVE_SITES`) with the fp L image's stock word.
- Formats: none. The five (og3k, og2k, s16, og35k, og4k) borrow IMX410 sensor modes; rcd.decode refuses them
  against the fp L's mode table (ENTRY), so `FORMATS` is empty on the fp L until phase 3.
- Emulated (test_v4's harness, the real Loader v4): the core runs, logs OCD / OCR with no files and releases
  itself, as the fp core does. The full emulated suite (test_v3/v4_rescustom) is fp-only: its camera model
  holds ~125 fp addresses and a mode descriptor built from the IMX410 tables; porting it needs fp L formats.

## The picker, done (static, 2026-11-04)

The fp L recording key builder FUN_c043ba20 is the only caller of the three lookups, so the hooks go on its
three `bl` sites rather than the lookups' entries (no replay; at the call r5 = obj, r6 = the request):

| hook | site | stock | bit depth |
|---|---|---|---|
| pick8 | 0xC043BAB0 | `bl 0xC043D0A8` | 8 (TAB code 1) |
| pick10 | 0xC043BAE4 | `bl 0xC043D108` | 10 (2) |
| pick12 | 0xC043BB10 | `bl 0xC043CE68` | 12 (3) |

Each shim calls ogc_pick(S, bit code, key, `[r6+0x48]` = crop factor x 100); ours -> our entry (the
firmware's 16-byte layout, as on the fp), else down to the stock lookup with r0 / r1 untouched. They are
patched last, as the fp's picker was; pick12's veneer is the last one, so `VRC_PICKER` (RES-Lab's way to
the virtual-RCD endpoint) is 0xC043BB10 on the fp L and `vrc_find` accepts a `bl` there.

Crop: the fp L key never ends in "CROP". ogc_pick takes Crop Mode as "crop step above 1.00x"
(**provisional**, phase 3: the fp L's 33 steps change the sensor mode at 1.37x and 2.00x) and then matches a
Crop Mode format's twin entry as key + "CROP".

**KEYBLD.** The name hook leaves the *playback* key builder's key stock (fp FUN_c043bc68, return 0xC043BCBC; a
format label there picked the wrong playback profile on the fp, 2026-09-13). The fp L's is FUN_c043bf60
(same template copy, one vtable+0xC call, return **0xC043BFB4**; template 0xC0CBE218 = 16 zero bytes as on
the fp), now in the address table (`verify`), so KEYBLD needs no fp L special case.

Untested: ogc_pick only runs with a format, and fp L formats are phase 3.

## Tests (2026-11-04)

- `test_fpl_rescustom.py` (new): builds with FPSUP_CAMERA=fpl and checks no formats, the three picks
  (site, kind, last, stock bl to the right lookup), no picker / v32 / binpath, every hook site claimed once and
  chainable, KEYBLD = 0xC043BFB4 (and not the fp's), and, run under FPSUP_CAMERA=fpl, one emulated boot under
  the real Loader v4 (no REPAIRED / CONFLICT, released for want of formats).
- test_v3/v4_rescustom, test_rcd_bitdepth, test_lv_text_style: fp-only, skipped (setUpModule) under fpl.
- Found on the way, not from the port: armasm.py (linked into open-gate/build) imported fwtarget only when
  the caller had put fp_usb_shell on the path (build_v3_og.py had not); test_rcd_bitdepth lacked NAME / HL
  after CoreTests got them; test_lv_text_style's two string-installer tests fail on the committed tree too
  (their mutation seam `#define MAX_STRBASE MAX_STRINGS` is no longer in uishare's ui_apply.c) -- left alone.
- fp, this machine (Fedora, clang 22.1.8): test_v4_rescustom 78/79, test_rcd_bitdepth 7/7. The one failure,
  V3UnchangedTests (the v3 build = released 32RESCUS.BIN), gives the same 714c921a… on the committed tree:
  the compiler, not the port (the release was built on macOS; the core comes out 1,920 B shorter here).
