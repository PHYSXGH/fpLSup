"""Print the static T-Kernel task table of a dp2 Quattro image (master or loader).

The firmware creates its tasks from a table of 52-byte T_CTSK records (exinf, tskatr, task, itskpri,
stksz, sstksz, stkptr, uatb, lsid, resid, dsname[8], pad) in a block that is copied to RAM 0x01000000
at boot (master 2.03: image 0x40C40628 -> 0x01000000; task table at runtime 0x01006B6C, 50 entries).
The table is found by its shape, not by address, so it works on both images and should survive a
version change.

usage: python -I task_table.py [master|loader] [--csv]
"""
import sys, struct, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))   # -I drops the script dir
from dp2q_lib import BASE, load

REC = 0x34


def rec_ok(d, o, used):
    if o + REC > used:
        return False
    w = struct.unpack_from('<13I', d, o)
    name = d[o + 0x28:o + 0x30]
    return (w[1] & 0x40 and w[1] < 0x1000                       # TA_DSNAME set, small attribute
            and BASE <= w[2] & ~1 < BASE + used                  # entry point in the image
            and 0 < w[3] < 141                                   # T-Kernel priority range
            and 0 < w[5] <= 0x100000                             # system stack size
            and re.fullmatch(rb'[A-Za-z0-9_]{0,8}\0*', name) is not None)


def find_table(d, used):
    best = (0, 0)
    o = 0
    while o < used - REC:
        if rec_ok(d, o, used):
            n = 0
            while rec_ok(d, o + n * REC, used):
                n += 1
            if n > best[1]:
                best = (o, n)
            o += n * REC
        else:
            o += 4
    return best


def main(name='master', csv=False):
    d, used = load(name)
    o, n = find_table(d, used)
    if n == 0:
        raise SystemExit('no task table found')
    print(f'# {name}: task table at image {BASE + o:#x}, {n} entries')
    print('idx,name,entry,mode,priority,stack,tskatr,stkptr' if csv else
          'idx name      entry       mode pri  stack   tskatr stkptr')
    for k in range(n):
        w = struct.unpack_from('<13I', d, o + k * REC)
        nm = d[o + k * REC + 0x28:o + k * REC + 0x30].split(b'\0')[0].decode()
        mode = 'T' if w[2] & 1 else 'A'
        if csv:
            print(f'{k},{nm},{w[2] & ~1:#x},{mode},{w[3]},{w[5]:#x},{w[1]:#x},{w[6]:#x}')
        else:
            print(f'{k:3d} {nm:<9} {w[2] & ~1:#010x}  {mode}  {w[3]:4d}  {w[5]:#7x}  {w[1]:#5x}  '
                  f'{w[6]:#x}' if w[6] else
                  f'{k:3d} {nm:<9} {w[2] & ~1:#010x}  {mode}  {w[3]:4d}  {w[5]:#7x}  {w[1]:#5x}  -')


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    main(a[0] if a else 'master', '--csv' in sys.argv)
