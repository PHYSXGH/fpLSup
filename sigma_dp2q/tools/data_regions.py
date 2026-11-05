"""Find long runs of highly repetitive bytes in a dp2q image (fills, bitmaps, lookup tables).
Thumb decodes such runs as endless straight-line code; Ghidra then builds one huge bogus function and
its constant propagation / decompiler run out of memory (master 2.03: 0x40754074..0x4077DFD8).
Output CSV start,end (exclusive) for DP2QData.java, which marks them as byte arrays before analysis.

A 1 KB block counts as repetitive if it holds <= 8 distinct 32-bit words; adjacent blocks are merged,
and runs shorter than MIN (4 KB) are dropped.

usage: python -I data_regions.py [master|loader] [min_bytes]
"""
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dp2q_lib import BASE, load

BLK = 0x400


def main(name='master', min_len=0x1000):
    d, used = load(name)
    rep = []
    for o in range(0, used - BLK, BLK):
        words = set(struct.unpack_from(f'<{BLK // 4}I', d, o))
        rep.append(len(words) <= 8)
    runs, start = [], None
    for k, r in enumerate(rep + [False]):
        if r and start is None:
            start = k
        elif not r and start is not None:
            if (k - start) * BLK >= min_len:
                runs.append((BASE + start * BLK, BASE + k * BLK))
            start = None
    for a, b in runs:
        print(f'{a:#x},{b:#x}')
    print(f'# {len(runs)} regions, {sum(b - a for a, b in runs):#x} bytes', file=sys.stderr)


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0] if a else 'master', int(a[1], 0) if len(a) > 1 else 0x1000)
