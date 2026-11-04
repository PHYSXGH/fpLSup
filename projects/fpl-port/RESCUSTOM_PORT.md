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
