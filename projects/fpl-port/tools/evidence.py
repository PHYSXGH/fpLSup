"""Evidence for a RAM/data address: every code site in fp that materialises a value
in [X-span, X] (literal pool or movw/movt), the matched site in fp L, and the value there.
   evidence.py X [--span 0x400]"""
import sys, struct, argparse, os, pickle
sys.path.insert(0, os.path.dirname(__file__))
from addrmap import AddrMap, BASE, ROOT, literal_refs, movw_movt_consts
from collections import Counter
ap = argparse.ArgumentParser(); ap.add_argument('x', nargs='+'); ap.add_argument('--span', type=lambda s: int(s, 0), default=0x400)
o = ap.parse_args(); m = AddrMap()
cache = ROOT / 'out_fpl/consts.pkl'
if cache.exists():
    CA, CB = pickle.load(open(cache, 'rb'))
else:
    def consts(buf):
        d = {off: struct.unpack_from('<I', buf, off)[0] for off in literal_refs(buf)}
        mw = dict(movw_movt_consts(buf))
        return d, mw
    CA, CB = consts(m.A), consts(m.B); pickle.dump((CA, CB), open(cache, 'wb'))
for xs in o.x:
    x = int(xs, 16); votes = Counter(); lines = []
    for kind, (da, db) in (('lit', (CA[0], CB[0])), ('movw', (CA[1], CB[1]))):
        for off, v in da.items():
            if x - o.span <= v <= x:
                b, how = m.map_img(BASE + off)
                w = db.get(b - BASE) if how == 'exact' else None
                d = (w - v) if w is not None else None
                if d is not None: votes[(v, d)] += 1
                lines.append((v, kind, BASE + off, b, w))
    per_base = {}
    for (v, d), c in votes.items(): per_base.setdefault(v, Counter())[d] += c
    print(f'== {x:#x}')
    for v in sorted(per_base, reverse=True)[:6]:
        ds = ', '.join(f'{d:+#x} x{c}' for d, c in per_base[v].most_common())
        print(f'   base {v:#x} (+{x - v:#x}): {ds}')
    if not per_base: print('   no evidence within span')
