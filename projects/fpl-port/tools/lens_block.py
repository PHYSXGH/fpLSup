"""Decode the fp L's lens correction block from a RAM dump and fit DNGs against it.

Layout (fp L, from F = 0xC307B9D4; same offsets as the fp's block at 0xC307CDF0):
  F+0x000  zoom positions, u32 tenths of mm, until 0xFFFF              -> Nz
  F+0x03C  focus axis, u32 2^24/mm, Nz*Na rows of Nn                     -> Nn
  F+0x3CC  apertures, u32 APEX Av x 1024, Nz*Na, until 0xFFFF            -> Na
  F+0x480  coefficients [zoom][aperture][node][plane][kr0..kr3] f64
DNG model: blend of the 8 surrounding records (zoom v, aperture u, focus t),
then kr_j * s^(2j).
    lens_block.py DUMP DUMP_BASE [DNG...]
"""
import sys, struct, math
sys.path.insert(0, __import__('os').path.dirname(__file__))
from match_dng_lens import tiff_tags, warp

F = 0xC307B9D4
FILL = (0xFFFF, 0x7FFFFFFF, 0xFFFFFFFF)


class Block:
    def __init__(self, dump, base):
        self.B, self.base = dump, base
        w = lambda a, n=1: struct.unpack_from('<%dI' % n, dump, a - base)
        self.zooms = [x for x in w(F, 15) if x not in FILL]
        self.Nz = len(self.zooms)
        aps = w(F + 0x3CC, 45)
        aps = list(aps[:next((i for i, x in enumerate(aps) if x in FILL), len(aps))])
        self.Na = len(aps) // self.Nz
        self.aps = [aps[z * self.Na:(z + 1) * self.Na] for z in range(self.Nz)]
        axis = w(F + 0x3C, 0x390 // 4)
        nax = next((i for i, x in enumerate(axis) if x in FILL), len(axis))
        self.Nn = nax // (self.Nz * self.Na)
        self.axis = [axis[r * self.Nn:(r + 1) * self.Nn] for r in range(self.Nz * self.Na)]

    def rec(self, z, a, n, p):
        i = ((z * self.Na + a) * self.Nn + n) * 3 + p
        return struct.unpack_from('<4d', self.B, F + 0x480 - self.base + 0x20 * i)

    def blend(self, z, a, n, v, u, t, p):
        out = [0.0] * 4
        for dz, wz in ((0, 1 - v), (1, v)):
            for da, wa in ((0, 1 - u), (1, u)):
                for dn, wn in ((0, 1 - t), (1, t)):
                    zz = min(z + dz, self.Nz - 1); aa = min(a + da, self.Na - 1); nn = min(n + dn, self.Nn - 1)
                    r = self.rec(zz, aa, nn, p)
                    for j in range(4):
                        out[j] += wz * wa * wn * r[j]
        return out

    def describe(self):
        print(f'zoom positions ({self.Nz}): {[x / 10 for x in self.zooms]} mm')
        print(f'apertures ({self.Na} per zoom), Av: ' + ' | '.join(
            '/'.join(f'{x / 1024:.2f}' for x in row) for row in self.aps))
        print(f'nodes ({self.Nn}); axis row 0: {self.axis[0]}')


def fit(block, w):
    best = None
    s0 = 0.993564
    def err(z, a, n, v, u, t, s):
        m = 0
        for p in range(3):
            b = block.blend(z, a, n, v, u, t, p)
            m = max(m, max(abs(b[j] * s ** (2 * j) - w[p][j]) for j in range(4)))
        return m
    for z in range(max(block.Nz - 1, 1)):
        for a in range(max(block.Na - 1, 1)):
            for n in range(block.Nn - 1):
                g = min((err(z, a, n, v / 4, u / 4, t / 4, s0), v / 4, u / 4, t / 4)
                        for v in range(5) for u in range(5) for t in range(5))
                e, v, u, t = g; s = s0; st = [0.05, 0.05, 0.05, 0.0005]
                for _ in range(400):
                    imp = False
                    for k in range(4):
                        for sg in (1, -1):
                            x = [v, u, t, s]; x[k] += sg * st[k]
                            if k < 3 and not -0.001 <= x[k] <= 1.001: continue
                            e2 = err(z, a, n, *x)
                            if e2 < e: e, (v, u, t, s), imp = e2, x, True
                    if not imp:
                        st = [q / 2 for q in st]
                        if max(st[:3]) < 1e-10: break
                if best is None or e < best[0]: best = (e, z, a, n, v, u, t, s)
    return best


def main():
    block = Block(open(sys.argv[1], 'rb').read(), int(sys.argv[2], 16))
    block.describe()
    for path in sys.argv[3:]:
        tags = tiff_tags(open(path, 'rb').read())
        w = warp(tags[0xC74E])
        e, z, a, n, v, u, t, s = fit(block, w)
        zf = block.zooms[z] + v * (block.zooms[min(z + 1, block.Nz - 1)] - block.zooms[z])
        av = block.aps[z][a] + u * (block.aps[z][min(a + 1, block.Na - 1)] - block.aps[z][a])
        print(f'== {path.split("/")[-1]}: {tags[0x100][0]}x{tags[0x101][0]}  DNG says F{tags[0x829D][0]} at '
              f'{tags[0x920A][0]} mm')
        print(f'   fit: zoom {z}+{v:.4f} -> {zf / 10:.2f} mm, aperture {a}+{u:.4f} -> Av {av / 1024:.4f} '
              f'(F{2 ** (av / 2048):.2f}), nodes {n}+{t:.4f}, s {s:.6f}; max error {e:.1e}')


if __name__ == '__main__':
    main()
