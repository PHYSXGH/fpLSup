"""fp L (IMX455) formats for res-custom: port phase 3 (projects/fpl-port/RESCUSTOM_PORT.md).

OG48K is the fp's OG3K recipe carried over, piece for piece:

  fp OG3K                                     fp L OG48K
  donor M98: full sensor, 2x2 binned         donor 98: full sensor, 2x2 binned
    3032x2012 read                             4784x3190 read (imx455_modes.csv; geometry out 4768x3168)
  base profile p83: the stock S still         base profile p1003: the stock 4768x3168 still
    (3:2, raster 3032x2012, out 3008x2000,      (3:2, raster 4784x3184, out 4768x3168, no classifier
    no classifier flag)                         flag: 990..1770 are unflagged)
  canvas: raster = rec, +0x90 = 1, +0xC0 = 0  the same, and the sensor read area / scale switched to the
    (the video values)                          binned readout (p1003 reads the full sensor unbinned for
                                                stills: +0xF4/+0xF8 9568x6380, scale 1.0; the stock binned
                                                profiles say 4784x3190, scale 2.0, as the fp's p83 does)
  video clamp on (stills donor)               the same: on the fp L too only video modes have the
                                                receiver row's +0x04 bit 3 (0xC0B94BBC)
  rates up to the mode's ceiling              23.98 / 24 / 25 / 29.97 (mode 98 tops out at 38.4 fps);
                                                29.97 solves to exactly the firmware's own mode 3
                                                (hmax 580, tail 620, vmax 4142)

Live view: no preview group (prev_h 0) -- the fp's preview profiles are fp ids.  Not on the camera yet:
every value here is static reading, the first card is the test.
"""
import struct

import ogc_layout as L

LABEL = 'OG48K'
DONOR = 98
DONOR_TIMING = (0x02440244, 0x000E0C9E)       # hmax 580 | tail 580, vmax 3230 | x 14 (the image's)
BASE_PROFILE = 1003
REC = (4784, 3184)                            # the base's raster: inside the 4784x3190 read
ACT = (4768, 3168)                            # mode 98's own output size, 3:2 to 0.3 %
READ = (4784, 3190)
SCALE_2 = 0x40000000                          # 2.0f
MAXRATE = 3843                                # 72 MHz / (580 x 3229 + 580): 38.43 fps


def _f(x):
    return struct.unpack('<I', struct.pack('<f', x))[0]


# OG4K: Jose Hurtado's fp OG4K recipe (jose_formats.py og4k: base p171, the stock UHD video profile;
# raster 3840x2560 downscaled from a full-sensor read; UHD's resolution value) on the IMX455:
#   base p2061       the stock UHD 23.98 8-bit CinemaDNG profile at crop 1.00 (video, classifier flag 8
#                    as Jose's p171 on the fp)
#   raster / preview p1004's, the stock 3840x2552 still: raster 3856x2568, active 3840x2552, preview
#                    1296x861 / 1280x851 -- 9.9 Mpx, no wider than UHD's 3856 (Jose's: 9.8 Mpx)
#   read             mode 98's binned 4784x3190, scale 2.0, downscaled 1.24x on both axes
OG4K_RASTER = (3856, 2568)
OG4K_ACT = (3840, 2552)
OG4K_BASE = 2061

ROWS = {
    # 2026-11-04, card 20261104-rescustom-og48k-r1, the user: live view showed the 3:2 open gate, but
    # recording (17.98) CRASHED the camera at once (colourful lines, battery pull). Its raster is 4784
    # wide -- the recording engine's stock maximum is UHD's 3856 (FHD reads 3184 and records 1936; Jose's
    # fp OG4K is 3840 wide). Not built (FORMATS); kept as the record of what failed.
    'og48k': dict(
        label=LABEL, profile=BASE_PROFILE, enum=10,            # uishare ui/enums.py 'OG48K'
        stock_value=2, aspect=2, flags=L.RFLAG_CLAMP,
        rec=list(REC), act=list(ACT), prev_h=0,
        modes=[(DONOR, MAXRATE, DONOR_TIMING[0] & 0xFFFF, 0, DONOR_TIMING[1] >> 16)],
        canvas_rec=[(0x00, REC[0]), (0x04, REC[1]), (0x90, 1), (0xC0, 0),
                    (0xF4, READ[0]), (0xF8, READ[1]),
                    (0xFC, SCALE_2), (0x100, SCALE_2), (0x104, SCALE_2)],
        canvas_pb=[(0x0C, REC[0]), (0x10, REC[1]), (0x1C, 2), (0x20, ACT[0]), (0x28, ACT[1]),
                   (0xD8, REC[0]), (0xE0, REC[1]), (0xF4, REC[0]), (0xF8, REC[1])],
        rate_canvas=[],
        row_text='%s %dx%d' % (LABEL, ACT[0], ACT[1]), summary=LABEL,
        bit_depths=(8, 10, 12),
    ),
    # UHDX (diagnostic, 2026-11-04): stock UHD under a new name -- the UHD 23.98 sensor mode 161 with its
    # own timing, the stock UHD 8-bit video profile p2061, no canvas change, 16:9, no clamp.  Every
    # res-custom path runs (menu row, picker hooks, virtual profile, virtual mode); nothing about the
    # image changes.  Records -> the core works and the open-gate content is the problem; crashes -> the
    # core's recording path on the fp L.
    'uhdx': dict(
        label='UHDX', profile=2061, enum=11,                    # uishare ui/enums.py 'UHDX'
        stock_value=3, aspect=3, flags=0, video_base=True,
        donor_timing=(161, 0x03EC020C, 0x001C1662),             # hmax 524 | tail 1004, vmax 5730 | x 28
        rec=[3856, 2170], act=[3840, 2160], prev_h=0,
        modes=[(161, 2398, 524, 0, 28)],
        # the stock 23.98 timing exactly (the solver gives the same frame as vmax 5731 / tail 480)
        capture_timing=[(2398, 0, 0x03EC020C, 0x001C1662, 0x41C00000, 24)],
        canvas_rec=[(0x90, 1)],                                 # p2061's own value: no change
        canvas_pb=[(0x1C, 1)],                                  # p2061's own value: no change
        rate_canvas=[],
        row_text='UHDX 3840x2160', summary='UHDX',
        bit_depths=(8,),                  # the virtual ids are in the 8-bit CinemaDNG block (ogc_layout)
    ),
    'og4k': dict(
        label='OG4K', profile=OG4K_BASE, enum=8,                # uishare ui/enums.py 'OG4K' (Jose's value)
        stock_value=3, aspect=2, flags=L.RFLAG_CLAMP, video_base=True,
        rec=list(OG4K_RASTER), act=list(OG4K_ACT), prev_h=0,
        modes=[(DONOR, MAXRATE, DONOR_TIMING[0] & 0xFFFF, 0, DONOR_TIMING[1] >> 16)],
        canvas_rec=[(0x00, OG4K_RASTER[0]), (0x04, OG4K_RASTER[1]),
                    (0x0C, 1296), (0x10, 861), (0x20, 1280), (0x28, 851),     # p1004's preview
                    (0x24, OG4K_ACT[0]), (0x2C, OG4K_ACT[1]),
                    (0xDC, OG4K_RASTER[0]), (0xE4, OG4K_RASTER[1]),
                    (0xF4, READ[0]), (0xF8, READ[1]),
                    (0xFC, SCALE_2), (0x100, SCALE_2), (0x104, SCALE_2)],
        canvas_pb=[(0x0C, OG4K_RASTER[0]), (0x10, OG4K_RASTER[1]), (0x1C, 2),
                   (0x20, OG4K_ACT[0]), (0x28, OG4K_ACT[1]),
                   (0xD8, OG4K_RASTER[0]), (0xE0, OG4K_RASTER[1]),
                   (0xF4, OG4K_RASTER[0]), (0xF8, OG4K_RASTER[1]),
                   (0x60, 1024), (0xD0, 1024), (0x64, 1024), (0xD4, 1024)],
        rate_canvas=[],
        row_text='OG4K %dx%d' % OG4K_ACT, summary='OG4K',
        bit_depths=(8, 10, 12),
    ),
}


def check(image, target):
    """the static facts this file rests on, against the fp L image"""
    w = lambda a, n=1: struct.unpack_from('<%dI' % n, image, a - 0xC0000000)    # noqa: E731
    row = ROWS[target]
    tt = 0xC0B90FF8
    rows = {w(tt + 0x20 * i)[0]: w(tt + 0x20 * i, 3) for i in range(85)}
    donor, *timing = row.get('donor_timing', (DONOR,) + DONOR_TIMING)
    if rows.get(donor, (0,))[1:] != tuple(timing):
        raise ValueError(f'{target}: mode {donor} timing differs from {timing}')
    if any(m[0] != donor or m[2] != timing[0] & 0xFFFF or m[4] != timing[1] >> 16 for m in row['modes']):
        raise ValueError(f'{target}: the modes do not carry mode {donor}\'s hmax / x')
    pid = row['profile']
    if w(0xC0BF6820 + 4 * pid)[0] == 0xFFFFFFFF:
        raise ValueError(f'{target}: p{pid} has no mapping row')
    flagged = any(lo <= pid <= hi for lo, hi in L.PROFILE_CLASSES)
    if flagged != bool(row.get('video_base')):
        raise ValueError(f'{target}: p{pid} classifier flag {flagged}, expected {bool(row.get("video_base"))}')


def row_data(target, tmp, image):
    """ogc_rowdata's dict for an fp L format, with its menu pack"""
    import build_og3k_ui_candidate as UI
    check(image, target)
    row = {k: v for k, v in ROWS[target].items() if k not in ('video_base', 'donor_timing')}
    old = UI.PLAN_TARGET
    try:
        UI.PLAN_TARGET = {'label': row['label'], 'act': tuple(row['act'])}
        pack, _ = UI.assets(tmp, names={'OG3K_QS': row['label'] + '_QS', 'OG3K_SET': row['label'] + '_SET',
                                        'OG3K_FONT': row['label'] + '_FONT'})
    finally:
        UI.PLAN_TARGET = old
    row['pack'] = pack
    return row
