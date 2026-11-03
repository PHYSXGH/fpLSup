"""Which camera a build is for, and how fp addresses become that camera's.

    FPSUP_CAMERA=fp    (default) SIGMA fp Ver.5.02 -- every address as written
    FPSUP_CAMERA=fpl   SIGMA fp L Ver.3.02 -- addresses through cameras/fpl302.tsv

The sources keep the fp addresses they were written and verified with.  For
another camera there is one table, reviewed by hand, and two ways in:

  * assembly: armasm preprocesses the source and rewrites every 0xC0000000..
    0xCFFFFFFF constant through the table before assembling (translate_asm);
  * Python:   constants that end up on the camera are written fw(0xC....).

An address the table does not know stops the build.  A constant in that range
that is not an address (a magic, a float) is listed as `const` so it is left
alone on purpose, not by accident.  For the fp the table is never read and
fw() is the identity, so fp builds are byte-for-byte what they were.

Table rows (tab-separated, '#' starts a comment):

    0xC0BAC2F8  0xC0BD2544  auto     how it was found
    0xC072D000  0xC0735000  range    -0x2580   (fp start, fp end, delta)
    0xC33C5AA5  -           const    ring end marker, not an address
    0xC032C720  -           todo     why it is not mapped yet

status: auto (byte-identical match / agreeing pointer evidence), checked (read by
hand), verify (best evidence, still to be confirmed on the camera), camera
(verified on a camera), range, const, todo (using it is an error).
"""
import os
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
CAMERAS = {
    'fp': None,
    'fpl': HERE / 'cameras' / 'fpl302.tsv',
}
NAMES = {'fp': 'SIGMA fp Ver.5.02', 'fpl': 'SIGMA fp L Ver.3.02'}

# What the address table cannot say: the memory map.  FUN_c001ed2c (identical
# code in both) registers RAM up to 0x80000000 on the fp and up to 0xC0000000
# on the fp L -- 1 GB against 2 GB, both at 0x40000000 = physical 0.  On the fp
# the CPU sees the same RAM uncached at +0x40000000, and the USB worker uses
# that mirror for its frames; on the fp L that range is the second gigabyte,
# ordinary RAM, so the worker must use the cached address and maintain the
# D-cache itself.  The bus address is the cached address - 0x40000000 on both.
# pool_hi: where a host tool still believes a pool address.  The fp's tools
# have always said below 0x50000000 (every pool seen was 0x45xxxxxx); kept as
# it was.  The fp L may hand out blocks anywhere in its two gigabytes.
MEMORY = {
    'fp':  {'ram_top': 0x80000000, 'uncached_alias': True,  'pool_hi': 0x50000000},
    'fpl': {'ram_top': 0xC0000000, 'uncached_alias': False, 'pool_hi': 0xC0000000},
}
RAM_BOTTOM = 0x40000000


# The sensor, for what the lens profile computes (gyro/gcsv_json.S).  Both read
# the same row layouts through identical accessors; the tables differ.
#   IMX410: 6000 px of image (the still mode reads 6064, outputs 6000), 35.9 mm.
#   IMX455: the fp L's mode object points at timing 0xC0B90FF8 / geometry
#   0xC0B91A98, 85 modes (read on the camera 2026-11-03).  The still mode reads
#   9568 x 6380 and outputs 9520 x 6328, so 9520 by the fp's convention;
#   9520 x 3.76 um (the IMX455's pitch) = 35.80 mm -> 358.
#   Clock: 72 MHz for both: at 72 MHz every NTSC video rate in the table is
#   exact (23.9760, 29.9700, 59.9401 ...); the misfits are still/burst modes
#   with truncated labels (projects/fpl-port/tools/imx455_modes.py).
#   focal_uncapped: the focal length in pixels uses the columns the mode really
#   reads (readout x binning), not that capped at the active width.  The fp
#   keeps its cap; on the fp L it is off (user's choice, 2026-11-03) and
#   untested -- see projects/fpl-port/FOCAL_CAP.md.
SENSOR = {
    'fp':  {'name': 'IMX410', 'active_w': 6000, 'mm10': 359, 'mhz': 72, 'focal_uncapped': False},
    'fpl': {'name': 'IMX455', 'active_w': 9520, 'mm10': 358, 'mhz': 72, 'focal_uncapped': True,
            # The radius the camera rescales the lens data by (its DNG's kr_j x s^(2j)):
            # s = (f64 at dist_halfdiag_at) / (f64 at dist_ref_at) = 21.4908 / 21.63
            # = 0.99356411, both doubles in the fp L image (the lens module divides
            # the same two at 0xC0044374).  Read at run time, not copied here.
            'dist_halfdiag_at': 0xC02D7D08, 'dist_ref_at': 0xC0044528,
            # The camera's current crop (video crop menu 1.0x .. 3.18x), as the lens
            # module reads it: u32 crop x100, u32 100, u32 width, u32 height (pixels
            # of the 9520 x 6328 still area), f64 half-diagonal in mm.  Object at
            # 0xC308A670 (FUN_c00530f0) +0x4268 (vt+0x3C) +0xC (vt+0x18) +0x17C.
            # Read live 2026-11-03: 2.48x / 1.00x / 1.53x followed the menu.
            'crop_record_at': 0xC308EA60},
}


def sensor():
    return SENSOR[target()]


def memory():
    return MEMORY[target()]


def ram_top():
    return memory()['ram_top']


def is_pool(addr):
    """Could `addr` be a pool the allocator handed out on this camera?"""
    return bool(addr) and RAM_BOTTOM <= addr < memory()['pool_hi']


def asm_defines():
    """Defines every assembly for this camera gets (armasm adds them)."""
    mem = memory()
    # FPSUP_REF_NO_ALIAS=1: an fp build with the fp L's memory code in it, only
    # as the reference card_check.py compares an fp L card against.
    if os.environ.get('FPSUP_REF_NO_ALIAS') == '1':
        mem = MEMORY['fpl']
    sen = SENSOR['fpl'] if os.environ.get('FPSUP_REF_NO_ALIAS') == '1' else sensor()
    out = ()
    if not mem['uncached_alias']:
        out += ('FPSUP_NO_UNCACHED_ALIAS=1', f'FPSUP_RAM_TOP=0x{mem["ram_top"]:X}')
    if sen is not SENSOR['fp']:
        out += (f'FPSUP_SENSOR_ACTIVE_W={sen["active_w"]}', f'FPSUP_SENSOR_MM10={sen["mm10"]}',
                f'FPSUP_SENSOR_MHZ={sen["mhz"]}', 'FPSUP_CAMERA_FPL=1')
        if sen['focal_uncapped']:
            out += ('FPSUP_SENSOR_FOCAL_UNCAPPED=1',)
        if 'dist_halfdiag_at' in sen:
            # Firmware addresses of this camera already: armasm passes them in
            # decimal, so the address table does not translate them again.
            out += (f'FPSUP_DIST_HALFDIAG_AT=0x{sen["dist_halfdiag_at"]:X}',
                    f'FPSUP_DIST_REF_AT=0x{sen["dist_ref_at"]:X}')
        if 'crop_record_at' in sen:
            out += (f'FPSUP_CROP_RECORD_AT=0x{sen["crop_record_at"]:X}',)
    return out

LO, HI = 0xC0000000, 0xD0000000
_HEX = re.compile(r'\b0[xX]([cC][0-9a-fA-F]{7})\b')


def target():
    t = os.environ.get('FPSUP_CAMERA', 'fp').strip().lower() or 'fp'
    if t not in CAMERAS:
        raise SystemExit(f'FPSUP_CAMERA={t!r}: known cameras are {", ".join(CAMERAS)}')
    return t


class UnmappedAddress(SystemExit):
    pass


_tables = {}


def _load(t):
    if t in _tables:
        return _tables[t]
    exact, ranges, const, todo = {}, [], set(), {}
    for n, line in enumerate(CAMERAS[t].read_text().splitlines(), 1):
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        f = line.split('\t')
        f = [x.strip() for x in f if x.strip()] if len(f) > 1 else line.split()
        src, dst, status = int(f[0], 16), f[1], f[2]
        if status == 'range':
            ranges.append((src, int(dst, 16), int(f[3], 16)))
        elif status == 'const':
            const.add(src)
        elif status == 'todo':
            todo[src] = ' '.join(f[3:])
        elif status in ('auto', 'checked', 'verify', 'camera'):
            exact[src] = int(dst, 16)
        else:
            raise SystemExit(f'{CAMERAS[t].name}:{n}: unknown status {status!r}')
    _tables[t] = (exact, ranges, const, todo)
    return _tables[t]


def fw(addr, what=''):
    """The current camera's address for fp address `addr`."""
    t = target()
    if CAMERAS[t] is None or not (LO <= addr < HI):
        return addr
    exact, ranges, const, todo = _load(t)
    if addr in exact:
        return exact[addr]
    if addr ^ 1 in exact:               # the same Thumb function, bit 0 set or clear
        return exact[addr ^ 1] ^ 1
    for s, e, d in ranges:
        if s <= addr < e:
            return addr + d
    if addr in const:
        return addr
    why = todo.get(addr, 'not in the table')
    raise UnmappedAddress(f'{NAMES[t]}: no address for fp {addr:#010x}'
                          f'{" (" + what + ")" if what else ""}: {why}')


POISON_BASE = 0xDEAD0000      # an unmapped address that is only DEFINED gets this
POISON_STEP = 0x100           # room for `.equ X, ADDR + offset` without overlap


def translate_asm(text, where='', poisons=None):
    """Rewrite the address constants in preprocessed assembly.  Comments after
    '@' are left as written: they describe the fp and are not assembled.

    An address the table cannot map is fatal where it is used, but harmless in
    a `.equ` nobody references -- an include defines everything it might need.
    So an unmapped address in a `.equ` line becomes a poison value (recorded in
    `poisons`, value -> fp address) and armasm fails the build if any poison
    value is found in the assembled code.  Anywhere else it is fatal at once."""
    if CAMERAS[target()] is None:
        return text
    if poisons is None:
        poisons = {}
    out, missing = [], []
    for n, line in enumerate(text.splitlines(keepends=True), 1):
        code, sep, comment = line.partition('@') if '"' not in line else (line, '', '')
        is_equ = code.lstrip().lower().startswith(('.equ', '.set'))

        def sub(m):
            a = int(m.group(1), 16)
            try:
                return f'{fw(a):#010x}'
            except UnmappedAddress as e:
                if is_equ:
                    for v, (fa, _) in poisons.items():
                        if fa == a:
                            return f'{v:#010x}'
                    v = POISON_BASE + POISON_STEP * len(poisons)
                    poisons[v] = (a, str(e))
                    return f'{v:#010x}'
                missing.append(f'  {where}:{n}: {e}')
                return m.group(0)
        out.append(_HEX.sub(sub, code) + sep + comment)
    if missing:
        raise UnmappedAddress('\n'.join(['addresses with no mapping:'] + sorted(set(missing))))
    return ''.join(out)


def poison_hits(code, poisons):
    """fp addresses whose poison value reached the assembled code: as a word,
    as an ARM movw/movt pair's halves, or as a Thumb-2 movt."""
    if not poisons:
        return []
    import struct
    lo, hi = POISON_BASE, POISON_BASE + POISON_STEP * len(poisons)
    top = POISON_BASE >> 16
    hits = set()

    def owner(v):
        k = (v - POISON_BASE) // POISON_STEP
        return list(poisons.values())[k][0] if 0 <= k < len(poisons) else None
    for i in range(0, len(code) - 3, 2):
        w = struct.unpack_from('<I', code, i)[0]
        if i % 4 == 0 and lo <= w < hi:
            hits.add(owner(w))
        if i % 4 == 0 and (w & 0x0FF00000) == 0x03400000 and \
                (((w >> 4) & 0xF000) | (w & 0xFFF)) == top:
            hits.add('movt #0xDEAD (upper half of a poisoned address)')
        h1, h2 = struct.unpack_from('<HH', code, i)
        if (h1 & 0xFBF0) == 0xF2C0:
            imm = ((h1 & 0xF) << 12) | (((h1 >> 10) & 1) << 11) | (((h2 >> 12) & 7) << 8) | (h2 & 0xFF)
            if imm == top:
                hits.add('thumb movt #0xDEAD (upper half of a poisoned address)')
    return sorted(f'{h:#010x}' if isinstance(h, int) else str(h) for h in hits)
