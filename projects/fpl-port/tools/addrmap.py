"""fp 5.02 -> fp L 3.02 address translation.

image addresses: piecewise-constant runs from anchor_map.py (byte-identical alignment).
RAM addresses (beyond the image: .bss, heap, fixed buffers): learned from literal
pools — every aligned word at fp offset X whose value lies in RAM is paired with the
word at map(X) in the fp L image; votes give a delta per RAM region.

    from addrmap import AddrMap; m = AddrMap(); m.map(0xC0BAC2F8) -> (addr, how)
CLI:  python addrmap.py build        # learn RAM deltas, write out_fpl/ram_runs.json
      python addrmap.py 0xC0BAC2F8 ...
"""
import sys, json, bisect, struct
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[3]
BASE = 0xC0000000


class AddrMap:
    def __init__(self, root=ROOT):
        self.A = (root / 'out/MAIN_c0000000.bin').read_bytes()
        self.B = (root / 'out_fpl/MAIN_c0000000.bin').read_bytes()
        self.runs = json.load(open(root / 'out_fpl/anchor_runs.json'))
        self.starts = [r[0] for r in self.runs]
        rr = root / 'out_fpl/ram_runs.json'
        self.ram = json.load(open(rr)) if rr.exists() else []
        self.img_end_a = BASE + len(self.A)
        pp = root / 'out_fpl/ptr_points.json'
        self.pts = json.load(open(pp)) if pp.exists() else []
        self.pv = [p[0] for p in self.pts]

    def from_points(self, a):
        """delta from pointer pairs: exact hit, or bracketed by two points with equal delta."""
        i = bisect.bisect_right(self.pv, a) - 1
        if i >= 0 and self.pv[i] == a:
            return a + self.pts[i][1], f'ptr({self.pts[i][2]})'
        if 0 <= i and i + 1 < len(self.pts) and self.pts[i][1] == self.pts[i + 1][1]:
            return a + self.pts[i][1], 'ptr-between'
        return None, None

    def map_img(self, a):
        """fp image addr -> (fpL addr, 'exact'|'interp'|None)"""
        off = a - BASE
        i = bisect.bisect_right(self.starts, off) - 1
        if i < 0:
            return None, None
        s, e, d, n = self.runs[i]
        if off < e:
            return a + d, 'exact'
        return self.vote(a, [self.window_search(a), self.from_points(a),
                             ((a + d, 'interp') if i + 1 < len(self.runs) and self.runs[i + 1][2] == d else (None, None)),
                             self.nearest_below(a)])

    def fuzzy(self, a, span=96, radius=0x30000):
        """best halfword-similarity position for the code at a (for code that changed)."""
        import numpy as np
        off = (a - BASE) & ~1
        i = bisect.bisect_right(self.starts, off) - 1
        guess = off + self.runs[max(i, 0)][2]
        lo = max(0, guess - radius) & ~1; hi = min(len(self.B) - span, guess + radius)
        pat = np.frombuffer(self.A[off:off + span], dtype='<u2')
        hb = np.frombuffer(self.B[lo:hi + span], dtype='<u2')
        n = (hi - lo) // 2
        score = np.zeros(n, dtype=np.int32)
        for k in range(len(pat)):
            score += (hb[k:k + n] == pat[k])
        j = int(score.argmax()); best = int(score[j])
        score[max(0, j - 4):j + 5] = 0
        second = int(score.max())
        return BASE + lo + 2 * j + ((a - BASE) & 1), best / len(pat), second / len(pat)

    @staticmethod
    def vote(a, cands):
        got = [(r, h) for r, h in cands if r is not None]
        if not got:
            return None, 'gap'
        best = got[0]
        agree = [h for r, h in got if r == best[0]]
        clash = [f'{h}={r:#x}' for r, h in got if r != best[0]]
        tag = '+'.join(agree) + (' CONFLICT ' + ','.join(clash) if clash else '')
        return best[0], tag

    def window_search(self, a, words=12, radius=0x40000):
        """translate pointer words in a window around a and search fp L near the expected spot."""
        off = (a - BASE) & ~3
        best = None
        for lead in (0, 4, 8, words // 2, words - 2):
            s0 = off - lead * 4
            if s0 < 0:
                continue
            pat = []
            for k in range(words):
                v = struct.unpack_from('<I', self.A, s0 + 4 * k)[0]
                if BASE <= v < BASE + len(self.A):
                    t, how = self.map_img_basic(v)
                    v = t if t is not None else None
                pat.append(v)
            if sum(1 for v in pat if v not in (None, 0)) < 3:
                continue
            i = bisect.bisect_right(self.starts, off) - 1
            guess = off + (self.runs[max(i, 0)][2])
            hits = []
            lo = max(0, guess - radius) & ~3; hi = min(len(self.B) - 4 * words, guess + radius)
            first = next(k for k, v in enumerate(pat) if v is not None)
            needle = struct.pack('<I', pat[first])
            j = self.B.find(needle, lo + 4 * first)
            while j != -1 and j < hi + 4 * first:
                if (j - 4 * first) % 4 == 0:
                    c = j - 4 * first
                    if all(v is None or struct.unpack_from('<I', self.B, c + 4 * k)[0] == v for k, v in enumerate(pat)):
                        hits.append(c)
                j = self.B.find(needle, j + 1)
            if len(hits) == 1:
                cand = BASE + hits[0] + lead * 4 + ((a - BASE) & 3)
                if best is None or best != cand:
                    best = cand if best is None else 'conflict'
        if best and best != 'conflict':
            return best, 'window'
        return None, 'gap'

    def map_img_basic(self, a):
        off = a - BASE
        i = bisect.bisect_right(self.starts, off) - 1
        if i >= 0 and off < self.runs[i][1]:
            return a + self.runs[i][2], 'exact'
        return None, None

    def nearest_below(self, a, maxdist=0x400):
        i = bisect.bisect_right(self.pv, a) - 1
        if i >= 0 and a - self.pv[i] <= maxdist:
            return a + self.pts[i][1], f'ptr-base-{a - self.pv[i]:#x}?'
        return None, None

    def map_ram(self, a):
        r, how = self.from_points(a)
        if r is not None:
            return r, how
        r, how = self.nearest_below(a)
        if r is not None:
            return r, how
        for s, e, d, n in self.ram:
            if s <= a < e:
                return a + d, f'ram({n})'
        return None, 'ram-unknown'

    def map(self, a):
        if BASE <= a < self.img_end_a:
            return self.map_img(a)
        if self.img_end_a <= a < 0xD0000000:
            return self.map_ram(a)
        return a, 'unchanged(io/other)'


def literal_refs(buf):
    """offsets of words loaded PC-relative (ARM ldr/Thumb ldr literal)."""
    import numpy as np
    out = set()
    w = np.frombuffer(buf[:len(buf)//4*4], dtype='<u4')
    idx = np.nonzero((w & 0x0F7F0000) == 0x051F0000)[0]           # ARM ldr rd,[pc,#+-imm]
    for i in idx.tolist():
        x = int(w[i]); imm = x & 0xFFF
        t = i*4 + 8 + (imm if x & 0x800000 else -imm)
        if 0 <= t < len(buf) - 3 and t % 4 == 0: out.add(t)
    h = np.frombuffer(buf[:len(buf)//2*2], dtype='<u2')
    idx = np.nonzero((h & 0xF800) == 0x4800)[0]                    # T1 ldr rd,[pc,#imm8*4]
    for i in idx.tolist():
        t = ((i*2 + 4) & ~3) + (int(h[i]) & 0xFF)*4
        if t < len(buf) - 3: out.add(t)
    idx = np.nonzero((h[:-1] & 0xFF7F) == 0xF85F)[0]                # T2 ldr.w rt,[pc,#+-imm12]
    for i in idx.tolist():
        imm = int(h[i+1]) & 0xFFF
        t = ((i*2 + 4) & ~3) + (imm if h[i] & 0x80 else -imm)
        if 0 <= t < len(buf) - 3 and t % 4 == 0: out.add(t)
    return out


def movw_movt_consts(buf):
    """[(offset_of_movw, value)] for ARM and Thumb-2 movw/movt pairs on the same register."""
    import numpy as np
    res = []
    W = np.frombuffer(buf[:len(buf)//4*4], dtype='<u4')
    aimm = lambda x: ((x >> 4) & 0xF000) | (x & 0xFFF)
    for i in np.nonzero((W & 0x0FF00000) == 0x03000000)[0].tolist():
        x = int(W[i]); rd = (x >> 12) & 15
        for k in range(1, 9):
            if i + k >= len(W): break
            y = int(W[i + k])
            if (y & 0x0FF00000) == 0x03400000 and ((y >> 12) & 15) == rd:
                res.append((i * 4, (aimm(y) << 16) | aimm(x))); break
    H = np.frombuffer(buf[:len(buf)//2*2], dtype='<u2')
    timm = lambda h1, h2: ((h1 & 0xF) << 12) | (((h1 >> 10) & 1) << 11) | (((h2 >> 12) & 7) << 8) | (h2 & 0xFF)
    for i in np.nonzero((H[:-1] & 0xFBF0) == 0xF240)[0].tolist():
        h1, h2 = int(H[i]), int(H[i + 1]); rd = (h2 >> 8) & 15
        for k in range(2, 18):
            if i + k + 1 >= len(H): break
            g1, g2 = int(H[i + k]), int(H[i + k + 1])
            if (g1 & 0xFBF0) == 0xF2C0 and ((g2 >> 8) & 15) == rd:
                res.append((i * 2, (timm(g1, g2) << 16) | timm(h1, h2))); break
    return res


def build_ram():
    m = AddrMap()
    A, B = m.A, m.B
    lo, hi = BASE, 0xD0000000
    refs = literal_refs(A)
    byv = defaultdict(Counter)
    for off in refs:
        v = struct.unpack_from('<I', A, off)[0]
        if not (lo <= v < hi):
            continue
        b, how = m.map_img(BASE + off)
        if how != 'exact':
            continue
        w = struct.unpack_from('<I', B, b - BASE)[0]
        if lo <= w < hi and v % 4 == 0:
            byv[v][w - v] += 1
    # movw/movt pairs: decode at the mapped position in fp L
    bmw = dict(movw_movt_consts(B))
    nmw = 0
    for off, v in movw_movt_consts(A):
        if not (lo <= v < hi) or v % 4:
            continue
        b, how = m.map_img(BASE + off)
        if how != 'exact':
            continue
        w = bmw.get(b - BASE)
        if w is not None and lo <= w < hi:
            byv[v][w - v] += 1; nmw += 1
    print('movw/movt pairs used', nmw)
    pts = []
    for v, c in sorted(byv.items()):
        d, top = c.most_common(1)[0]; tot = sum(c.values())
        if top * 3 >= tot * 2:
            pts.append((v, d, top))
    # segment: a run continues while the delta stays the same
    runs = []
    for v, d, n in pts:
        if runs and runs[-1][2] == d:
            runs[-1][1] = v + 4; runs[-1][3] += 1
        else:
            runs.append([v, v + 4, d, 1])
    json.dump(pts, open(ROOT / 'out_fpl/ptr_points.json', 'w'))
    runs = [r for r in runs if r[0] >= m.img_end_a]
    json.dump(runs, open(ROOT / 'out_fpl/ram_runs.json', 'w'))
    print('literal refs', len(refs), 'ram values', len(pts), 'runs', len(runs))
    for r in runs:
        if r[3] >= 2 or r[2] != 0:
            print(f'{r[0]:#x}-{r[1]:#x}  delta {r[2]:+#x}  pts {r[3]}')


if __name__ == '__main__':
    if sys.argv[1] == 'build':
        build_ram()
    else:
        m = AddrMap()
        for x in sys.argv[1:]:
            a = int(x, 16)
            r, how = m.map(a)
            print(f'{a:#010x} -> {r:#010x} {how}' if r is not None else f'{a:#010x} -> ? {how}')
