# fp L port (SIGMA fp 5.02 → fp L 3.02)

Goal: make the fpSup cards, the USB shell and the research tools run on the fp L.
The two firmwares are built from the same source (`w71c1` = fp, `w91c1` = fp L);
the fp L changes the sensor (IMX410 → IMX455: higher resolution, PDAF).

## Setup

```
python3 -I projects/fpl-port/tools/unpack_fw.py firmware/FP__V502.bin out        # fp, the existing out/ convention
python3 -I projects/fpl-port/tools/unpack_fw.py firmware/FPL_V302.bin out_fpl    # fp L
python3 -m venv projects/fpl-port/.venv && projects/fpl-port/.venv/bin/pip install capstone unicorn keystone-engine numpy
PY=projects/fpl-port/.venv/bin/python
$PY -I projects/fpl-port/tools/anchor_map.py out/MAIN_c0000000.bin out_fpl/MAIN_c0000000.bin out_fpl/anchor_runs.json
$PY -I projects/fpl-port/tools/addrmap.py build        # pointer pairs -> out_fpl/ptr_points.json, ram_runs.json
$PY -I projects/fpl-port/tools/addrmap.py 0xC0BAC2F8   # translate one address
$PY -I projects/fpl-port/tools/port_table.py fpSup     # -> addr_table.csv
```

`out/` and `out_fpl/` are ignored (firmware-derived). `addr_table.csv` holds addresses only.

## How addresses are translated (`tools/addrmap.py`)

| method | where it applies | how |
|---|---|---|
| `exact` | code/data that is byte-identical | unique 32-byte windows in both images, longest increasing chain, merged into 438 constant-delta runs covering 95.8% of MAIN |
| `window` | `.data` that holds pointers | pointer words in a window are translated, the window is searched in fp L |
| `ptr`, `ptr-between` | BSS / data / RAM | every literal-pool load and `movw`/`movt` pair in matched code gives a (fp value, fp L value) pair |
| `ptr-base-0xNN?` | BSS fields | delta of the nearest referenced struct base below — a guess |
| `fuzzy a/b` | code that changed | best halfword similarity near the expected place (a = best, b = runner-up) |

Methods are compared; disagreement is flagged `CONFLICT`.

## First results (2026-11-02)

- Example (all checks agree): the shell's echo slot `0xC0BAC2F8` → `0xC0BD2544`, and that slot in
  fp L holds the mapped echo handler `0xC03D9BB8`.
- `fpSup/` uses 2,910 distinct addresses: 2,651 high, 208 medium, 38 low, 13 none.
- Whole repo (`fpSup projects research`): 14,062 addresses, 11,768 high.
- RAM: BSS mostly keeps the same addresses, but parts move (for example the pool pointer `0xC3757A7C` → `0xC37588BC`
  from a single vote; `0xC37CE210` → `0xC37CDCD8`). Heap and fixed buffers that the code never names
  cannot be derived offline.
- What doesn't translate is mostly sensor-specific code (the `XC_ImageSensorIMX410` vtable, register
  tables, open-gate and res-lab hooks such as `0xC043A19C` and `0xC043B6A4`). On the fp L that is IMX455
  code, so it needs new reverse engineering, not just new addresses.

## Not yet checked

- ~~The cave~~: checked 2026-11-02. The zero run at fp 0xC072DE64 is the same length in the fp L at
  0xC072B8E4 (−0x2580), the whole block 0xC072D000..0xC0735000 moves by −0x2580, and no literal-pool or
  movw/movt constant in either image points into the zero run. Static evidence only.
- The loader, stage2 and power-off write-back have run under unicorn against the fp L image (see below).
  Nothing has run on an fp L camera yet.

## The fp L build target (2026-11-02)

`FPSUP_CAMERA=fpl` selects the fp L for any build; unset or `fp`, everything builds as before
(checked byte for byte: gyro base and gcsv cards, debug; all `fp_usb_shell` tests and the gyro offline
tests have the same results as before the change).

- `fpSup/fp_usb_shell/fwtarget.py`: the target, `fw(addr)` for Python constants, and the assembly rewrite.
- `fpSup/fp_usb_shell/cameras/fpl302.tsv`: the one address table. `auto` rows come from
  `tools/gen_table.py`; `checked` rows were read by hand (the note says how); `verify` rows have the best
  evidence available and need confirming on the camera; `todo` rows are unmapped, and using one stops the build.
- `armasm.py`: for a non-fp target it preprocesses, rewrites every 0xC…–0xCF… constant through the table, and
  assembles. An unmapped address in a `.equ` gets a poison value, and the build fails if poison reaches the code.
  Defines come from Python already translated and are not rewritten again.
- Python on the build path writes its constants as `fw(0x…)` (`tools/wrap_fw.py` did it mechanically).
- Refused on the fp L until checked on the camera: `--store-boot` / `--loader-hook` (Fast Start writes the
  flash-backed settings block, whose fp L address is inferred).
- Gyro: on the fp L the lens profile `.json` is left out (`FPGYRO_NO_LENS_JSON`). Its readout time, frame
  timing and crop come from IMX410 mode tables, so on the IMX455 it would write numbers Gyroflow trusts and
  that are wrong. The `.GYR`/`.gcsv` log does not depend on the sensor.
- Hook sites (accel, rec start, rec stop, mode) and the F_WRITE restore site: the instructions are identical in
  both images.
- `tools/card_check.py FP_CARD FPL_CARD`: the structural check. `tools/sbs.py`, `tools/evidence.py`: what the
  hand review used.

Test cards and the camera plan: [cards/README.md](cards/README.md).

## Differences the address table can't catch

The table maps addresses. Memory-map facts are kept separately in `fwtarget.MEMORY`:

- RAM size and the uncached mirror: fp 1 GB with the mirror at +0x40000000, fp L 2 GB with no mirror
  (found 2026-11-02 when the USB shell echoed its own commands; see cards/README.md).

To look for more: constants in 0x40000000–0xBFFFFFFF that differ at matched code (one such pass found
0x80000000 → 0xC0000000 in FUN_c001ed2c).
