"""Give a virtual mode id a row in the fp L's three IMX455-only per-mode tables (RAM only, live).

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 tablepatch.py show
    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 tablepatch.py apply [VMODE DONOR [ROW]]
    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 tablepatch.py restore [ROW]

The sensor object 0xC343C5B4 holds {REG desc 0xC0B98DE0, 0xC0BB05CC, 0xC0BB01C8}.  Besides REG (hooked
as lk_reg) it searches three tables by mode id, none of which res-custom knows:
    0xC032C658  stride 0x3C  (desc 0xC0BB05CC +8/+0xC)   row copier 0xC032C4E0
    0xC032C6C0  stride 0x5C  (desc 0xC0BB05CC +0/+4)     row copier 0xC032C548
    0xC032C728  stride 0x0C  (desc 0xC0BB01C8 +0/+4)     row copier 0xC032C598
A miss returns -1 and the copier copies row -1.  This test overwrites row ROW (default 84, mode 217)
of each table with the DONOR's row carrying id VMODE; restore copies the image's row back.
"""
import os, struct, sys
import putfile as P

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = open(os.path.join(HERE, '..', '..', '..', '..', 'out_fpl', 'MAIN_c0000000.bin'), 'rb').read()
TABLES = [('T3C', 0xC0BB05CC + 8, 0x3C), ('T5C', 0xC0BB05CC, 0x5C), ('T0C', 0xC0BB01C8, 0x0C)]


def img(a, n=1):
    return list(struct.unpack_from(f'<{n}I', IMG, a - 0xC0000000))


def rd(a, n=1):
    for _ in range(8):
        r = P.mem_get(a, n)
        if r and None not in r:
            return list(r)
    raise SystemExit(f'read {a:#x} failed')


def wr(a, words):
    for i, v in enumerate(words):
        P.mem_set(a + 4 * i, v)
    if rd(a, len(words)) != list(words):
        raise SystemExit(f'write {a:#x} did not stick')


def tables():
    for name, desc, stride in TABLES:
        base, count = rd(desc, 2)
        if (base, count) != tuple(img(desc, 2)):
            raise SystemExit(f'{name}: descriptor {base:#x} x{count} differs from the image')
        yield name, base, count, stride


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'
    if cmd == 'show':
        for name, base, count, stride in tables():
            ids = [rd(base + stride * i)[0] for i in range(count)]
            print(f'{name} {base:#x} x{count}: ids {ids}')
    elif cmd == 'apply':
        vm = int(sys.argv[2]) if len(sys.argv) > 2 else 230
        donor = int(sys.argv[3]) if len(sys.argv) > 3 else 161
        row = int(sys.argv[4]) if len(sys.argv) > 4 else 84
        for name, base, count, stride in tables():
            ids = [rd(base + stride * i)[0] for i in range(count)]
            if vm in ids:
                print(f'{name}: mode {vm} already has row {ids.index(vm)}')
                continue
            d = rd(base + stride * ids.index(donor), stride // 4)
            wr(base + stride * row, [vm] + d[1:])
            print(f'{name}: row {row} (was mode {ids[row]}) = mode {donor} as {vm}')
    elif cmd == 'restore':
        row = int(sys.argv[2]) if len(sys.argv) > 2 else 84
        for name, base, count, stride in tables():
            wr(base + stride * row, img(base + stride * row, stride // 4))
            print(f'{name}: row {row} restored (mode {img(base + stride * row)[0]})')
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
