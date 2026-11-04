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
| redesign (different data model) | picker |

Code changes for the fp L besides addresses: angtv's replay; ogc.c's G_MAG constant (return v + 8); leave out
v32/binpath; the picker.
