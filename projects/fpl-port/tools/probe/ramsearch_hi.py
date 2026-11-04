"""ramsearch2 + list search over a big dump, in 64 MiB blocks with overlap.  python3 ramsearch_hi.py DUMPDIR"""
import os, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
img = open(os.path.join(HERE, '..', '..', '..', '..', 'out_fpl', 'MAIN_c0000000.bin'), 'rb').read()
order_ids = [struct.unpack_from('<I', img, 0xC0B90FF8 + 0x20 * i - 0xC0000000)[0] for i in range(85)]
ids = sorted(set(order_ids)); R = set(ids)
free = [i for i in range(218) if i not in R]
d = sys.argv[1]
pieces = sorted(f for f in os.listdir(d) if f.startswith('ram_'))
BLK, OV = 64 << 20, 64 << 10
bm = bytearray(32)
for i in R: bm[i >> 3] |= 1 << (i & 7)
pats = []
for name, sq in (('order', order_ids), ('sorted', ids)):
    for fmt in ('B', 'H', 'I'):
        pats.append((name, fmt, struct.pack(f'<20{fmt}', *sq[:20])))
def blocks():
    buf = b''; start = None
    for f in pieces:
        a = int(f[4:12], 16)
        if start is None: start = a
        buf += open(os.path.join(d, f), 'rb').read()
        while len(buf) >= BLK + OV:
            yield start, buf[:BLK + OV]
            buf = buf[BLK:]; start += BLK
    if buf: yield start, buf
for base, data in blocks():
    at = data.find(bytes(bm))
    if at >= 0: print(f'bitmap at {base + at:#x}', flush=True)
    for name, fmt, p in pats:
        at = data.find(p)
        if at >= 0: print(f'list ({name}, {fmt}) at {base + at:#x}', flush=True)
    raw = np.frombuffer(data, dtype=np.uint8)
    for e, dt in ((1, np.uint8), (2, np.uint16), (4, np.uint32)):
        arr = raw[:len(raw) // e * e].view(dt); nz = arr != 0
        for s in range(e, 65, e):
            k = s // e; n = len(arr) - k * 218
            if n <= 0: continue
            c = nz[k*ids[1]:k*ids[1]+n] & nz[k*ids[2]:k*ids[2]+n] & nz[k*ids[3]:k*ids[3]+n] & ~nz[k*free[0]:k*free[0]+n] & ~nz[k*free[1]:k*free[1]+n]
            cand = np.nonzero(c)[0]
            for i in ids[4:]:
                if not len(cand): break
                cand = cand[nz[cand + k*i]]
            for i in free[2:]:
                if not len(cand): break
                cand = cand[~nz[cand + k*i]]
            for p in cand[:3]: print(f'present e={e} s={s} at {base + int(p)*e:#x}', flush=True)
            cv = arr[k*free[0]:k*free[0]+n]
            c = (arr[k*free[1]:k*free[1]+n] == cv) & (arr[k*free[2]:k*free[2]+n] == cv) & (arr[k*ids[1]:k*ids[1]+n] != cv) & (arr[k*ids[2]:k*ids[2]+n] != cv) & (cv != 0)
            cand = np.nonzero(c)[0]; cvals = arr[cand + k*free[0]]
            for i in ids[3:]:
                if not len(cand): break
                keep = arr[cand + k*i] != cvals; cand, cvals = cand[keep], cvals[keep]
            for i in free[3:]:
                if not len(cand): break
                keep = arr[cand + k*i] == cvals; cand, cvals = cand[keep], cvals[keep]
            for p, v in list(zip(cand, cvals))[:3]: print(f'absent={int(v):#x} e={e} s={s} at {base + int(p)*e:#x}', flush=True)
    print(f'.. {base:#x} done', flush=True)
