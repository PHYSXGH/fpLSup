# IMX455 sensor modes on the fp L (Ver.3.02)

The fp L's 85 sensor readout modes, grouped by readout, with the sensor area each one covers. Static
reading of the firmware image (`out_fpl/MAIN_c0000000.bin`), 2026-11-06.

The sensor is 9568 x 6380. **Max fps** is computed from each mode's line timing at 72 MHz
(`72e6 / (hmax x (vmax - 1) + tail)`). **Crop** is relative to the full sensor width. **Sensor area**
is the read size multiplied by the binning, and **Aspect** is that area's aspect.

## Where the numbers come from

- **Mode table** (`imx455_modes.csv`, from `tools/imx455_modes.py`): one row per mode id. It gives
  the read width and lines, the HORIZONTAL binning, the photo output size, the stock frame rate, and
  the timing words (hmax, tail, vmax). Its order is the timing table's (0xC0B90FF8, 85 rows, 0x20 each).
- **Binning across x down** comes from each mode's register record: the 0x460-byte records at
  REGDESC 0xC0B98DE0 {base 0xC0B98DE8, 85}, in mode order, hold 280 settings words; word **+0x08**
  is the readout code, one value per binning:

  | +0x08 | binning |
  |---|---|
  | 0x40, 0x80, 0xA0 | 1x1 |
  | 0x86 | 2x2 |
  | 0x88, 0x89 | 3x3 |
  | 0x8E, 0x8F | 3x5 |
  | 0xB4 | 3x7 |
  | 0xB6 | 3x9 |
  | 0xB8 | 3x15 |

  Found by pairing 3290 recording entries {type, profile, mode, key*} with their profiles' canvas
  (+0xFC binning across, +0x100 down; `tools/canvas_compare.py`): 55 modes got a known binning, and
  +0x08 is the only word that separates every binning across them. It then gives the other 30
  modes theirs; all 11 codes in the table are among the known ones. Live view's mode 9 is 3x5.

## Full sensor width

| Read | Binning (across x down) | Sensor area | Mode ids | Stock rates | Max fps | Aspect | Used by |
|---|---|---|---|---|---|---|---|
| 9568x6380 | 1x1 | **9568x6380** (whole sensor) | 0, 142, 97 | 9, 10, 17 | 17.92 | 3:2 | - |
| 9568x5382 | 1x1 | 9568x5382 | 159-161 | 23.98-25 | 25.00 | 16:9 | stock UHD |
| 4784x3190 | 2x2 | **9568x6380** (whole sensor) | 3, 98, 143 | 29.97, 38, 10 | 38.43 | 3:2 | **OG4K, OG48K** (98) |
| 4784x2700 | 2x2 | 9568x5400 | 155-158 | 23.98-29.97 | 29.97 | 16:9 | **U48K** |
| 4784x1700 | 2x2 | 9568x3400 | 188-195 | 23.98-59.94 | 59.94 | 2.81:1 | **W48K** |
| 4784x1596 | 2x2 | 9568x3192 | 215 | 59.94 | 59.94 | 3:1 | - |
| 3184x2126 | 3x3 | 9552x6378 (whole sensor) | 4, 8 | 29.97, 59.94 | 59.94 | 3:2 | focus live view |
| 3184x2124 | 3x3 | 9552x6372 (whole sensor) | 204, 217 | 57.5, 10 | 57.52 | 3:2 | - |
| 3184x1796 | 3x3 | 9552x5388 | 166-173 | 23.98-59.94 | 59.94 | 16:9 | stock FHD |
| 3184x1276 | 3x5 | 9552x6380 (whole sensor) | 9, 117, 148-150 | 59.94-100 | 100.00 | 3:2 | normal live view (9) |
| 3184x1276 | 3x3 | 9552x3828 | 205-208 | 70-100 | 100.00 | 2.5:1 | - |
| 3184x1180 | 3x3 | 9552x3540 | 175-183 | 23.98-100 | 100.00 | 2.7:1 | stock FHD |
| 3184x1090 | 3x5 | 9552x5450 | 154, 174, 209 | 100, 119.88 | 119.88 | 16:9 | stock FHD high speed |
| 3184x1090 | 3x3 | 9552x3270 | 153, 210 | 119.88 | 119.88 | 2.9:1 | stock FHD high speed |
| 3184x910 | 3x7 | 9552x6370 (whole sensor) | 11 | 119.88 | 119.88 | 3:2 | - |
| 3184x580 | 3x9 | 9552x5220 | 211 | 239.76 | 239.76 | 1.83:1 | - |
| 3184x580 | 3x7 | 9552x4060 | 212 | 239.76 | 239.76 | 2.35:1 | - |
| 3184x540 | 3x5 | 9552x2700 | 213 | 237.2 | 237.23 | 3.5:1 | - |
| 3184x540 | 3x3 | 9552x1620 | 214 | 235.6 | 235.57 | 5.9:1 | - |
| 3184x424 | 3x15 | 9552x6360 (whole sensor) | 12 | 239.76 | 239.76 | 3:2 | - |

## Cropped reads

| Read | Binning | Sensor area | Mode ids | Stock rates | Max fps | Crop | Aspect | Used by |
|---|---|---|---|---|---|---|---|---|
| 8208x4320 | 1x1 | 8208x4320 | 184-187 | 23.98-29.97 | 29.97 | 1.17 | 1.90:1 | stock UHD crop steps |
| 8208x2160 | 1x1 | 8208x2160 | 216 | 59.94 | 59.94 | 1.17 | 3.8:1 | - |
| 3184x2124 | 2x2 | 6368x4248 | 131, 146 | 38, 10 | 38.43 | 1.50 | 3:2 | - |
| 6288x4192 | 1x1 | 6288x4192 | 129, 145, 130 | 9, 10, 17 | 17.92 | 1.52 | 3:2 | - |
| 6288x3528 | 1x1 | 6288x3528 | 162-165 | 23.98-29.97 | 29.97 | 1.52 | 16:9 | - |
| 6288x2174 | 1x1 | 6288x2174 | 196-203 | 23.98-59.94 | 59.94 | 1.52 | 2.89:1 | - |

## Notes

- **Whole sensor:** four readouts cover the entire 3:2 sensor at different binning: 1x1 (~61 MP,
  up to 17.9 fps), 2x2 (OG48K's, 38 fps), 3x3 (57-60 fps), and the very fast 3x7 / 3x15 reads.
- **Uneven binning** (3x5, 3x7, 3x9, 3x15) skips more rows than columns, so the raw pixels are not
  square: fine for live view, but a recorded frame would need vertical resampling.
- **Modes that differ only in frame length:** within a group, the modes share hmax (580 for the
  4784-wide reads) and differ in vmax / tail, which is why one donor mode serves all of a format's
  rates (W48K: 188 for 188..195; U48K: 155 for 155..158). The capture-timing section can still give
  each rate SIGMA's own words (`fpl_formats.stock_timing`).
- **A RES-Custom format** names a donor mode; the core makes one virtual mode (ids 230..) that clones
  the donor's rows from every per-mode table (RESCUSTOM_PORT.md). Up to 6 formats on the menu at once,
  16 .RCD files read, 18 virtual profile ids, 16 virtual modes.
- **Candidates not used yet:** the full-resolution 9568x6380 open gate (1x1, up to 17.9 fps,
  ~61 MB a frame at 8-bit); the 1.52x crop at 6288x4192 (1x1, 17.9 fps); the 1.5x crop 3:2 binned
  (3184x2124 2x2, mode 131, 38 fps).
