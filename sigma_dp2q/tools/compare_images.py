"""Match functions between two dp2q Ghidra exports (DP2QExportFuncs.java) and report what differs.

Matching, in order:
  name   same non-default name in both (string-derived names; module-file names like dd_uart_<addr> and
         FUN_/thunk_ are excluded because they embed addresses); a name used k times on both sides is
         paired in address order
  bytes  same fingerprint: the function's bytes with Thumb BL/BLX immediates and 32-bit words that look
         like addresses (0x0100xxxx, 0x40xxxxxx-0x41xxxxxx) zeroed; only fingerprints unique on both sides
  insns  same instruction sequence with every immediate / offset replaced by '#' (survives literal-pool
         and branch offsets moving when the image is relinked); unique on both sides
Prints counts, then the unmatched functions on each side grouped by namespace (task owner).

usage: python -I compare_images.py funcs_master.tsv funcs_loader.tsv [--list]
"""
import sys, csv, struct, hashlib, collections, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dp2q_lib import BASE, load

ADDRISH = lambda w: 0x01000000 <= w < 0x01010000 or 0x40000000 <= w < 0x42000000


def rd(p):
    return {int(r['addr'], 16): r for r in csv.DictReader(open(p), delimiter='\t')}


def fingerprint(d, a, size, thumb):
    if a < BASE or size <= 0 or a - BASE + size > len(d):
        return None
    b = bytearray(d[a - BASE:a - BASE + size])
    if thumb:
        i = 0
        while i + 4 <= len(b):
            h1, h2 = struct.unpack_from('<HH', b, i)
            if h1 & 0xF800 == 0xF000 and h2 & 0xC000 == 0xC000:      # BL / BLX imm
                b[i:i + 4] = b'\0\xf0\0\xd0'; i += 4
            else:
                i += 2
    for i in range(0, len(b) - 3, 4):                                   # literal-pool style words
        if ADDRISH(struct.unpack_from('<I', b, i)[0]):
            b[i:i + 4] = b'\0\0\0\0'
    if not thumb:                                                       # ARM BL: keep opcode, drop offset
        for i in range(0, len(b) - 3, 4):
            w = struct.unpack_from('<I', b, i)[0]
            if (w >> 25) & 7 == 5:
                struct.pack_into('<I', b, i, w & 0xFF000000)
    return hashlib.sha1(bytes(b)).hexdigest()


_MD = {}


def insn_print(d, a, size, thumb):
    """Instruction sequence with immediates/offsets replaced: robust to relinking."""
    import capstone as cs
    if a < BASE or size <= 0 or a - BASE + size > len(d):
        return None
    md = _MD.get(thumb)
    if md is None:
        md = _MD[thumb] = cs.Cs(cs.CS_ARCH_ARM, cs.CS_MODE_THUMB if thumb else cs.CS_MODE_ARM)
    out = []
    for ins in md.disasm(d[a - BASE:a - BASE + size], a):
        out.append(ins.mnemonic + ' ' + re.sub(r'#-?(0x)?[0-9a-f]+', '#', ins.op_str))
    if len(out) < 4:                         # too short to be distinctive
        return None
    return hashlib.sha1('\n'.join(out).encode()).hexdigest()


def plain_name(n):
    return not (n.startswith(('FUN_', 'thunk_', 'LAB_')) or re.search(r'_[0-9a-f]{8}$', n))


def main(pa, pb, listing=False):
    A, B = rd(pa), rd(pb)
    da, _ = load('master'); db, _ = load('loader')
    match = {}
    na = collections.defaultdict(list); nb = collections.defaultdict(list)
    for a, r in A.items():
        if plain_name(r['name']): na[r['name']].append(a)
    for b, r in B.items():
        if plain_name(r['name']): nb[r['name']].append(b)
    for n in na.keys() & nb.keys():
        if len(na[n]) == len(nb[n]):
            for x, y in zip(sorted(na[n]), sorted(nb[n])):
                match[x] = (y, 'name')
    fa = collections.defaultdict(list); fb = collections.defaultdict(list)
    for a, r in A.items():
        if a not in match:
            f = fingerprint(da, a, int(r['size']), r['thumb'] == '1')
            if f: fa[f].append(a)
    used_b = {v[0] for v in match.values()}
    for b, r in B.items():
        if b not in used_b:
            f = fingerprint(db, b, int(r['size']), r['thumb'] == '1')
            if f: fb[f].append(b)
    for f in fa.keys() & fb.keys():
        if len(fa[f]) == 1 and len(fb[f]) == 1:
            match[fa[f][0]] = (fb[f][0], 'bytes')
    used_b = {v[0] for v in match.values()}
    ia = collections.defaultdict(list); ib = collections.defaultdict(list)
    for a, r in A.items():
        if a not in match:
            f = insn_print(da, a, int(r['size']), r['thumb'] == '1')
            if f: ia[f].append(a)
    for b, r in B.items():
        if b not in used_b:
            f = insn_print(db, b, int(r['size']), r['thumb'] == '1')
            if f: ib[f].append(b)
    for f in ia.keys() & ib.keys():
        if len(ia[f]) == 1 and len(ib[f]) == 1:
            match[ia[f][0]] = (ib[f][0], 'insns')
    by = collections.Counter(v[1] for v in match.values())
    ua = sorted(set(A) - set(match)); ub = sorted(set(B) - {v[0] for v in match.values()})
    print(f'master {len(A)}  loader {len(B)}  matched {len(match)} '
          f'(name {by["name"]}, bytes {by["bytes"]}, insns {by["insns"]})')
    print(f'unmatched: master {len(ua)}  loader {len(ub)}')
    for label, un, T in (('master-only', ua, A), ('loader-only', ub, B)):
        c = collections.Counter(T[x]['ns'] or '(global)' for x in un)
        print(f'{label} by namespace: {dict(c.most_common(12))}')
        named = [T[x]['name'] for x in un if plain_name(T[x]['name'])]
        print(f'{label} named ({len(named)}): {named[:40]}')
        if listing:
            for x in un:
                print(f'  {label} {x:#x} {T[x]["ns"]}::{T[x]["name"]} size {T[x]["size"]}')
    return match, ua, ub


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], '--list' in sys.argv)
