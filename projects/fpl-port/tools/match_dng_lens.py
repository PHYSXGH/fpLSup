"""Match a DNG's WarpRectilinear against the fp L lens table dump.

Model (verified on A001_100): coefficients = table block b, nodes n..n+1 interpolated at one t for all
planes, then kr_j scaled by s^(2j).  For each block / node pair: t from kr0 per plane, s from kr1,
residual on kr2/kr3.
    match_dng_lens.py DUMP DUMP_BASE TABLE_ADDR DNG...
"""
import sys, struct, math

def tiff_tags(d):
    e = '<' if d[:2] == b'II' else '>'
    out = {}
    def ifd(o, depth=0):
        n = struct.unpack_from(e + 'H', d, o)[0]
        for i in range(n):
            tag, t, c, v = struct.unpack_from(e + 'HHII', d, o + 2 + 12 * i)
            size = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 10: 8, 12: 8}.get(t, 1) * c
            p = o + 2 + 12 * i + 8 if size <= 4 else v
            if t == 5:
                out[tag] = [a / b if b else 0 for a, b in zip(*[iter(struct.unpack_from(e + '%dI' % (2 * c), d, p))] * 2)]
            elif t == 3:
                out[tag] = struct.unpack_from(e + '%dH' % c, d, p)
            elif t == 4:
                out[tag] = struct.unpack_from(e + '%dI' % c, d, p)
            elif t == 2:
                out[tag] = d[p:p + c].split(b'\0')[0].decode(errors='replace').strip()
            else:
                out[tag] = d[p:p + c]
            if tag == 0x8769 and depth == 0:
                ifd(v, 1)
    ifd(struct.unpack_from(e + 'I', d, 4)[0])
    return out

def warp(op):
    cnt = struct.unpack_from('>I', op, 0)[0]; p = 4
    for _ in range(cnt):
        oid, ver, flags, size = struct.unpack_from('>IIII', op, p); p += 16; body = op[p:p + size]; p += size
        if oid == 1:
            n = struct.unpack_from('>I', body, 0)[0]
            return [struct.unpack_from('>4d', body, 4 + 48 * i) for i in range(n)]

def main():
    dump = open(sys.argv[1], 'rb').read(); base = int(sys.argv[2], 16); table = int(sys.argv[3], 16)
    rec = lambda b, n, p: struct.unpack_from('<4d', dump, table - base + 0x20 * (b * 36 + n * 3 + p))
    for path in sys.argv[4:]:
        tags = tiff_tags(open(path, 'rb').read())
        w = warp(tags[0xC74E])
        print(f'== {path.split("/")[-1]}: {tags[0x100][0]}x{tags[0x101][0]}  F{tags.get(0x829D, ["?"])[0]}  '
              f'{tags.get(0x920A, ["?"])[0]} mm  crop {tags.get(0xC620)}')
        for p, c in enumerate(w):
            print(f'   DNG plane {p}: ' + ' '.join(f'{x:.9f}' for x in c))
        fits = []
        for b in range(3):
            for n in range(11):
                ts, ss, res = [], [], 0
                for p in range(3):
                    a, z = rec(b, n, p), rec(b, n + 1, p)
                    if abs(z[0] - a[0]) < 1e-12: break
                    t = (w[p][0] - a[0]) / (z[0] - a[0]); k = [a[j] + t * (z[j] - a[j]) for j in range(4)]
                    s2 = w[p][1] / k[1] if k[1] else float('nan')
                    ts.append(t); ss.append(s2)
                    res = max(res, abs(k[2] * s2 ** 2 - w[p][2]), abs(k[3] * s2 ** 3 - w[p][3]))
                if len(ts) == 3 and all(-0.02 <= t <= 1.02 for t in ts):
                    fits.append((res + (max(ts) - min(ts)), res, b, n, ts, [math.sqrt(x) for x in ss]))
        fits.sort()
        for f in fits[:3]:
            print(f'   block {f[2]} nodes {f[3]}-{f[3]+1}: t = {", ".join(f"{t:.5f}" for t in f[4])}  '
                  f's = {", ".join(f"{s:.6f}" for s in f[5])}  max residual kr2/kr3 {f[1]:.1e}')


if __name__ == '__main__':
    main()
