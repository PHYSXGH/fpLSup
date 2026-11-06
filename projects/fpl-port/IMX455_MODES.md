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
- **Vertical binning** is not in the mode table. It comes from the recording/live-view profiles'
  canvas: +0xF4 / +0xF8 is the read area, +0xFC the binning across, +0x100 the binning down
  (`tools/canvas_compare.py` reads the canvas columns). Four read sizes appear with two different
  vertical factors (3184x1276, 1090, 580, 540). The profiles do not say which mode id goes with
  which, so those rows list both.
- Reads that no stock profile uses (4784x1596, 8208x2160, 3184x2124 2x2, 6288x4192, 6288x3528)
  assume the same binning down as across (marked *).

## Full sensor width

| Read | Binning (across x down) | Sensor area | Mode ids | Stock rates | Max fps | Aspect | Used by |
|---|---|---|---|---|---|---|---|
| 9568x6380 | 1x1 | **9568x6380** (whole sensor) | 0, 142, 97 | 9, 10, 17 | 17.92 | 3:2 | - |
| 9568x5382 | 1x1 | 9568x5382 | 159-161 | 23.98-25 | 25.00 | 16:9 | stock UHD |
| 4784x3190 | 2x2 | **9568x6380** (whole sensor) | 3, 98, 143 | 29.97, 38, 10 | 38.43 | 3:2 | **OG4K, OG48K** (98) |
| 4784x2700 | 2x2 | 9568x5400 | 155-158 | 23.98-29.97 | 29.97 | 16:9 | **U48K** |
| 4784x1700 | 2x2 | 9568x3400 | 188-195 | 23.98-59.94 | 59.94 | 2.81:1 | **W48K** |
| 4784x1596 | 2x2 * | 9568x3192 | 215 | 59.94 | 59.94 | 3:1 | - |
| 3184x2126 | 3x3 | 9552x6378 (whole sensor) | 4, 8 | 29.97, 59.94 | 59.94 | 3:2 | focus live view |
| 3184x2124 | 3x3 | 9552x6372 (whole sensor) | 204, 217 | 57.5, 10 | 57.52 | 3:2 | - |
| 3184x1796 | 3x3 | 9552x5388 | 166-173 | 23.98-59.94 | 59.94 | 16:9 | stock FHD |
| 3184x1276 | 3x5 / 3x3 | 9552x6380 / 9552x3828 | 9, 117, 148-150, 205-208 | 59.94-100 | 100.00 | 3:2 / 2.5:1 | live view (3x5) |
| 3184x1180 | 3x3 | 9552x3540 | 175-183 | 23.98-100 | 100.00 | 2.7:1 | stock FHD |
| 3184x1090 | 3x5 / 3x3 | 9552x5450 / 9552x3270 | 153, 154, 174, 209, 210 | 100, 119.88 | 119.88 | 16:9 / 2.9:1 | stock FHD high speed |
| 3184x910 | 3x7 | 9552x6370 (whole sensor) | 11 | 119.88 | 119.88 | 3:2 | - |
| 3184x580 | 3x9 / 3x7 | 9552x5220 / 9552x4060 | 211, 212 | 239.76 | 239.76 | 1.83:1 / 2.35:1 | - |
| 3184x540 | 3x5 / 3x3 | 9552x2700 / 9552x1620 | 213, 214 | 237.2, 235.6 | 237.23 | 3.5:1 / 5.9:1 | - |
| 3184x424 | 3x15 | 9552x6360 (whole sensor) | 12 | 239.76 | 239.76 | 3:2 | - |

## Cropped reads

| Read | Binning | Sensor area | Mode ids | Stock rates | Max fps | Crop | Aspect | Used by |
|---|---|---|---|---|---|---|---|---|
| 8208x4320 | 1x1 | 8208x4320 | 184-187 | 23.98-29.97 | 29.97 | 1.17 | 1.90:1 | stock UHD crop steps |
| 8208x2160 | 1x1 * | 8208x2160 | 216 | 59.94 | 59.94 | 1.17 | 3.8:1 | - |
| 3184x2124 | 2x2 * | 6368x4248 | 131, 146 | 38, 10 | 38.43 | 1.50 | 3:2 | - |
| 6288x4192 | 1x1 * | 6288x4192 | 129, 145, 130 | 9, 10, 17 | 17.92 | 1.52 | 3:2 | - |
| 6288x3528 | 1x1 * | 6288x3528 | 162-165 | 23.98-29.97 | 29.97 | 1.52 | 16:9 | - |
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
