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

## Phase 3 groundwork (static, 2026-11-04)

**Per-mode tables: confirmed.** The fp L's lookups (lk_tim / meta / r28 / r38 / r14 / r68 / r10 and the
magnifier copier ac38) are the fp's instruction for instruction (only branch offsets differ): same
descriptor fields, same strides (0x20, 0x64, 0x28, 0x38, 0x14, 0x68, 8; magnifier +0x128, 0x5C). REG is
0x460. The "unverified strides" caveat in ogc_layout is gone.

**Sensor clock.** The IMX455 timing words use the same 72 MHz as the IMX410 (UHD 23.98: 3,003,000 cycles
a frame), so ogc_layout.solve's arithmetic carries over; MIN_TAIL and the hmax limits are the IMX410's and
still need checking against `imx455_modes.csv`.

**Open-gate donors already in the firmware.** Full-sensor 2x2-binned modes: id 3 (4784x3190 read, 30 fps,
hmax 580), id 98 (4784x3190, out 4768x3168, 38 fps), id 143 (10 fps); full-sensor unbinned id 0 / 97 / 142
(9568x6380, out 9520x6328, 9-17 fps). A 3:2 open-gate format can start from these rather than new
register programming.

**The mapping table** (0xC0BF6820) has 4,000 entries (fp: 500 at 0xC0BD05D4, bounded at 0x200 by the
core). `ogc_layout.PID_MAX` = 0xF9F on the fp L (0x200 on the fp, so the fp build is unchanged); ogc.c and
rcd.py use it.

**Profile ids of the recording entries** are static data (0xC0CBE840..): per crop step, UHD23_98FPS is
type 3 p161.. (+0x30), type 3 p3081.. (+0x40), type 5 p2061.. (+0x48, 8-bit CinemaDNG), p2391.. (+0x50,
10-bit), p2721.. (+0x58, 12-bit); 19 crop-step copies (p161..179, sensor mode 161 then 187 from the 6th).

**The classifier** 0xC0439F70 returns flags, not a class: 1 = 1..33, 2 = 51..83, 4 = 101..989, 8 =
2001..2989 (CinemaDNG), 0x10 = 1771..1838, 0x20 = 1841..1978, 0x100 = [obj+0xE0] == 11. The fp's
classifier gives its CinemaDNG donor p83 no flag, and the fp formats record through flag-0 profiles on
purpose (OG3K_PLAYBACK_PROFILE_CLASSES.md: p83 fixed the S-size stills freeze). The fp L pool keeps that
choice (34..50, 84..90, 97..100, no flag); whether CinemaDNG records through a flag-0 profile on the fp L,
or our profiles must carry flag 8 (empty slots inside 2001..2989), is a camera question.

**Still needed for a first fp L format:** the canvas profile's fields on the fp L (the fp formats write
fp offsets: +0x0C/+0x10 sizes, +0x30 engine fps, +0xB0, ...), the register overrides for a new readout
window (0x460-byte records), the menu pack (NBR images), and the user's choice of formats.

**The canvas: same fields.** The canvas builder (fp FUN_c0439d18, fp L FUN_c043a090) fills the canvas
column-wise (canvas + off = column[row]); `tools/canvas_compare.py` reads both builders and compares a
profile pair. fp p132 (UHD23_98, 8-bit CinemaDNG) against fp L p2061 (UHD23_98FPS, 8-bit, crop 1.00): 67
fields on the fp, 65 on the fp L (no +0xF0, no +0x108), and the identifying ones agree at the same offsets
-- +0x00/+0x04 raster 3856x2170, +0x24/+0x2C output 3840x2160, +0x30 engine fps 24.0, +0xFC..+0x104 1.0f
-- while +0xF4/+0xF8 hold each sensor's read area (fp 6064x3412, fp L 9568x5382) and the preview sizes
(+0x0C/+0x10/+0x20/+0x28, +0x60/+0x64, +0xD0..+0xE0) differ. So the fp formats' canvas pairs keep their
meaning on the fp L, except any at +0xF0 / +0x108. The fp's stock CinemaDNG profiles (p131.., keys
"UHD30") carry classifier flag 8 like the fp L's p2001..; only the fp formats' donor p83 has none.

## OG48K: the first fp L format (2026-11-04, static + emulated)

`res-custom-v4/fpl_formats.py`. The fp's OG3K recipe carried over: donor sensor mode 98 (full sensor, 2x2
binned, 4784x3190 read, 38.4 fps ceiling), base profile p1003 (the stock 4768x3168 still, no classifier flag,
like the fp's p83), recording raster 4784x3184, active 4768x3168 (3:2), the video values +0x90 = 1 /
+0xC0 = 0, and the sensor read area / scale set to the binned readout (+0xF4/+0xF8 4784x3190, +0xFC..+0x104
2.0f -- p1003 itself reads the whole sensor unbinned). Video clamp on: on the fp L too only video modes have
the receiver row's +0x04 bit 3 (table 0xC0B94BBC, added `checked`). No preview group (prev_h 0). Rates
23.98 / 24 / 25 / 29.97 (+ the core's virtual 17.98); 29.97 solves to the firmware's own mode 3 timing
(hmax 580, tail 620, vmax 4142). 8/10/12-bit. Resolution value 10 (uishare ui/enums.py 'OG48K').

What had to change for it:
- keys: the fp L's rate tokens are the true rate + "FPS" ("23_98FPS" .. "119_88FPS", strings 0xC0CBE2D0..);
  ogc.c key_make and ogc_layout.RATES carry them under OGC_FPL / FPL.
- uishare's ui package (options.py, qs.py, chain.py) was fp-only: image, resource-set index, NBU base,
  the file-redirect site / cave words and every UI-data address now go through fwtarget (identity on the
  fp). Before, the fp L core's menu block named the fp's redirect site and the applier refused it
  (UIA_HOOK, found with a diagnostic build). build_v3_rescustom no longer maps the template's sites again.
- rcd.py / vr_ui.py imported fwtarget with a silent identity fallback; now a plain import.

Emulated (test_fpl_rescustom, 8/8): with OG48K.RCD the core accepts the file (OCD01010100), every claim,
the donor's timing claim, the veneers and the bit-depth menu go in, and it reaches the menu rows (OCO0: the
bare harness has no GUI) -- the same point the fp core reaches with OG3K there. Beyond that only the camera.
fp: core and all five .RCDs unchanged; uishare test_options / test_qs / test_qs_option / test_qs_layer /
test_ui_strings / test_layer_compat / test_qs_c pass.

Card: `cards/20261104-rescustom-og48k-r1` = card r4 (rebuilt, byte-identical) + `fpSup\RES-Custom_v0.1.5.BIN`
(`33537573…`) + `fpSup\RESCUS\OG48K.RCD` (`2015d873…`).

**OG48K on the camera (r1, 2026-11-04):** live view showed the 3:2 open gate; recording (at the virtual
17.98) crashed the camera at once (colourful lines, battery pull, no file). Reading: the recording engine
got a 4784-wide raster where its stock maximum is UHD's 3856 -- the raster is what it processes (stock FHD
reads 3184x1796 and records 1936x1090; UHD reads 9568x5382 and records 3856x2170; Jose's fp OG4K records
3840x2560 from a 6030x4020 read). Not built any more (kept in fpl_formats.py as the record).

**OG4K (r2):** Jose's fp OG4K recipe: base p2061 (the stock UHD 8-bit CinemaDNG video profile, flag 8 like
his p171), raster 3856x2568 / active 3840x2552 / preview 1296x861, 1280x851 (the stock 3840x2552 still
p1004's), read mode 98's binned 4784x3190 at scale 2.0 (1.24x down on both axes), UHD's resolution value
(3), clamp on. 9.9 Mpx (his: 9.8). Card `cards/20261104-rescustom-og4k-r2`.

**OG4K on the camera (r2, 2026-11-04):** the same crash at record start. So not (only) the raster width. Next,
card r3: **UHDX**, stock UHD under a new name (mode 161 at its exact stock timing through the capture-timing
section, base p2061, no canvas change, 16:9) -- separates the core's recording path from the open-gate content.

**UHDX on the camera (r3) and the USB probe (2026-11-04):** UHDX crashed too, so it is the core, not the
open-gate content. The probe: live view makes no picker call; record calls it ~31 times, each returning our
entry {type 5, profile 34, mode 230, stock timing}; then the whole camera stops, no assertion. The lead: our
profile ids (34..50) carry no classifier flag -- on the fp L that is the still-profile class (1001..) --
where every stock CinemaDNG profile is 2001..2989 (flag 8). Card r4 moves the pool into the CinemaDNG
8-bit block's empty slots (2020, 2040, ..., 2325) and offers UHDX in 8-bit only.

## The recording crash, narrowed on the camera (2026-11-04, USB, RAM only)

Tools: `tools/probe/recdiag.py` (the core's state found from the pick8 veneer, the entry it hands out,
the virtual-mode record; `setent PID MODE` edits the 23.98 entry live; the assertion routine 0xC0011100
hooked) and `tools/probe/vecprobe.py` (VBAR 0xC0000000, literal vectors; a catcher on undefined /
prefetch abort / data abort that records the first fault and parks the task). Card r4 (UHDX, profile pool
2020..2325), always 23.98 CinemaDNG 8-bit:

| entry handed to the camera | result |
|---|---|
| p2061 + mode 161 (stock ids, our entry in our memory) | records |
| p2020 (our virtual profile) + mode 161 | records |
| p2020 + mode 230 (our virtual mode; r1..r4) | crash |
| p2020 + mode 60 (the virtual mode moved below the fp L's 217) | crash |

- Live view never calls the recording lookups; record calls the picker about 20 times a second.
- The virtual mode's six cloned rows equal mode 161's word for word except the id; the register row
  (regfilled) was still unfilled when it crashed.
- The configurator's consumer (v5, 0xC043C2E8) recognises entries only by address range, as on the fp:
  our entry falls through to the same pipeline in every test, so not that. The index lookups' callers are
  the fp's code instruction for instruction.
- **No CPU fault**: with the catcher on, nothing was caught, and the shell kept answering for about a
  minute after the colourful lines appeared. So the image / recording hardware is set up wrong from
  something selected by the mode id, and the system dies later -- not a bad pointer in the CPU.

Next (user, option 2): no invented mode id on the fp L. The entry carries the donor's real id, and while
a res-custom row is live the core's lookup hooks give that id the format's rows.

## Hunting the mode-id consumer (option 1, 2026-11-04, USB, RAM only)

The user's description of the failure: first a semi-transparent overlay of colourful vertical lines, then
after a second or two the live-view image itself gets lines at 45 degrees (a buffer read with the wrong
line width). The CPU does not fault (vecprobe) and the shell sometimes lives on for a minute.

Probes (`tools/probe/`), all with UHDX (virtual mode 230, donor 161), always pressing record at 23.98:

- `magprobe.py`: the five magnifier-table scanners (index starts at -1: an unknown id reads the row
  before the table). In live view they see only modes 9 and 12. A version that also swaps 230 -> 161
  in r0/r1 did not prevent the lines.
- `wideprobe.py`: all 19 functions with an inline per-mode scan, logging any call with 230 in r0..r3:
  none, ever; the record start wakes six of them, all with real ids.
- `cmpprobe.py`: the compare inside all 29 per-mode loops (21 inline scans and the firmware loops behind
  the core's 8 hooked lookups), counting searches for 230 however the id got there: **none**. At record
  start every loop runs, always for real ids; the hooked lookups never pass 230 down.
- Static: no compare chains on mode ids; the only `cmp #161` is USB request handling; the index getters
  (0xC03250E0..) turn the fake index back into a row pointer with the same stride, as on the fp; id 0x77
  means "the current mode", read from the sensor object's +4.

So no firmware code on the CPU looks our id up and gets it wrong -- yet the image hardware is set up
wrong. The id must leave the lookup world: stored (sensor object +4) and handed on as a number, to code
or hardware that keys its own setup on it (an image-processor command, a register value) rather than
through any table the CPU scans.

**Following the mode change (fnprobe, same day).** The sensor-control task (main loop 0xC0207AD0, waiting on
event flags at object +0x52C) runs once per frame in live view and, when a change is requested, calls the
mode-switch routine 0xC0207D38 (target mode at object +0x48), which calls 0xC0310E98 -> sensor task message
(mode at +0x1C4) -> 0xC032A108 (the register-record handler, through the hooked lk_reg).
- Reference (entry = p2020 + mode 161): at record start 0xC0310E98 is called with 161 from 0xC020808C
  (inside 0xC0207D38), then 0xC03253A8 and 0xC032A108 with 161; at stop, back to 9.
- Failing (entry = p2020 + mode 230): 0xC0207D38 is never entered; the per-frame calls of the loop freeze
  at about the moment record is pressed, the shell dies ~10 s later.
So the image path breaks at record start before any sensor mode change is even requested -- in the step
that reconfigures the image pipeline for the recording entry, which reads the entry (its mode 230) and
works with 161. None of the per-mode lookups (cmpprobe), inline scans (wideprobe) or compares saw 230 there.

**Who reads the entry's sensor mode (2026-11-04, cont.).** The only firmware reader of the recording
entry's mode (+8) is the helper 0xC0437290 ("ask the configurator for the entry, return its mode"); the
other configurator users read its profile (+4, into the canvas code the core handles) or work on the
pipeline object v5 picked. Its 21 callers: the four fps sites the core hooks (+ a fifth at 0xC068704C,
0xC032C820 = the geometry row's fps, the clone answers), two 12-byte tables (0xC0910F28: five stills
modes, 161 is not in it either -> no difference), the AE program-line model, a pipeline job that stores
the mode at +0x60 (0xC0374480), comparisons. `tools/probe/idswap.py` gave all 21 the donor id (161)
instead of 230: still the lines; only the per-frame fps site was even called before the camera died.
So nothing reads the virtual id directly at record start. Remaining: the image pipeline breaks first
(the sensor-control task's per-frame loop freezes at the press), from something that depends on the id
only through the core's own answers -- the fake row indices, vm_zoom, R10 -- as the fp L uses them.

**The id itself (2026-11-04, the decisive tests).**
- `tools/probe/realidx.py`: every lookup for 230 returning mode 161's REAL row index (26) instead of the
  fake index: still the lines. The fake indices are not the cause.
- The virtual mode moved to **id 3** (a real IMX455 mode, binned 30p, unused by UHD), same cloned 161
  rows, same entry, same profile: **UHDX records.** With 60 (free, not a real mode) or 230: lines.
So the fp L keeps per-mode data that exists only for real mode ids and reaches it by the id itself -- no
search or compare any probe saw. Leads: `SensorAdjustment` (src/library/CameraController/SensorAdjustment,
0xC051xxxx; also the biggest caller of the mode-change message) builds per-mode adjustment data at boot
from the R68 rows (FUN_c051c490: row +0 id, +4 the mode whose adjustment it uses, +0x60/+0x64), i.e. for
real ids only -- colourful vertical lines fit wrong column/defect correction. Not yet: how it finds the
recording mode's entry at record start. (The 0xD9 compares in AfMgr are the 7 x 31 AF grid, not mode ids.)
Fallback that already works: virtual ids taken from real mode ids.

**id 3 vs 230 with fnprobe on SensorAdjustment (2026-11-04).** With id 3 (records): SensorAdjustment's
builders (0xC051C490, 0xC05227D8) are never called at record start -- not the path. The geometry helper
0xC032C930 is called with the recording id (3) from **0xC0316224, in ImagerController (ImagerDefect.cpp /
ImagerMode.cpp)**, and with 0x77 ("current mode") from 0xC0685xxx (CoordinateMgr / AfLogParser area).
The failing run (230) was not captured (the poller had hung). 0xC03161F0 (the ImagerDefect-side caller)
first calls 0xC032D0D8(out, mode): a mode id from 0xC0122050 (Thumb, outside the sensor module) goes to
0xC0324818 (R28 row, hooked), 0xC032D078 / 0xC032D0A8 (geometry, hooked) and 0xC032DF58 (not read yet).
Next: 0xC032DF58, 0xC0122050 and the defect-correction setup that follows in 0xC03161F0 -- defect /
column correction keyed by the imager mode is the best fit for the vertical lines.

**The camera writes its own evidence (user's idea, 2026-11-04).** `tools/probe/sdprobe.py` + `sd/sdtrig.S`:
a trigger on the configurator's dispatcher (0xC043C0B8) writes a RAM block (the fnprobe records, or the
caller's stack) to \PROBEn.BIN with the firmware's file calls (f_ctor 0xC03660A8, create 0xC03661C8,
write 0xC0366300, close 0xC0366238, dtor 0xC03660E8; mem_heap/get/free as the loader) -- after cleaning
the D-cache (the card write reads memory, not the cache: the first dumps were zeros / stale). The files
survive the crash. Results:
- fnprobe (6 fns), id 3 vs 230: with 230 nothing after the first dispatcher calls -- no ImagerDefect
  call (0xC03161F0: 140 calls while recording with 3, 0 with 230), no mode change.
- stack dumps at dispatcher calls 5/40/200 (id 3) and 5/25/60 (230): the same chain in both -- task
  0xC036F068 -> 0xC0203DA8 -> 0xC02042F8 -> 0xC02076E8 -> 0xC0205A00 -> 0xC04CBF80 -> 0xC0205BA8 (AE,
  the fps1 site; also the AE program line 0xC0227xxx) -> 0xC0437290. The dispatcher calls are auto-exposure
  asking for the recording mode every frame, in both runs: not the stall.
Next suspect: the R10 value (descriptor +0x10 {value, mode} pairs; "FUN_c0320008 programs the readout
with it"): the core returns the donor's value only when the donor has a pair, else the firmware's
lookup falls back to pair 0 for an id it does not know -- a real id (3) finds its own pair.
**R10 ruled out (r10check.py, camera):** the R10 table (0xC0B93BCC, 85 pairs) has a pair for every real
mode (161 -> 2, 3 -> 1, ...); the core answers its virtual mode itself with the donor's value (R10OK 1,
R10 2). No fallback to pair 0. ImagerMode / ImagerShoot (0xC0319050..) reach the per-mode data through
the hooked lookups as well. Still open: what keys on the id number itself.

**id tests and memory searches (2026-11-04, cont.).** Virtual id 98 (real) records; 1 (free, small) gives
the lines -- it is membership in the firmware's mode set, not the number's size. No structure in RAM marks
the real ids: ramdump/ramsearch(2)/ramsearch_hi over 0xC0B00000-0xC0E00000, 0xC2D00000-0xC8000000 and
the whole upper gigabyte (0x80000000-0xBFFFFFFF, physical RAM only the uncached window reaches; dumped
through MEM1 in 8 MiB pieces -- a 16 MiB request is over the worker's limit and wedges the shell): no
bitmap, id->index / id->pointer map, per-id "present" record (zero or constant absent), or id list. The
descriptor holds only the tables the core already covers. The six inline R10 scans (0xC03EBAE0..) are the
factory test commands (mode_list, testpattern, adj_init ...). So the membership test is a search of the
mode tables themselves; next: cmpprobe on all 29 loops, its counters written to the card by sdtrig
(`CMPPROBE_COUNTS=1 sdprobe.py cmp`), so a search for 230 just before the camera dies is kept.

## Three IMX455-only per-mode tables the core does not know (static, 2026-11-04)
Searching the image for tables in the timing table's row order (85 rows, ids 0, 129, 97, ...) found three
more, all reached through a second sensor object, 0xC343C5B4, built by FUN_c0329f68 from three getters:
[0] = 0xC0B98DE0 (REG, hooked as lk_reg = 0xC032C5F0), [4] = 0xC0BB05CC, [8] = 0xC0BB01C8.

| table | descriptor {base, count} | stride | index search (id -> i, -1 on a miss) | row copier (dst, obj, id) | copier's callers |
|---|---|---|---|---|---|
| T3C | 0xC0BB05D4 {0xC0BB2468, 85} | 0x3C | 0xC032C658 | 0xC032C4E0 | 0xC0329498, 554, 608, 868 |
| T5C | 0xC0BB05CC {0xC0BB05DC, 85} | 0x5C | 0xC032C6C0 | 0xC032C548 | 0xC0329A90, BB8, C08, C70, D0C, DA4 |
| T0C | 0xC0BB01C8 {0xC0BB01D0, 85} | 0x0C | 0xC032C728 | 0xC032C598 | 0xC0327AEC, BE0, C0C, C34 |

None has a counterpart in the core: a virtual id misses, the search returns -1 and the copier copies the
row before the table (row -1), which is what reads differently for a real id and a virtual one. Mode 161
is row 26 in all three (as in the timing table). Live test: `tablepatch.py apply 230 161` copies donor
161's row over row 84 (mode 217) in each table, relabelled 230; `restore` puts the image's rows back.

**The fix (static + emulated, 2026-11-04):** three fp L-native `b` hooks, `lk_x3c` 0xC032C658, `lk_x5c`
0xC032C6C0, `lk_x0c` 0xC032C728 (ogc_layout.XLOOKS). For an id in the core's virtual range, one shared shim
body (`xlook`, ogc_shims.S) asks `ogc_donor` (FN DONOR, fp L only) for the vm's donor and runs the search
with it, so each copier gets the donor's row; any other id goes straight down. Their return addresses
are written in decimal, so fwtarget doesn't map them. test_fpl_rescustom
`test_imx455_searches_find_the_donor_row_for_a_virtual_id` runs the shims against the real search code
in unicorn (230 -> 26, 217 -> 84, 231 -> -1, 161 -> 26); with the swap removed it fails with -1, the
crash mechanism. fp core unchanged (7b575c72). fp L core `77d0dd65…`; card
`cards/20261104-rescustom-uhdx-r5-xlook` = r4 with only that BIN changed (UHDX.RCD `a2375fd0…` as r4).

**UHDX on the camera (r5, 2026-11-04): it records.** Cold boot, UHDX at 23.98, virtual mode 230 → the
recording starts and stops normally, no lines. The three IMX455-only tables were the cause of every
RES-Custom recording crash on the fp L (OG48K, OG4K, UHDX r3/r4).
Clip `A001_136` (r5, UHDX): 104 frames, 4.3 s, 3856x2170 8-bit uncompressed, ActiveArea 0,0,2170,3856,
DefaultCrop 3840x2160 at (8,5), FrameRate 23.976 -- the same tags and file size (8,447,488 B) as a
stock UHD clip (A001_131). Frame 50 is a clean picture, no lines.

**Card r6 (2026-11-04): OG4K retried.** `cards/20261104-rescustom-og4k-r6` = r5 + `RESCUS\OG4K.RCD`
(`24d5daa4…`): the r2 recipe (p2061, raster 3856x2568, active 3840x2552, mode 98 read 4784x3190 at
scale 2.0, clamp on), now 8-bit only (the virtual pids are in the 8-bit CinemaDNG block). Entries:
23.98 / 24 / 25 / 29.97 and the virtual 17.98, all on mode 98. Core and UHDX.RCD as r5.

**OG4K on the camera (r6, 2026-11-04): records, but the files are UHD.** The user recorded OG4K at 23.98
and at 17.98; no crash. LOAD.LOG `OCD02020200` (2 found, 2 accepted, 2 rows); the BIN's saved record says
OG4K at the virtual 17.98 (SEL "OG4K", FLAGS 0x70601). But A001_137 (104 frames) and A001_138 (161) are
3856x2170, DefaultCrop 3840x2160, FrameRate 23.976 -- tag for tag the stock UHD / UHDX clip (A001_136), and
16:9 pictures. So the recording path did not take OG4K's raster (canvas_rec 3856x2568) nor the virtual
rate's DNG rate. (Audio length / frame count is no rate measure here: UHDX at 23.98 gives 17.8 too.)
Open: what live view showed, and what the picker handed out at record (recdiag over USB).

**Why r6 recorded UHD: ogc_name's size match picks UHDX (camera, USB, 2026-11-04).** recdiag at OG4K
17.98: the picker's last entry was `UHDX23_98FPS` (pid 2040, mode 231), PBROW 2. ogc_name matches the
request's sizes against every row's active size before it looks at S.CUR; UHDX's active size is stock
UHD's 3840x2160, so the key built for OG4K's recording (base p2061, UHD sizes) got UHDX's label. A
diagnostic format that is stock UHD under a new name collides with UHD itself -- it must not ship beside
other formats (or with stock UHD: a stock UHD clip's playback would say UHDX too).
RAM test: UHDX row (S+0xB74) +0x10 AW := 0 -> the picker hands out `OG4K23_98FPS` (pid 2020, mode 230,
donor 98, vm filled), PBROW 0.

**OG4K's first recording (A001_139, same session, 17.98):** no crash; 53 frames, 3856x2568 8-bit,
DefaultCrop 3840x2552 at (8,8), FrameRate 17.982 -- the format's tags are right. The pictures are not:
frame means jump 16..229 frame to frame, and the frames are mosaics -- the scene appears twice in the left
half (one copy shifted a Bayer phase: green vs magenta), the right half is a different, noisy image,
some frames are washed out pink. Reading: the recorder writes a buffer whose geometry is not the
raster the DNG declares (the 4784x3190 read not scaled to 3856x2568, or a different line pitch), and
exposure is not under control (per-frame brightness swings). Next: what the fp L's recording path takes
the read size / scale / line pitch from (canvas +0xF4..+0x104 were the fp's) and the exposure for mode 230.

**The mosaic: OG4K kept its base profile's downscale (static, 2026-11-04).** Over all stock fp L canvases,
+0xFC..+0x104 is the read's binning (1.0 full, 2.0 2x2, 3.0 ...), not a downscale, and +0x60/+0x64/+0xD0
/+0xD4 hold one value, the read -> raster downscale x 1024 at that crop step: p2001..2005 (read 4784x2700
binned -> 3856x2170) 1269, 1203, 1141, 1084, 1028; p2021.. / p2061 (9568x5382 -> 3856x2170) 2539, ...;
p2081.. (3184 -> 1936) 1684, .... OG4K set the 4784 read and binning 2.0 but kept p2061's 2539: the
picture came out 4784 / 2.48 = 1928 wide (and 1284 high) in a 3856x2568 raster -- the small copy in
A001_139's corner, the rest of the buffer stale memory (the brightness swings). Card r7
(`cards/20261104-rescustom-og4k-r7-resize`, OG4K.RCD `e42a4501…`) sets the four to 1269 (p2001's: the
same 4784 -> 3856 width ratio; 3190 -> 2568 is 1.242, the same within a line) and drops UHDX.RCD.

**OG4K records on the fp L (card r7, 2026-11-04).** A001_140 (23.98, 54 frames) and A001_141 (17.98,
65 frames): 3856x2568 8-bit, DefaultCrop 3840x2552 at (8,8), FrameRate 23.976 / 17.982; clean 3:2
open-gate pictures, edge to edge, frame brightness steady (the earlier swings were the stale buffer).

**Card r8 (2026-11-04): OG48K retried, on OG4K's pattern.** `cards/20261104-rescustom-og48k-r8` = r7 +
`RESCUS\OG48K.RCD` (`ae7584e4…`): base p2061 (video, flagged) instead of the still p1003, 8-bit only,
raster 4784x3184 / active 4768x3168 from mode 98's 4784x3190 binned read, downscale 1023 (1:1, stock's
unscaled value), preview p1003's (1616x1066 / 1590x1056), clamp on. 23.98 / 24 / 25 / 29.97 + 17.98.
Open: the recorder at 4784 wide (stock's widest recording is 4096) and the card rate: 15.2 MB a frame
(UHD 8.4 MB; UHD 23.98 already stops at ~104 frames on this card).

**OG48K records on the fp L (card r8, 2026-11-04).** LOAD.LOG `OCD02020200`. A001_142 (23.98, 23
frames) and A001_143 (17.98, 32 frames): 4784x3184 8-bit (15,312,384 B a frame), DefaultCrop 4768x3168
at (8,8), FrameRate 23.976 / 17.982; clean full-sensor 3:2 pictures, edge to edge, steady exposure. So
the recorder takes 4784 wide -- r1's crash was the mode searches, not the width. The clips are short
(about 1 and 1.8 s): the camera stopped by itself -- the user's test SD card is slow (the 104-frame
UHD clips likewise). Longer takes need a fast card or an external SSD (the fp L supports one; not tried).
Rates for the SSD test (MB/s, decimal): OG48K (15.31 MB a frame) 17.98 ~275, 23.98 ~367, 24 ~367, 25 ~383,
29.97 ~459; OG4K (9.98 MB) ~180 / ~240 / ~240 / ~250 / ~300. The user expects the SSDs to sustain
350-400 MB/s or more.

## 10 / 12-bit (static, 2026-11-04)
Stock UHD 23.98 per depth: p2061 / p2391 / p2721 (8-bit block 2001..2329, 10-bit 2331..2659, 12-bit
2661..2989; empty slots parallel to the 8-bit pool at +330 / +660). Their canvases differ only in +0x80 /
+0x84 (9,10 / 9,9 / 7,7) -- and p2721 reads the 2x-binned 4784 like our formats. The fp's core writes
+0x80 = 10 for 8/10-bit; the fp L's stock value is 9 (OGC_FPL). No firmware code found that classifies
a profile id by block (the classifier flags all of 2001..2989 as 8; the 0xA64 "2660" uses are offsets
and addresses). So one virtual id (8-bit block) for all depths, the depth by the picker's table
(pick8/10/12 -> S.BITLATCH -> canvas +0x80/+0x84), as on the fp. If 10/12-bit record as 8-bit or fail,
next: per-depth ids from the 10/12-bit blocks.
Card r9 (`cards/20261104-rescustom-bitdepth-r9`): core `af0fcc41…`, OG4K.RCD `0c28185d…`, OG48K.RCD
`6feec29c…`, both 8/10/12-bit.
**10 / 12-bit on the camera (r9, 2026-11-04): they record.** OG4K, all 3856x2568: A001_144 (23.98, 10-bit,
66 frames), 145 (23.98, 12-bit, 52), 146 (17.98, 8-bit, 28), 147 (17.98, 10-bit, 23), 148 (17.98, 12-bit,
37). BitsPerSample 10 / 12 with WhiteLevel 1023 / 4095 and BlackLevel 64 / 256 (8-bit: 8 bits, its
4095 / 256 as stock), frame sizes 12,456,960 / 14,932,480 / 9,982,464 B; clean pictures, steady
exposure. So one virtual id in the 8-bit block serves every depth: the depth goes by the picker's table
and canvas +0x80/+0x84. 8-bit still records with +0x80 = 9.

## The frame-rate menu greys every stock rate (static, 2026-11-05)
The user (camera, 2026-11-04): with a RES-Custom format live, the frame-rate list greys every rate but the
virtual 17.98. Cause: `key_rate_row` (ogc.c) finds which stock rate row an entry serves by parsing the
end of its key in the fp's format ("23_98", "24" ... "120", nothing after); the fp L's keys end in
"FPS" (OG4K23_98FPS, OG4K29_97FPS ...), so no entry matched a stock row and `rate_row_ok` greyed all
nine. The virtual rates go by ENT_VRATE, not the key -- hence 17.98 alone. Fix (OGC_FPL): parse digits,
an optional "_" and two digits, then "FPS", and map 23.98 / 24 / 25 / 29.97 / 48 / 50 / 59.94 / 100 /
119.88 to rows 0..8. test_fpl_rescustom compiles the function from ogc.c on the host and checks every
token and near misses (mutation-checked). fp core unchanged (7b575c72). Card r10
(`cards/20261105-rescustom-ratemenu-r10`): core `87134ead…`, the .RCDs as r9. Assumes the fp L's
frame-rate list has the fp's nine rows in that order -- the camera says.
**On the camera (r10, 2026-11-05):** with OG4K live the frame-rate list offers 23.98, 24, 25, 29.97 and the
virtual 17.98 (the user); 48 and up stay greyed (mode 98 tops out at 38.4 fps). So the fp L's list has
the fp's nine rows in the same order.
Clips at 29.97 (r10): A001_152 and A001_153, OG4K 8-bit, 47 frames each, 3856x2568, FrameRate 29.97;
clean pictures. The first OG4K takes at a stock rate other than 23.98.

## 3:2 live view: photo mode's heights (camera + static, 2026-11-05)
The user: with OG4K live, live view (not recording) is the 16:9 picture stretched to 3:2. fnprobe on
FUN_c04398f0 (r1 = the profile id): video live view builds p51 continuously, photo mode p1. Both read
3184x1276 binned 3 / 5 / 5 -- the full sensor height -- and differ only in +0x10 / +0x28 / +0xE0:
p51 1081 / 1071 / 1081 (a 16:9 slice), p1 1276 / 1268 / 0 (every row). ogc_out already shows our rows'
live view in a 3:2 box, so p51's slice came out stretched. RAM test (p51's three column entries at
0xC0C6FCA0 / 0xC0C66C34 / 0xC0C5ABA4 := p1's): 3:2, no stretching (the user's idea: use photo mode's live
view) -- and, being the firmware's table, stock 16:9 distorted; restored. The fix is per format: a
standby group (applied only while the row is live) `LV32` = p51 <- p1's three heights, in OG4K and
OG48K. Test against the stock tables. Card r11 (`cards/20261105-rescustom-liveview-r11`): core as r10
(`87134ead…`), OG4K.RCD `03a921a6…`, OG48K.RCD `c7534e81…`. Only p51 (the uncropped step): the
magnifier / crop steps p52..60 keep theirs.

**Toolchain (2026-11-05).** The Fedora 45 upgrade replaced clang 22.1.8 with 23.1.4 (cores rebuilt
differently: fp L 87134ead -> 99c9d4af, fp 7b575c72 -> 1ca0f36f; the C text grew 102 bytes) and Python
3.14 with 3.15 (the venv broke). Restored without touching the system compiler: Fedora 44's clang
22.1.8 unpacked to ~/.local/opt/clang22 (wrapper `bin/clang`; put it first on PATH for builds), and
python3.14 installed by the user, the venv's python3 pointed at /usr/bin/python3.14. With both, the
cores are byte-identical again (fp 7b575c72, fp L 87134ead).

**Half-press focus stretched the 3:2 live view (camera, 2026-11-05).** pidring.py (a ring of profile
CHANGES at FUN_c04398f0, with S.FLAG / S.CUR): the half-press switches live view to a focus profile
and back -- p1551 one time, p1516 another (by setting) -- and builds p1031 (a 3856x2568 still) too.
Photo mode: live view p1, half-press p1271. Every uncropped video live-view profile (width 1928, no
raster) has a photo twin with the same read and rate, 280 ids lower (p51 <- p1): p1481/1201,
1516/1236, 1551/1271, 1586/1306, 1621..1726/1341..1446 (3184 x 424 / 910 / 2126 / 1276 reads, binned
to the full sensor height); the twin keeps every row, the video one crops to 16:9 (+0x28, and
+0x10/+0xE0/+0xD0/+0x1C/+0x88/+0x8C as the case is). A RAM patch of p1551 alone did nothing (that
half-press used p1516). Fix: fpl_formats LV32, one standby group per distinct set of the twin's
differing fields (6 groups, 9 profiles); MAX_SBY_GROUPS 8 on the fp L (4 on the fp: unchanged).
test_fpl_rescustom derives the table from the image and checks no such profile is left out. Card r12
(`cards/20261105-rescustom-afview-r12`): core `a6a5ddeb…`, OG4K.RCD `167bc794…`, OG48K.RCD
`eaf5c20b…`; fp core 7b575c72.

**The live-view label says UHD (camera, 2026-11-05).** callring.py on the label function's second word
(0xC0437D64; the core's `name` hook owns 0xC0437D60): the only calls that reach the stock code come
from 0xC043BA74 (the recording key builder) with 3840x2160 while stock UHD is live (FLAG 0); with
OG4K live none reach it -- the core answers them all with its label. So the on-screen resolution
label is not this function: the GUI draws it from the resolution setting, which for our rows holds
the stock value 3 (UHD). The brief "DCI 4K" when first switching to a new row: probably the row's own
value (OG4K 8) in the setting before the core's setter moves it to 3 -- to be confirmed. Open.
The user (2026-11-05): the fp L has no DCI 4K resolution setting of its own, so OG4K's 8 / OG48K's 10
collide with nothing. Label behaviour (the user): any resolution -> OG48K shows "DCI 4K"; OG48K ->
OG4K stays "DCI 4K"; UHD -> OG4K stays "UHD"; FHD -> OG4K "DCI 4K". Reading: the label refreshes only
when its 4K class changes, and our values read as "DCI 4K" when it does. Cosmetic; to find where the
live-view label is drawn.
**On the camera (r12, 2026-11-05):** half-press focus with OG4K stays 3:2 (the user); stock 16:9
live view and focus are normal.
