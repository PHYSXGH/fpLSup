# The focal-length cap on the fp L: back on, following the camera

**Status (2026-11-03, later the same day):** the cap is **on** again for the fp L
(`fwtarget.SENSOR['fpl']['focal_uncapped'] = False`): full-width modes count 9520 columns, the still image's
width. Reason: the camera's own crop records put 1.00× at 9520 × 6328, and every crop step's DNG
(1.05 … 2.48×) scales its FocalPlaneXResolution against 9520 exactly (`LENS_TABLES.md`, "Crop"). With the cap
off, the profile's focal jumped by 9568 / 9024 = 1.060 from 1.00× to 1.05× where the camera's jumps by
1.055. This is the camera's convention, not a measurement of the picture; the test below would still say
what the frame really shows. The history follows.

## What the cap is

The profile turns the lens's focal length into pixels:

```
focal_px = frame width (px) × focal length (mm) / width of sensor the frame shows (mm)
```

The width of sensor the frame shows is `covered × pixel pitch`, where `covered` is the number of sensor
columns the mode reads: readout width × binning, from the camera's own mode table.

The fp code caps `covered` at the active width, the width of the full-resolution still image:

```
covered = min(readout × binning, active width)      # gcsv_json.S j_covered
```

The fp code's reasoning: a mode that reads past the active area "still images only the active area", i.e. the
border columns outside the still image are assumed not to end up in the video frame.

## Why it matters on the fp L

| | columns |
|---|---|
| readable (full readout) | 9568 |
| active (the still image: 9568 read → 9520 out) | 9520 |
| FHD modes (readout 3184 at binning 3) | 3184 × 3 = **9552** |

The FHD modes read 32 columns more than the still image. The camera scales those 3184 binned columns to the
1936-px CinemaDNG frame. Whether the frame shows all 9552 columns or only 9520 depends on whether the camera
trims before scaling, and that isn't known.

For take A001_100 (FHD 23.976, mode 173, SIGMA 45mm F2.8 at 45 mm, 1936 × 1090 frame):

| assumption | covered | focal_px |
|---|---|---|
| cap (the fp convention) | 9520 | 2433.5 |
| **no cap (now on the fp L)** | 9552 | **2425.4** |
| the DNG's own EXIF (FocalPlaneXResolution 1362.42 px/in) | nominal: the 1920 crop = 9520 columns | 2413.7 |

The capped and uncapped values differ by 0.33%. In Gyroflow that scales how far each rotation is
corrected, by the same 0.33%: small but systematic. Only modes that read past 9520 columns are affected
(the binning-3 modes, 9552); for every other mode the two give the same number. The crop factor still uses
the cap, so it stays 1.000.

The EXIF value is nominal rather than physical. It equates the 1920 crop with the full 9520 still width,
which would make the 1936 frame span ~9600 columns, more than the mode reads.

## How to test it later

The question is how many sensor columns the FHD frame actually shows. Compare the same scene in a still and
in FHD:

1. Tripod, a static scene with sharp detail near **both left and right edges** (a ruler, a test chart, a
   doorframe). Fixed focus, same lens and focal length.
2. Take a full-resolution still (9520 px wide), then an FHD CinemaDNG take (1936 px wide) without moving the
   camera.
3. Find the same two features near the left and right edges in both images, and their x positions.
4. Scale: `columns per FHD pixel = (still distance in px) / (FHD distance in px)`. Then
   `columns the FHD frame spans = 1936 × that`.
   - ≈ **9552**: the frame shows the whole readout; **no cap is right** (current fp L setting).
   - ≈ **9520** (or ~9600 per the EXIF): the frame is trimmed; restore the cap by setting
     `focal_uncapped: False` for `fpl` in `fpSup/fp_usb_shell/fwtarget.py`, and rebuild.
5. Note the result here and in `cards/README.md`.

Alternatively, a Gyroflow calibration of the same lens on an FHD take gives a measured focal_px to compare
against 2425.4 / 2433.5.

The same question applies to the fp's own modes that read 6064 columns (capped at 6000 there). It was never
tested on the fp either.

## Evidence from the camera itself (2026-11-03)

The fp L's crop records (`LENS_TABLES.md`, "Crop") put the 1.00× frame at **9520 × 6328**, and the DNGs'
FocalPlaneXResolution for the 1.53 / 2.0 / 2.5× crops is the 1.00× value × 9520 / crop width exactly. So the
camera's own convention for full-width video is 9520 columns: the cap. That is what the camera assumes,
not a measurement of the picture; the still-vs-video test above would still settle what the frame shows.
