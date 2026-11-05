"""Shared helpers for the dp2 Quattro images unpacked by unpack_dp2q.py (load base 0x40000000)."""
import struct
from pathlib import Path

BASE = 0x40000000


OUT = Path(__file__).resolve().parents[2] / 'out_dp2q'     # repo root / out_dp2q, independent of cwd


def load(name, out=OUT):
    d = Path(out, f'{name}_40000000.bin').read_bytes()
    return d, len(d.rstrip(b'\xff'))


def thumb_calls(d, used, base=BASE):
    """Yield (site, target, is_blx) for every Thumb-2 BL/BLX encoding (unaligned scan: includes noise)."""
    for i in range(0, used - 4, 2):
        h1, h2 = struct.unpack_from('<HH', d, i)
        if h1 & 0xF800 != 0xF000 or h2 & 0xC000 != 0xC000:
            continue
        blx = not (h2 & 0x1000)
        s = (h1 >> 10) & 1
        j1 = (h2 >> 13) & 1; j2 = (h2 >> 11) & 1
        i1 = 1 - (j1 ^ s); i2 = 1 - (j2 ^ s)
        imm = (s << 24) | (i1 << 23) | (i2 << 22) | ((h1 & 0x3FF) << 12) | ((h2 & 0x7FF) << 1)
        if s:
            imm -= 1 << 25
        pc = base + i + 4
        t = ((pc & ~3) + imm) if blx else (pc + imm)
        yield base + i, t, blx


def veneers(d, used, base=BASE):
    """Map veneer address -> target for 'ldr pc,[pc,#-4]; .word T' (ARM) and Thumb 'movw ip; movt ip; bx ip'."""
    out = {}
    for i in range(0, used - 8, 4):
        if struct.unpack_from('<I', d, i)[0] == 0xE51FF004:
            out[base + i] = struct.unpack_from('<I', d, i + 4)[0]
    for i in range(0, used - 10, 2):
        h = struct.unpack_from('<5H', d, i)
        # movw ip,#lo : F240 0C00 pattern (Rd=ip=12) ; movt ip,#hi : F2C0 0C00 ; bx ip : 4760
        if (h[0] & 0xFBF0) == 0xF240 and (h[1] & 0x8F00) == 0x0C00 and (h[2] & 0xFBF0) == 0xF2C0 \
                and (h[3] & 0x8F00) == 0x0C00 and h[4] == 0x4760:
            def imm16(a, b):
                return ((a & 0xF) << 12) | (((a >> 10) & 1) << 11) | (((b >> 12) & 7) << 8) | (b & 0xFF)
            out[base + i] = (imm16(h[2], h[3]) << 16) | imm16(h[0], h[1])
    # veneers can chain (Thumb movw/movt veneer -> ARM ldr-pc veneer -> target): resolve to the end
    for v in list(out):
        t, seen = out[v], {v}
        while t & ~1 in out and t & ~1 not in seen:
            seen.add(t & ~1); t = out[t & ~1]
        out[v] = t
    return out


def arm_calls(d, used, base=BASE):
    """Yield (site, target) for ARM B/BL (cond != 0xF) and BLX imm (cond == 0xF)."""
    for i in range(0, used, 4):
        w = struct.unpack_from('<I', d, i)[0]
        if (w >> 25) & 7 != 5:
            continue
        off = ((w & 0xFFFFFF) ^ 0x800000) - 0x800000
        t = base + i + 8 + off * 4
        if w >> 28 == 0xF:
            t += ((w >> 24) & 1) * 2
        yield base + i, t


def callers(d, used, target, base=BASE, ven=None):
    """All direct call sites of target, through veneers too. Returns list of (site, mode, via)."""
    ven = veneers(d, used, base) if ven is None else ven
    tset = {target & ~1}
    via = {v: hex(v) for v, t in ven.items() if t & ~1 == target & ~1}
    tset |= set(via)
    out = [(s, 'T', via.get(t)) for s, t, _ in thumb_calls(d, used, base) if t & ~1 in tset]
    out += [(s, 'A', via.get(t)) for s, t in arm_calls(d, used, base) if t & ~1 in tset]
    return out
