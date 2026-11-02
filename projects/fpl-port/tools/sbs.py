"""Side-by-side disassembly: fp address vs fp L candidate.
   sbs.py ADDR [FPL_ADDR] [-n N] [--thumb] [--words]"""
import sys, struct, argparse
sys.path.insert(0, __import__('os').path.dirname(__file__))
from addrmap import AddrMap, BASE
import capstone as C
ap = argparse.ArgumentParser(); ap.add_argument('a'); ap.add_argument('b', nargs='?')
ap.add_argument('-n', type=int, default=12); ap.add_argument('--thumb', action='store_true')
ap.add_argument('--words', action='store_true'); ap.add_argument('--before', type=int, default=4)
o = ap.parse_args(); m = AddrMap()
a = int(o.a, 16); b = int(o.b, 16) if o.b else m.map(a)[0]
def show(buf, x):
    if o.words:
        s = x - 4 * o.before
        return [f'{s+4*i:#010x}: {struct.unpack_from("<I", buf, s+4*i-BASE)[0]:#010x}' for i in range(o.n)]
    md = C.Cs(C.CS_ARCH_ARM, C.CS_MODE_THUMB if o.thumb else C.CS_MODE_ARM)
    s = x - (2 if o.thumb else 4) * o.before
    return [f'{i.address:#010x}: {i.mnemonic} {i.op_str}' for i in md.disasm(buf[s-BASE:s-BASE+8*o.n], s)][:o.n]
L = show(m.A, a); R = show(m.B, b) if b else []
print(f'{"fp " + hex(a):52} fpL {hex(b) if b else "?"}')
for i in range(max(len(L), len(R))):
    print(f'{(L[i] if i < len(L) else ""):52} {(R[i] if i < len(R) else "")}')
