"""Compare an fp card with the fp L card built from the same sources and options.

    card_check.py FP_CARD_DIR FPL_CARD_DIR

1. fpSup.BIN: same section count and lengths.  Word by word:
   - differing words must be fw(fp word), or ARM bl/b whose target maps;
   - equal words that look like firmware addresses must not move on the fp L
     (fw(w) == w), or they are an untranslated fp address.
2. Every section placed into the firmware image: the stock word there must be the
   same instruction/data in both images (so a 'restore'/hook word is right).
3. AutoRun.txt: `mem set A V` lines pair up; A and V obey the same rules.
Exit status 1 if anything is unexplained.
"""
import sys, struct, re, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'fpSup/fp_usb_shell')); sys.path.insert(0, str(Path(__file__).parent))
os.environ['FPSUP_CAMERA'] = 'fpl'
from fwtarget import fw, UnmappedAddress
from addrmap import AddrMap, BASE
m = AddrMap(); IMG_END = BASE + len(m.A)
LO, HI = 0xC0000000, 0xD0000000

def tr(v):
    try: return fw(v)
    except UnmappedAddress: return None

def parse_bin(p):
    b = Path(p).read_bytes()
    assert b[:4] == b'VBIN', p
    n, entry, plen = struct.unpack_from('<III', b, 4)
    secs = []; off = 16 + 8 * n
    for i in range(n):
        dest, ln = struct.unpack_from('<II', b, 16 + 8 * i)
        secs.append((dest, b[off:off + ln])); off += (ln + 3) & ~3
    return entry, secs

def bl_target(w, at):
    if (w & 0x0E000000) == 0x0A000000 and (w >> 28) != 0xF:
        o = w & 0xFFFFFF; o = o - (1 << 24) if o & 0x800000 else o
        return at + 8 + 4 * o
    return None

problems = []
def word_rule(fw_w, fl_w, where, at_fp=None, at_fl=None):
    if fw_w == fl_w:
        if LO <= fw_w < HI:
            t = tr(fw_w)
            if t is not None and t != fw_w:
                problems.append(f'{where}: {fw_w:#010x} unchanged but the fp L address is {t:#010x}')
        return
    if LO <= fw_w < HI and tr(fw_w) == fl_w:
        return
    if at_fp is not None:
        a, b = bl_target(fw_w, at_fp), bl_target(fl_w, at_fl)
        if a is not None and b is not None and (fw_w >> 24) == (fl_w >> 24) and (tr(a) == b or (a - at_fp) == (b - at_fl)):
            return
    problems.append(f'{where}: fp {fw_w:#010x} vs fp L {fl_w:#010x} (fw -> {tr(fw_w) and hex(tr(fw_w))})')

def compare_words(WA, WB, base_a, base_b, label, addrs_a=None, addrs_b=None):
    done = set()
    imm = lambda x: ((x >> 4) & 0xF000) | (x & 0xFFF)
    for j, x in enumerate(WA):                       # ARM movw/movt pairs, same Rd
        if (x & 0x0FF00000) != 0x03000000: continue
        for k in range(j + 1, min(j + 9, len(WA))):
            y = WA[k]
            if (y & 0x0FF00000) == 0x03400000 and ((y >> 12) & 15) == ((x >> 12) & 15):
                xb, yb = WB[j], WB[k]
                if (xb & 0xFFF0F000) != (x & 0xFFF0F000) or (yb & 0xFFF0F000) != (y & 0xFFF0F000):
                    problems.append(f'{label} +{4*j:#x}: movw/movt shape differs'); break
                word_rule((imm(y) << 16) | imm(x), (imm(yb) << 16) | imm(xb), f'{label}+{4*j:#x} movw/movt')
                done.update((j, k)); break
    for j in range(len(WA)):
        if j in done: continue
        aa = addrs_a[j] if addrs_a else (base_a + 4 * j if base_a is not None else None)
        ab = addrs_b[j] if addrs_b else (base_b + 4 * j if base_b is not None else None)
        word_rule(WA[j], WB[j], f'{label}+{4*j:#x}', aa, ab)

fa, fb = sys.argv[1], sys.argv[2]
ea, sa = parse_bin(Path(fa) / 'fpSup.BIN'); eb, sb = parse_bin(Path(fb) / 'fpSup.BIN')
if len(sa) != len(sb): problems.append(f'section count {len(sa)} vs {len(sb)}')
word_rule(ea, eb, 'entry')
stock = []
for i, ((da, ba), (db, bb)) in enumerate(zip(sa, sb)):
    word_rule(da, db, f'section {i} destination')
    if len(ba) != len(bb):
        problems.append(f'section {i} @{db:#x}: length {len(ba)} vs {len(bb)}'); continue
    WA = struct.unpack(f'<{len(ba)//4}I', ba[:len(ba)//4*4]); WB = struct.unpack(f'<{len(bb)//4}I', bb[:len(bb)//4*4])
    compare_words(WA, WB, da if da >= 0x40000000 else None, db if db >= 0x40000000 else None, f'section {i} @{db:#x}')
    if BASE <= db < IMG_END and BASE <= da < IMG_END:
        oa = m.A[da - BASE: da - BASE + len(ba)]; ob = m.B[db - BASE: db - BASE + len(bb)]
        same = oa == ob
        if not same:   # allow relative-branch / address differences that map
            ok = True
            for k in range(0, len(oa) - 3, 4):
                wa, wb = struct.unpack_from('<I', oa, k)[0], struct.unpack_from('<I', ob, k)[0]
                n0 = len(problems); word_rule(wa, wb, f'stock under section {i}', da + k, db + k)
                if len(problems) > n0: ok = False
            same = ok
        stock.append((db, len(bb), 'stock words equivalent' if same else 'STOCK DIFFERS'))

ra = [l.split() for l in (Path(fa) / 'AutoRun.txt').read_text().splitlines() if l.startswith('mem set')]
rb = [l.split() for l in (Path(fb) / 'AutoRun.txt').read_text().splitlines() if l.startswith('mem set')]
if len(ra) != len(rb): problems.append(f'AutoRun mem set count {len(ra)} vs {len(rb)}')
compare_words([int(x[3], 16) for x in ra], [int(y[3], 16) for y in rb], None, None, 'AutoRun mem set values',
              [int(x[2], 16) for x in ra], [int(y[2], 16) for y in rb])
for i, (x, y) in enumerate(zip(ra, rb)):
    A0, V0, A1, V1 = int(x[2], 16), int(x[3], 16), int(y[2], 16), int(y[3], 16)
    word_rule(A0, A1, f'AutoRun mem set #{i} address')
    if BASE <= A1 < IMG_END and not (fw(0xC072D000) <= A1 < fw(0xC0735000)):
        word_rule(struct.unpack_from('<I', m.A, A0 - BASE)[0], struct.unpack_from('<I', m.B, A1 - BASE)[0],
                  f'stock word under AutoRun write {A1:#x}', A0, A1)
        stock.append((A1, 4, 'AutoRun write'))

for s in stock: print(f'  firmware write {s[0]:#010x} {s[1]:5d} B  {s[2]}')
print(f'{len(sa)} sections, {len(ra)} AutoRun writes compared')
if problems:
    print(f'{len(problems)} unexplained:'); [print('  ' + p) for p in problems[:60]]; sys.exit(1)
print('all differences explained by the address table')
