"""Wider search of RAM dumps: per-mode records indexed by the mode id (any stride, any field).

    python3 ramsearch2.py DUMPDIR [DUMPDIR ...]

For element size e (1, 2, 4) and record stride s (a multiple of e, up to 64): positions P where the
element at P + s * id is non-zero for every real fp L mode id and zero for every other id below 218 (a
"present" field), and positions where it equals the id itself (a record that carries its id).
"""
import os, struct, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
img = open(os.path.join(HERE, '..', '..', '..', '..', 'out_fpl', 'MAIN_c0000000.bin'), 'rb').read()
ids = sorted({struct.unpack_from('<I', img, 0xC0B90FF8 + 0x20 * i - 0xC0000000)[0] for i in range(85)})
free = [i for i in range(218) if i not in set(ids)]
order = ids[1:] + free                    # id 0 adds nothing to a shifted-AND start


def search(path):
    pieces = sorted(f for f in os.listdir(path) if f.startswith('ram_'))
    base = int(pieces[0][4:12], 16)
    raw = np.frombuffer(b''.join(open(os.path.join(path, f), 'rb').read() for f in pieces), dtype=np.uint8)
    print(f'{path}: {len(raw) >> 20} MiB from {base:#x}', flush=True)
    for e, dt in ((1, np.uint8), (2, np.uint16), (4, np.uint32)):
        arr = raw[:len(raw) // e * e].view(dt)
        nz = arr != 0
        for s in range(e, 65, e):
            k = s // e
            span = k * 217 + 1
            n = len(arr) - span
            if n <= 0:
                continue
            # present: start with three real ids and one free id, then check the rest sparsely
            c = nz[k * ids[1]: k * ids[1] + n] & nz[k * ids[2]: k * ids[2] + n] & nz[k * ids[3]: k * ids[3] + n] \
                & ~nz[k * free[0]: k * free[0] + n]
            cand = np.nonzero(c)[0]
            for i in ids[4:]:
                if not len(cand):
                    break
                cand = cand[nz[cand + k * i]]
            for i in free[1:]:
                if not len(cand):
                    break
                cand = cand[~nz[cand + k * i]]
            for p in cand[:5]:
                print(f'  present: e={e} stride={s}: {base + int(p) * e:#x}', flush=True)
            # absent marked by a constant c (the value at every other id), present != c
            cv = arr[k * free[0]: k * free[0] + n]
            c = (arr[k * free[1]: k * free[1] + n] == cv) & (arr[k * free[2]: k * free[2] + n] == cv) \
                & (arr[k * ids[1]: k * ids[1] + n] != cv) & (arr[k * ids[2]: k * ids[2] + n] != cv) & (cv != 0)
            cand = np.nonzero(c)[0]
            cvals = arr[cand + k * free[0]]
            for i in ids[3:]:
                if not len(cand):
                    break
                keep = arr[cand + k * i] != cvals
                cand, cvals = cand[keep], cvals[keep]
            for i in free[3:]:
                if not len(cand):
                    break
                keep = arr[cand + k * i] == cvals
                cand, cvals = cand[keep], cvals[keep]
            for p, cv0 in list(zip(cand, cvals))[:5]:
                print(f'  absent={int(cv0):#x}: e={e} stride={s}: {base + int(p) * e:#x}', flush=True)
            # carries its id: arr[P + k*id] == id for every real id
            c = (arr[k * ids[1]: k * ids[1] + n] == ids[1]) & (arr[k * ids[2]: k * ids[2] + n] == ids[2])
            cand = np.nonzero(c)[0]
            for i in ids[3:]:
                if not len(cand):
                    break
                cand = cand[arr[cand + k * i] == i]
            for p in cand[:5]:
                print(f'  carries id: e={e} stride={s}: {base + int(p) * e:#x}', flush=True)


for p in sys.argv[1:]:
    search(p)
