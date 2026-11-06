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
# 3:2 live view (camera, 2026-11-05; the user's idea: use photo mode's live view).  Every uncropped
# video live-view profile reads the full sensor height and crops it to 16:9; photo mode has a twin
# with the same read that keeps every row (p51 <- p1; the focus profiles p1481.. <- p1201.., 280 ids
# lower).  While a 3:2 row is live each video profile gets its twin's differing fields (a standby
# group; stock 16:9 keeps its own).  Seen on the camera: p51 (live view), p1551 / p1516 (half-press,
# by setting).  test_fpl_rescustom derives the same table from the image.
LV_TWINS = [(51, 1), (1481, 1201), (1516, 1236), (1551, 1271), (1586, 1306),
            (1621, 1341), (1656, 1376), (1691, 1411), (1726, 1446)]
LV32 = [([51], [(0x10, 1276), (0x28, 1268), (0xE0, 0)], 0),
        ([1481], [(0x1C, 2), (0x28, 422), (0x88, 4), (0x8C, 4)], 0),
        ([1516], [(0x1C, 2), (0x28, 906), (0x88, 4), (0x8C, 2)], 0),
        ([1551], [(0x10, 1290), (0x1C, 2), (0x28, 1280), (0xD0, 1687), (0xE0, 0)], 0),
        ([1586], [(0x10, 1276), (0x1C, 2), (0x28, 1266), (0xD0, 1706)], 0),
        ([1621, 1656, 1691, 1726], [(0x1C, 2), (0x28, 1266)], 0)]
OG4K_RASTER = (3856, 2568)
OG4K_ACT = (3840, 2552)
OG4K_BASE = 2061
OG48K_RESIZE = 1023                # 1:1 (read 4784 -> raster 4784): stock's unscaled value (p2019, p1002..)
OG4K_RESIZE = 1269                 # stock p2001 (read 4784x2700 -> raster 3856x2170, crop 1.00)

ROWS = {
    # r1 (2026-11-04, base p1003, profile pool 34.., 8/10/12-bit) crashed at record start -- every
    # format did until cb0b6b24 (the IMX455-only mode searches).  Now on OG4K's working pattern (r7):
    # video base p2061, the 8-bit CinemaDNG pool, the downscale field set (1:1 here: 4784 -> 4784).
    # Open: the recorder at 4784 wide (stock records at most 4096) and the card's rate (15.2 Mpx a frame).
    'og48k': dict(
        label=LABEL, profile=OG4K_BASE, enum=10,               # uishare ui/enums.py 'OG48K'
        stock_value=3, aspect=2, flags=L.RFLAG_CLAMP, video_base=True,
        rec=list(REC), act=list(ACT), prev_h=0,
        modes=[(DONOR, MAXRATE, DONOR_TIMING[0] & 0xFFFF, 0, DONOR_TIMING[1] >> 16)],
        canvas_rec=[(0x00, REC[0]), (0x04, REC[1]),
                    (0x0C, 1616), (0x10, 1066), (0x20, 1590), (0x28, 1056),     # p1003's preview
                    (0x24, ACT[0]), (0x2C, ACT[1]),
                    (0xDC, REC[0]), (0xE4, REC[1]),
                    (0xF4, READ[0]), (0xF8, READ[1]),
                    (0xFC, SCALE_2), (0x100, SCALE_2), (0x104, SCALE_2),
                    (0x60, OG48K_RESIZE), (0x64, OG48K_RESIZE), (0xD0, OG48K_RESIZE), (0xD4, OG48K_RESIZE)],
        canvas_pb=[(0x0C, REC[0]), (0x10, REC[1]), (0x1C, 2),
                   (0x20, ACT[0]), (0x28, ACT[1]),
                   (0xD8, REC[0]), (0xE0, REC[1]),
                   (0xF4, REC[0]), (0xF8, REC[1]),
                   (0x60, 1024), (0xD0, 1024), (0x64, 1024), (0xD4, 1024)],
        rate_canvas=[],
        standby=LV32,
        row_text='%s %dx%d' % (LABEL, ACT[0], ACT[1]), summary=LABEL,
        # 10/12-bit: one virtual profile id (the 8-bit CinemaDNG block) for all three; the depth goes
        # by the picker's table (pick8/10/12) into canvas +0x80/+0x84, as stock p2061/p2391/p2721
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
    # 2026-11-04 (card r2): crashed at record start -- the IMX455-only mode searches (lk_x3c/x5c/x0c,
    # fixed in cb0b6b24), not the content.  Card r6 retries it with that core, beside UHDX.
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
                    (0xFC, SCALE_2), (0x100, SCALE_2), (0x104, SCALE_2),
                    # the read -> raster downscale x 1024 (one value, all four): p2061's 2539 is
                    # 9568 -> 3856; ours is the 2x-binned 4784 -> 3856, stock p2001's 1269
                    # (r6 recorded p2061's: a 1928-wide picture in a 3856 raster, A001_139)
                    (0x60, OG4K_RESIZE), (0x64, OG4K_RESIZE), (0xD0, OG4K_RESIZE), (0xD4, OG4K_RESIZE)],
        canvas_pb=[(0x0C, OG4K_RASTER[0]), (0x10, OG4K_RASTER[1]), (0x1C, 2),
                   (0x20, OG4K_ACT[0]), (0x28, OG4K_ACT[1]),
                   (0xD8, OG4K_RASTER[0]), (0xE0, OG4K_RASTER[1]),
                   (0xF4, OG4K_RASTER[0]), (0xF8, OG4K_RASTER[1]),
                   (0x60, 1024), (0xD0, 1024), (0x64, 1024), (0xD4, 1024)],
        rate_canvas=[],
        standby=LV32,
        row_text='OG4K %dx%d' % OG4K_ACT, summary='OG4K',
        # 10/12-bit: one virtual profile id (the 8-bit CinemaDNG block) for all three; the depth goes
        # by the picker's table (pick8/10/12) into canvas +0x80/+0x84, as stock p2061/p2391/p2721
        bit_depths=(8, 10, 12),
    ),
}

# W48K (the user, 2026-11-05): the full-width band the stock FHD high rates read -- IMX455 mode 188,
# 4784x1700 2x2 binned (3400 of the sensor's 6380 rows), 2.81:1 -- recorded 1:1 like OG48K.  Modes
# 188..195 differ only in frame length (hmax 580 throughout), so mode 188 (59.94) is the one donor
# and the core's solver gives every rate (23.98 .. 59.94) the stock timing.  A video mode: no clamp.
# 8.1 MB a frame at 8-bit (59.94: ~490 MB/s).  Live view: 16:9 for now (aspect 3; the core has no
# letterboxed live view yet), so it shows more height than is recorded.
# The recording preview (canvas +0x0C / +0x10 buffer, +0x20 / +0x28 active, as p2061's 1288x724 /
# 1280x720) must stay within PREVIEW_MAX_DOWN of the recorded raster on each axis: U48K with p2061's
# preview (4784x2688 -> 1288x724, 3.71x both ways) flashed pink garbage over live view all through
# every recording (camera, 2026-11-05) -- the only format beyond 3x down; W48K (3.71x across, 2.34x
# down) did not, but its preview was squeezed unevenly.  Stock never goes beyond 3x.
PREVIEW_MAX_DOWN = 3.0
W48K_RASTER = (4784, 1696)
W48K_ACT = (4768, 1680)
W48K_READ = (4784, 1700)
ROWS['w48k'] = dict(
    label='W48K', profile=OG4K_BASE, enum=12,                   # uishare ui/enums.py 'W48K'
    stock_value=3, aspect=3, flags=0, video_base=True,
    donor_timing=(188, 0x049C0244, 0x000E0816),                 # hmax 580 | tail 1180, vmax 2070 | x 14
    # each stock rate at SIGMA's own split of the frame (the solver's gives the same period, but more
    # lines and a shorter tail at 23.98 / 25 / 50 / 59.94): the timing words of modes 188..195
    capture_modes={2398: 195, 2400: 194, 2500: 193, 2997: 192, 4800: 190, 5000: 189, 5994: 188},
    rec=list(W48K_RASTER), act=list(W48K_ACT), prev_h=0,
    modes=[(188, 5994, 580, 0, 14)],
    canvas_rec=[(0x00, W48K_RASTER[0]), (0x04, W48K_RASTER[1]),
                (0x24, W48K_ACT[0]), (0x2C, W48K_ACT[1]),
                (0xDC, W48K_RASTER[0]), (0xE4, W48K_RASTER[1]),
                (0x0C, 1616), (0x10, 572), (0x20, 1608), (0x28, 568),   # the preview (PREVIEW_MAX_DOWN)
                (0xF4, W48K_READ[0]), (0xF8, W48K_READ[1]),
                (0xFC, SCALE_2), (0x100, SCALE_2), (0x104, SCALE_2),
                (0x60, OG48K_RESIZE), (0x64, OG48K_RESIZE), (0xD0, OG48K_RESIZE), (0xD4, OG48K_RESIZE)],
    canvas_pb=[(0x0C, W48K_RASTER[0]), (0x10, W48K_RASTER[1]), (0x1C, 1),
               (0x20, W48K_ACT[0]), (0x28, W48K_ACT[1]),
               (0xD8, W48K_RASTER[0]), (0xE0, W48K_RASTER[1]),
               (0xF4, W48K_RASTER[0]), (0xF8, W48K_RASTER[1]),
               (0x60, 1024), (0xD0, 1024), (0x64, 1024), (0xD4, 1024)],
    rate_canvas=[],
    row_text='W48K %dx%d' % W48K_ACT, summary='W48K',
    bit_depths=(8, 10, 12),
)

# U48K (the user, 2026-11-05): mode 155's 4784x2700 2x2-binned read -- the full width at 16:9 (5400
# of 6380 rows), the read stock UHD 29.97 / 12-bit scale down to 3856 -- recorded 1:1.  Modes
# 155..158 differ only in frame length: one donor (155, 29.97), each stock rate at SIGMA's own words.
# The band is too tall for 48 fps.  Live view: the stock 16:9 view shows exactly this area.
# 12.9 MB a frame at 8-bit (29.97: ~385 MB/s).
U48K_RASTER = (4784, 2688)
U48K_ACT = (4768, 2672)
U48K_READ = (4784, 2700)
ROWS['u48k'] = dict(
    label='U48K', profile=OG4K_BASE, enum=13,                   # uishare ui/enums.py 'U48K'
    stock_value=3, aspect=3, flags=0, video_base=True,
    donor_timing=(155, 0x026C0244, 0x000E102E),                 # hmax 580 | tail 620, vmax 4142 | x 14
    capture_modes={2398: 158, 2400: 157, 2500: 156, 2997: 155},
    rec=list(U48K_RASTER), act=list(U48K_ACT), prev_h=0,
    modes=[(155, 2997, 580, 0, 14)],
    canvas_rec=[(0x00, U48K_RASTER[0]), (0x04, U48K_RASTER[1]),
                (0x24, U48K_ACT[0]), (0x2C, U48K_ACT[1]),
                (0xDC, U48K_RASTER[0]), (0xE4, U48K_RASTER[1]),
                (0x0C, 1616), (0x10, 908), (0x20, 1608), (0x28, 904),   # the preview (PREVIEW_MAX_DOWN)
                (0xF4, U48K_READ[0]), (0xF8, U48K_READ[1]),
                (0xFC, SCALE_2), (0x100, SCALE_2), (0x104, SCALE_2),
                (0x60, OG48K_RESIZE), (0x64, OG48K_RESIZE), (0xD0, OG48K_RESIZE), (0xD4, OG48K_RESIZE)],
    canvas_pb=[(0x0C, U48K_RASTER[0]), (0x10, U48K_RASTER[1]), (0x1C, 1),
               (0x20, U48K_ACT[0]), (0x28, U48K_ACT[1]),
               (0xD8, U48K_RASTER[0]), (0xE0, U48K_RASTER[1]),
               (0xF4, U48K_RASTER[0]), (0xF8, U48K_RASTER[1]),
               (0x60, 1024), (0xD0, 1024), (0x64, 1024), (0xD4, 1024)],
    rate_canvas=[],
    row_text='U48K %dx%d' % U48K_ACT, summary='U48K',
    bit_depths=(8, 10, 12),
)

# UHDC (the user, 2026-11-06): stock UHD's frame (3856x2170 / 3840x2160) cut 1:1 from the middle of
# mode 196's 6288x2174 unbinned read (the 1.52x crop band) -- 3840 of the sensor's 9568 columns, a
# ~2.5x crop -- up to 59.94 (stock UHD stops at 29.97).  Modes 196..203 differ only in frame length
# (hmax 534): one donor, each stock rate at SIGMA's own words.  The canvas is p2061's but for the read
# and the 1:1 resize, as stock's largest UHD crop step (p2019: 8208x4320 -> 3856x2170 at 1023).
# No playback pairs: its clips are stock UHD size (and ogc_name leaves it out of the size match).
# Live view: the stock 16:9 view of the whole sensor, not the crop (a frame guide marks it).
UHDC_READ = (6288, 2174)
# UHDC's recording live view: with p2061's preview (1288x724, 2.99x / 3.00x below its frame) it
# flashed pink (camera, r17); with the stock crop step's fields (p2079: preview 1296x730, +0xA4 42,
# +0xD8 / +0xE0 1296 / 2190) it froze on a garbage frame (r18) -- those are 8208x4320's, not this
# read's.  r19: U48K's larger preview, 1616x908 (2.39x).
ROWS['uhdc'] = dict(
    label='UHDC', profile=OG4K_BASE, enum=14,                   # uishare ui/enums.py 'UHDC'
    stock_value=3, aspect=3, flags=0, video_base=True,
    donor_timing=(196, 0x05160216, 0x001008C8),                 # hmax 534 | tail 1302, vmax 2248 | x 16
    capture_modes={2398: 203, 2400: 202, 2500: 201, 2997: 200, 4800: 198, 5000: 197, 5994: 196},
    rec=[3856, 2170], act=[3840, 2160], prev_h=0,
    modes=[(196, 5994, 534, 0, 16)],
    canvas_rec=[(0xF4, UHDC_READ[0]), (0xF8, UHDC_READ[1]),
                (0x60, OG48K_RESIZE), (0x64, OG48K_RESIZE), (0xD0, OG48K_RESIZE), (0xD4, OG48K_RESIZE)]
               + [(0x0C, 1616), (0x10, 908), (0x20, 1608), (0x28, 904)]    # the preview, as U48K's
               # the crop-window fields stock's crop steps set (p2079: 42 / 1296 / 2190), tuned live
               # (camera r20, test 2): +0xD8 = the preview's width, +0xE0 = the read's height -- the
               # bands at the top and bottom gone; the picture still squeezed (ISSUES.md 2)
               + [(0xA4, 42), (0xD8, 1616), (0xE0, 2174)],
    canvas_pb=[],
    rate_canvas=[],
    # the camera's crop factor while UHDC records: its live view's area is placed by it (9568 / 3856
    # = 2.48, stock's largest UHD crop step; ISSUES.md 2)
    crop100=248,
    row_text='UHDC 3840x2160', summary='UHDC',
    bit_depths=(8, 10, 12),
)


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


# ---- the live-view resolution label (camera 2026-11-05; RESCUSTOM_PORT.md "live-view label") ----
# LV_Resolution (the row's QS state k) drives group "Resolution" in four live-view sets: a clip whose
# image key at time 0 / 33 / 66 is L_ or M_resolution_1 / _2 / _dci4K, then two width properties
# (93 / 138 L, 78 / 113 M), the group ending at 66.  For every row k the core appends a key at
# t_k = 100k/3 to each property -- a copy of the LAST key (the wide one) with the row's image -- and
# moves the end (ogc.c QS_LVCLONE / QS_END).  The STILLlike sets also move the frame-rate text by
# the label's width (FrameRatePos): those keys copy the last one as well.  fp L addresses.
LV_CLIPS = [(0xC1E58194, 0), (0xC1EA8613, 1), (0xC1FC5D08, 0), (0xC20196F5, 1),   # (record, L 0 / M 1)
            (0xC1FB3D93, None), (0xC200796F, None)]                               # FrameRatePos: no image
LV_GROUPS = [0xC1E58232, 0xC1EA86B1, 0xC1FC5DA6, 0xC2019793, 0xC1FB3E18, 0xC20079F4]
# the tiles: the size of the stock DCI 4K label (the key every row's copies), white letters, opaque
# black ring, ARGB4444, left-aligned like the stock ones; Nimbus Sans Narrow at a medium weight comes
# closest to the stock face (measured: letters 37 / 30 px, ring 2 px)
LV_TILE = {'LVL': (138, 43, 37, 0.5), 'LVM': (113, 35, 30, 0.4)}
LV_RING = 2
LV_FONT = '/usr/share/fonts/urw-base35/NimbusSansNarrow-Regular.otf'


def lv_tile(text, width, height, cap, embolden, ring=LV_RING, font=None):
    """(luminance, alpha) bytes of an ARGB4444 tile (build_og3k_ui_candidate._hud_tile's format):
    alpha from the coverage grown by `ring`, grey from the coverage; the text shrinks to fit"""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    import os
    font = font or os.environ.get('FPSUP_FONT_LV', LV_FONT)
    ss = 8
    for size in range(120, 8, -1):
        f = ImageFont.truetype(font, size * ss)
        big = Image.new('L', (width * 2 * ss, height * 2 * ss), 0)
        ImageDraw.Draw(big).text((0, height * ss), text, font=f, fill=255, anchor='lm',
                                 stroke_width=int(round(embolden * ss)), stroke_fill=255)
        arr = np.array(big)
        ys, xs = np.where(arr > 30)
        if len(xs) and (ys.max() - ys.min() + 1) / ss <= cap and (xs.max() - xs.min() + 1) / ss <= width - 2 * ring:
            break
    else:
        raise ValueError(f'{text!r} does not fit {width}x{height}')
    cover = np.array(big.resize((width * 2, height * 2), Image.LANCZOS))
    ys, xs = np.where(cover > 10)
    top = (height - (ys.max() - ys.min() + 1)) // 2
    cover = np.roll(cover[ys.min() - top: ys.min() - top + height, :], ring - xs.min(), 1)[:, :width]
    c16 = cover.astype(np.uint16)
    grown = c16.copy()
    for dy in range(-ring, ring + 1):
        for dx in range(-ring, ring + 1):
            if dx * dx + dy * dy <= ring * ring + 1:
                grown = np.maximum(grown, np.roll(np.roll(c16, dy, 0), dx, 1))
    argb = (((grown >> 4) & 0xF) << 12) | (((c16 >> 4) & 0xF) * 0x111)
    return (argb & 0xFF).astype(np.uint8), (argb >> 8).astype(np.uint8)


def lv_tiles(label):
    """[(name, w, h, luminance, alpha)]: the row's live-view label, large and medium"""
    return [(f'{label}_{k}', w, h) + lv_tile(label, w, h, cap, emb) for k, (w, h, cap, emb) in LV_TILE.items()]


def stock_timing(image, modes):
    """capture_timing rows {rank, crop 0, w0, w1, engine fps (f32), nominal} from the firmware's
    timing table (0xC0B90FF8): each rate at stock mode `modes[rank]`'s own words"""
    tt = {}
    for i in range(85):
        mid, w0, w1 = struct.unpack_from('<3I', image, 0xC0B90FF8 + 0x20 * i - 0xC0000000)
        tt[mid] = (w0, w1)
    rates = {r[7]: r for r in L.RATES}
    out = []
    for rank, mid in sorted(modes.items()):
        w0, w1 = tt[mid]
        eng, nominal = rates[rank][5], rates[rank][6]
        out.append((rank, 0, w0, w1, _f(eng), nominal))
    return out


def row_data(target, tmp, image):
    """ogc_rowdata's dict for an fp L format, with its menu pack"""
    import build_og3k_ui_candidate as UI
    check(image, target)
    row = {k: v for k, v in ROWS[target].items() if k not in ('video_base', 'donor_timing', 'capture_modes')}
    if ROWS[target].get('capture_modes'):
        row['capture_timing'] = stock_timing(image, ROWS[target]['capture_modes'])
    old = UI.PLAN_TARGET
    try:
        UI.PLAN_TARGET = {'label': row['label'], 'act': tuple(row['act'])}
        pack, _ = UI.assets(tmp, names={'OG3K_QS': row['label'] + '_QS', 'OG3K_SET': row['label'] + '_SET',
                                        'OG3K_FONT': row['label'] + '_FONT'},
                            extra=lv_tiles(row['label']))
    finally:
        UI.PLAN_TARGET = old
    row['pack'] = pack
    return row
