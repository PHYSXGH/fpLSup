#!/usr/bin/env python3
"""Compare a profile's canvas on the fp and the fp L, field by field.

The canvas builder (fp FUN_c0439d18, fp L FUN_c043a090) stores the canvas column-wise:
canvas + off = column_off[row], row = MAPPING[profile].  This reads each builder's
(offset -> column) pairs from its code, then prints both profiles' values.

    canvas_compare.py FP_IMAGE FPL_IMAGE FP_PROFILE FPL_PROFILE
"""
import struct, sys
import capstone

FP = dict(builder=0xC0439D18, mapping=0xC0BD05D4)
FPL = dict(builder=0xC043A090, mapping=0xC0BF6820)
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)


def columns(img, start, n=1200):
    """{canvas offset: column base} from the builder's movw/movt; ldr [rX, rN, lsl #2]; str pattern"""
    out, reg, last = {}, {}, None
    for i in md.disasm(img[start - 0xC0000000:start - 0xC0000000 + 4 * n], start):
        op = i.op_str.replace(' ', '')
        ops = op.split(',')
        if i.mnemonic == 'movw':
            reg[ops[0]] = int(ops[1].lstrip('#'), 0)
        elif i.mnemonic == 'movt':
            reg[ops[0]] = (reg.get(ops[0], 0) & 0xFFFF) | int(ops[1].lstrip('#'), 0) << 16
        elif i.mnemonic == 'ldr' and 'lsl#2' in op:
            last = (ops[0], reg.get(op.split('[')[1].split(',')[0]))
        elif i.mnemonic == 'str' and '[' in op and last and last[0] == ops[0] and last[1]:
            m = op.split('[')[1].rstrip(']!').split(',')
            out[int(m[1].lstrip('#'), 0) if len(m) > 1 else 0] = last[1]
        elif (i.mnemonic == 'pop' and 'pc' in op) or (i.mnemonic == 'bx' and op == 'lr'):
            break
    return out


def main():
    fp_img, fpl_img = (open(p, 'rb').read() for p in sys.argv[1:3])
    pa, pb = int(sys.argv[3], 0), int(sys.argv[4], 0)
    w = lambda img, a: struct.unpack_from('<I', img, a - 0xC0000000)[0]     # noqa: E731
    ca, cb = columns(fp_img, FP['builder']), columns(fpl_img, FPL['builder'])
    ra, rb = w(fp_img, FP['mapping'] + 4 * pa), w(fpl_img, FPL['mapping'] + 4 * pb)
    print(f'fp p{pa} row {ra}, {len(ca)} fields | fp L p{pb} row {rb}, {len(cb)} fields')
    fmt = lambda v: '-' if v is None else (hex(v) if v >= 0x10000000 else str(v))   # noqa: E731
    for off in sorted(set(ca) | set(cb)):
        va = w(fp_img, ca[off] + 4 * ra) if off in ca else None
        vb = w(fpl_img, cb[off] + 4 * rb) if off in cb else None
        print(f'+0x{off:03X}  {fmt(va):>12}  {fmt(vb):>12}' + ('' if va == vb else '  *'))


if __name__ == '__main__':
    main()
