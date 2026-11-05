"""Extra seeds for a Ghidra re-analysis of a dp2q image (CSV addr,name,mode for DP2QSeeds.java):
  T  Thumb function: a Thumb BL target (or ARM BLX target) that starts with push {..,lr} / push.w {..,lr}
  A  ARM function:   an ARM BL target that starts with push {..,lr} (stmdb sp!)
  P  pointer data:   the entry-point word of each static task-table record (so the tasks get xrefs)
Only addresses not already in the first seeds file are written.

usage: python -I ghidra_more_seeds.py master out_dp2q/ghidra/seeds_master.csv > more.csv
"""
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dp2q_lib import BASE, load, thumb_calls, arm_calls
from task_table import find_table, REC


CODE_END = 0x210000      # master/loader 2.03: code is 0x40000000..~0x40210000, data above


def thumb_prologue(d, o):
    h = struct.unpack_from('<H', d, o)[0]
    if h & 0xFF00 == 0xB500:                                   # push {..., lr}
        return True
    if h == 0xE92D:                                            # push.w {..., lr}
        return struct.unpack_from('<H', d, o + 2)[0] & 0x4000 != 0
    return False


def arm_prologue(d, o):
    w = struct.unpack_from('<I', d, o)[0]
    return w & 0xFFFF4000 == 0xE92D4000                        # stmdb sp!, {..., lr}


def main(name, have):
    d, used = load(name)
    old = {int(l.split(',')[0], 16) for l in Path(have).read_text().splitlines() if l.strip()}
    inimg = lambda a: BASE <= a < BASE + used
    th, ar = set(), set()
    for site, t, blx in thumb_calls(d, used):
        if blx:                                                # Thumb BLX -> ARM target
            if inimg(t) and t % 4 == 0 and arm_prologue(d, t - BASE):
                ar.add(t)
        elif inimg(t) and thumb_prologue(d, t - BASE):
            th.add(t)
    for site, t in arm_calls(d, used):
        w = struct.unpack_from('<I', d, site - BASE)[0]
        if w >> 28 == 0xF:                                     # ARM BLX -> Thumb target
            if inimg(t) and thumb_prologue(d, t - BASE):
                th.add(t)
        elif inimg(t) and arm_prologue(d, t - BASE):
            ar.add(t)
    # pointer-referenced prologues: any aligned word in the image that points at a prologue in the
    # code area (Thumb targets carry bit 0). Catches functions reached only through handler tables.
    code_end = BASE + CODE_END
    for i in range(0, used - 4, 4):
        w = struct.unpack_from('<I', d, i)[0]
        if not BASE <= w & ~1 < code_end:
            continue
        if w & 1 and thumb_prologue(d, (w & ~1) - BASE):
            th.add(w & ~1)
        elif not w & 3 and arm_prologue(d, w - BASE):
            ar.add(w)
    n = 0
    for t in sorted(th - old):
        print(f'{t:#x},,T'); n += 1
    for t in sorted(ar - old):
        print(f'{t:#x},,A'); n += 1
    o, cnt = find_table(d, used)
    for k in range(cnt):
        print(f'{BASE + o + k * REC + 8:#x},,P')
    print(f'# {n} functions, {cnt} pointers', file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
