"""Write a seeds CSV (addr,name,mode) for ghidra_scripts/DP2QSetup.java: reset vector, OS stubs,
T-Kernel call wrappers named by function code, and the 50 named tasks.

usage: python -I ghidra_seeds.py [master|loader] > seeds.csv
"""
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import capstone as cs
from dp2q_lib import BASE, load, arm_calls
from task_table import find_table, REC

# checked against use: 0x8001 tk_cre_tsk, 0x8038 tk_cre_mbx. Others: named by code only.
KNOWN = {0x80010100: 'tk_cre_tsk', 0x80380100: 'tk_cre_mbx'}


def svc_stubs(d, used):
    """ARM 'push {r4,lr}; svc #N; pop {r4,pc}' stubs."""
    out = {}
    for i in range(0, used - 12, 4):
        w = struct.unpack_from('<3I', d, i)
        if w[0] == 0xE92D4010 and w[2] == 0xE8BD8010 and w[1] & 0xFF000000 == 0xEF000000:
            out[BASE + i] = w[1] & 0xFFFFFF
    return out


def wrappers(d, used, stubs):
    md = cs.Cs(cs.CS_ARCH_ARM, cs.CS_MODE_ARM)
    res = {}
    for site, t in arm_calls(d, used):
        if t not in stubs:
            continue
        o = site - BASE
        code = start = None
        for k in range(4, 40, 4):
            ins = next(md.disasm(d[o - k:o - k + 4], site - k), None)
            ends = (ins is None                                    # literal / data word
                    or ins.mnemonic == 'bx' and ins.op_str == 'lr'
                    or ins.mnemonic.startswith('pop') and 'pc' in ins.op_str
                    or ins.mnemonic in ('b', 'bl'))
            if ends:                      # previous function's return / literal: wrapper starts after it
                start = site - k + 4; break
            if code is None and ins.mnemonic == 'ldr' and ins.op_str.startswith('r1, [pc'):
                imm = int(ins.op_str.split('#')[1].rstrip(']'), 16)
                code = struct.unpack_from('<I', d, o - k + 8 + imm)[0]
            if ins.mnemonic == 'push':
                start = site - k; break
        if code is not None and start is not None:
            res[start] = (code, stubs[t])
    return res


def main(name='master'):
    d, used = load(name)
    print(f'{BASE:#x},reset_vectors,A')
    stubs = svc_stubs(d, used)
    for a, n in stubs.items():
        print(f'{a:#x},svc{n}_stub,A')
    for a, (code, n) in sorted(wrappers(d, used, stubs).items()):
        nm = (KNOWN.get(code) if n == 6 else None) or (f'tk_{code >> 16 & 0xFF:02x}_{code:08x}' if code >> 24 == 0x80 and n == 6
                                 else f'td_{code:08x}' if n == 9 else f'svc{n}_{code:08x}')
        print(f'{a:#x},{nm},A')
    o, cnt = find_table(d, used)
    for k in range(cnt):
        w = struct.unpack_from('<13I', d, o + k * REC)
        nm = d[o + k * REC + 0x28:o + k * REC + 0x30].split(b'\0')[0].decode() or f'idx{k}'
        print(f'{w[2] & ~1:#x},task_{nm},{"T" if w[2] & 1 else "A"}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'master')
