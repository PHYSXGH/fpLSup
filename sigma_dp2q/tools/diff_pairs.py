"""What changed between paired master/loader functions.

Pairs: compare_images.py matches of kind 'insns' (same instruction shape, numbers may differ) plus
differing functions paired by position (one unmatched function on each side between the same two matched
neighbours). For each pair, compared by meaning, not bytes:
  calls     BL/BLX targets mapped to master addresses through the function matches (a call to the
            "same" function in both images is equal even though the address differs)
  strings   text of strings loaded through literal pools / referenced as constants
  consts    plain numeric literals and instruction immediates (not addresses)
  ramrefs   count of pointers into RAM/BSS (0x0100xxxx, 0x41xxxxxx); layout differs, only counted
Prints per-category totals, the most common added/removed callees and strings, and writes a per-pair
report to <outdir>/pair_diffs.txt.

usage: python -I diff_pairs.py funcs_master.tsv funcs_loader.tsv <outdir>
"""
import sys, re, io, bisect, difflib, contextlib, collections, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import capstone as cs
import compare_images as C
from dp2q_lib import load, BASE

CODE_END = BASE + 0x210000
MD = {True: cs.Cs(cs.CS_ARCH_ARM, cs.CS_MODE_THUMB), False: cs.Cs(cs.CS_ARCH_ARM, cs.CS_MODE_ARM)}


def cstr(d, a):
    if not BASE <= a < BASE + len(d) - 1:
        return None
    o = a - BASE
    e = d.find(b'\0', o, o + 300)
    if e - o < 3:
        return None
    s = d[o:e]
    if all(32 <= c < 127 or c in (9, 10, 13) for c in s):
        return s.decode()
    return None


def facts(d, a, size, thumb, owner):
    """calls (as master-space function ids via owner()), strings, consts, ramrefs, n_insns"""
    calls, strs, consts, ram = collections.Counter(), collections.Counter(), collections.Counter(), 0
    n = 0
    for ins in MD[thumb].disasm(d[a - BASE:a - BASE + size], a):
        n += 1
        m, op = ins.mnemonic, ins.op_str
        if m in ('bl', 'blx') and op.startswith('#'):
            calls[owner(int(op[1:], 16))] += 1
            continue
        vals = []
        lit = re.match(r'(\w+), \[pc, #(-?0x[0-9a-f]+|-?\d+)\]', op)
        if m.startswith('ldr') and lit:
            pc = ((ins.address + (4 if thumb else 8)) & ~3) + int(lit.group(2), 0)
            if BASE <= pc < BASE + len(d) - 4:
                vals.append(struct.unpack_from('<I', d, pc - BASE)[0])
        elif m.startswith(('b', 'cb')) and not m.startswith('bic'):
            continue                                           # branch offsets: layout, not meaning
        else:
            vals += [int(x, 0) & 0xFFFFFFFF for x in re.findall(r'#(-?0x[0-9a-f]+|-?\d+)', op)]
        for v in vals:
            s = cstr(d, v)
            if s is not None:
                strs[s.replace('/M7_Loader/', '/M7_*/').replace('/M7_Master/', '/M7_*/')] += 1
            elif 0x01000000 <= v < 0x01010000 or 0x41000000 <= v < 0x42000000:
                ram += 1
            elif BASE <= v & ~1 < CODE_END:
                calls['ptr:' + str(owner(v & ~1))] += 1
            elif CODE_END <= v < BASE + 0xE00000:
                ram += 1                                       # data-area address (tables, images): moved
            else:
                consts[v] += 1
    return calls, strs, consts, ram, n


def main(fa, fb, outdir):
    with contextlib.redirect_stdout(io.StringIO()):
        match, ua, ub = C.main(fa, fb)
    A, B = C.rd(fa), C.rd(fb)
    da, _ = load('master'); db, _ = load('loader')
    inv = {b: a for a, (b, _) in match.items()}
    ea = sorted(A); eb = sorted(B)

    def containing(tab, ents, x):
        i = bisect.bisect_right(ents, x) - 1
        return ents[i] if i >= 0 and x < ents[i] + int(tab[ents[i]]['size']) else None

    matched_a = set(match)

    def own_a(x):
        if x < BASE:
            return f'ram:{x:#x}'                               # RAM block: same runtime layout at its start
        f = containing(A, ea, x)
        if f is None:
            return hex(x)
        return A[f]['name'] if f in matched_a else '(unmatched)'

    def own_b(x):                                              # loader target -> master function name
        if x < BASE:
            return f'ram:{x:#x}'
        f = containing(B, eb, x)
        if f is None:
            return hex(x)
        return A[inv[f]]['name'] if f in inv else '(unmatched)'

    pairs = [(a, b, 'insns') for a, (b, k) in match.items() if k == 'insns']
    # position pairs among genuinely differing functions
    def insn_set(un, T, d):
        return collections.Counter(C.insn_print(d, x, int(T[x]['size']), T[x]['thumb'] == '1') for x in un)
    pb_all, pa_all = insn_set(ub, B, db), insn_set(ua, A, da)
    dm = sorted(x for x in ua if x >= BASE and (p := C.insn_print(da, x, int(A[x]['size']), A[x]['thumb'] == '1')) and pb_all[p] == 0)
    dl = sorted(x for x in ub if x >= BASE and (p := C.insn_print(db, x, int(B[x]['size']), B[x]['thumb'] == '1')) and pa_all[p] == 0)
    anch = sorted((a, b) for a, (b, _) in match.items() if a >= BASE)
    am = [a for a, _ in anch]
    for x in dm:
        i = bisect.bisect_left(am, x)
        if 0 < i < len(am):
            lo, hi = anch[i - 1][1], anch[i][1]
            cand = dl[bisect.bisect_left(dl, lo):bisect.bisect_left(dl, hi)]
            gap = dm[bisect.bisect_left(dm, anch[i - 1][0]):bisect.bisect_left(dm, anch[i][0])]
            if hi > lo and len(cand) == 1 and len(gap) == 1:
                pairs.append((x, cand[0], 'position'))

    tot = collections.Counter(); add_c = collections.Counter(); rem_c = collections.Counter()
    add_s = collections.Counter(); rem_s = collections.Counter(); const_chg = collections.Counter()
    lines = []
    for a, b, kind in sorted(pairs):
        ra, rb = A[a], B[b]
        ca, sa, ka, rama, na = facts(da, a, int(ra['size']), ra['thumb'] == '1', own_a)
        cb, sb, kb, ramb, nb = facts(db, b, int(rb['size']), rb['thumb'] == '1', own_b)
        dc_add, dc_rem = cb - ca, ca - cb
        ds_add, ds_rem = sb - sa, sa - sb
        dk = (ka - kb) + (kb - ka)
        cats = []
        if dc_add or dc_rem: cats.append('calls')
        if ds_add or ds_rem: cats.append('strings')
        if dk: cats.append('consts')
        if na != nb: cats.append('length')
        if not cats: cats.append('none-visible')
        for c in cats: tot[(kind, c)] += 1
        add_c.update(dc_add); rem_c.update(dc_rem); add_s.update(ds_add); rem_s.update(ds_rem)
        if dk and not (dc_add or dc_rem or ds_add or ds_rem):
            const_chg[(tuple(sorted(k for k in ka - kb)), tuple(sorted(k for k in kb - ka)))] += 1
        lines.append(f'{a:#x} {b:#x} {kind} {ra["ns"]}::{ra["name"]} insns {na}->{nb} [{",".join(cats)}]'
                     + (f'\n    calls +{dict(dc_add)} -{dict(dc_rem)}' if dc_add or dc_rem else '')
                     + (f'\n    strings +{list(ds_add)} -{list(ds_rem)}' if ds_add or ds_rem else '')
                     + (f'\n    consts master-only {[hex(k) for k in (ka - kb)]} loader-only {[hex(k) for k in (kb - ka)]}' if dk else ''))
    Path(outdir, 'pair_diffs.txt').write_text('\n'.join(lines) + '\n')
    print(f'pairs {len(pairs)} (insns {sum(1 for p in pairs if p[2] == "insns")}, '
          f'position {sum(1 for p in pairs if p[2] == "position")})')
    for kind in ('insns', 'position'):
        print(f'  {kind}:', {c: n for (k, c), n in sorted(tot.items()) if k == kind})
    print('callees added in loader (most common):', add_c.most_common(15))
    print('callees removed in loader (most common):', rem_c.most_common(15))
    print('strings only in loader version:', add_s.most_common(15))
    print('strings only in master version:', rem_s.most_common(15))
    print('constant-only changes (master -> loader), most common:',
          [(tuple(hex(x) for x in m), tuple(hex(x) for x in l), n) for (m, l), n in const_chg.most_common(12)])


if __name__ == '__main__':
    main(*sys.argv[1:4])
