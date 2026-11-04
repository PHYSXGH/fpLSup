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


ROWS = {
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
}


def check(image, target):
    """the static facts this file rests on, against the fp L image"""
    w = lambda a, n=1: struct.unpack_from('<%dI' % n, image, a - 0xC0000000)    # noqa: E731
    tt = 0xC0B90FF8
    rows = {w(tt + 0x20 * i)[0]: w(tt + 0x20 * i, 3) for i in range(85)}
    if rows.get(DONOR, (0,))[1:] != DONOR_TIMING:
        raise ValueError(f'{target}: mode {DONOR} timing differs from {DONOR_TIMING}')
    if w(0xC0BF6820 + 4 * BASE_PROFILE)[0] == 0xFFFFFFFF:
        raise ValueError(f'{target}: p{BASE_PROFILE} has no mapping row')
    for lo, hi in L.PROFILE_CLASSES:
        if lo <= BASE_PROFILE <= hi:
            raise ValueError(f'{target}: p{BASE_PROFILE} carries a classifier flag')


def row_data(target, tmp, image):
    """ogc_rowdata's dict for an fp L format, with its menu pack"""
    import build_og3k_ui_candidate as UI
    check(image, target)
    row = dict(ROWS[target])
    old = UI.PLAN_TARGET
    try:
        UI.PLAN_TARGET = {'label': row['label'], 'act': tuple(row['act'])}
        pack, _ = UI.assets(tmp, names={'OG3K_QS': row['label'] + '_QS', 'OG3K_SET': row['label'] + '_SET',
                                        'OG3K_FONT': row['label'] + '_FONT'})
    finally:
        UI.PLAN_TARGET = old
    row['pack'] = pack
    return row
