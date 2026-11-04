"""The R10 {value, mode} table (descriptor +0x10 / +0x14) and the core's answer for its virtual mode.
Read-only.

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 r10check.py [MODE ...]

lk_r10 (FUN_c03240b8) returns the VALUE of the pair whose mode matches -- and pair 0's value when none
does.  res-custom answers its virtual mode with the donor's value only if the donor has a pair
(vm.R10OK); otherwise the lookup goes down to the firmware with the virtual id.
"""
import sys
import putfile as P

SENSOR_OBJ = 0xC343C4C0
VM_R10, VM_R10OK = 0x40, 0x44


def rd(a, n=1):
    for _ in range(8):
        r = P.mem_get(a, n)
        if r and None not in r:
            return r
    raise SystemExit(f'read {a:#x} failed')


def main():
    desc = rd(SENSOR_OBJ)[0]
    base, count = rd(desc + 0x10, 2)
    pairs = [tuple(rd(base + 8 * i, 2)) for i in range(count)] if 0 < count < 400 else []
    print(f'descriptor {desc:#x}: R10 table {base:#x} x{count}')
    print(f'  pair 0 (the fallback): value {pairs[0][0]:#x} mode {pairs[0][1]}' if pairs else '  (no pairs)')
    by_mode = {}
    for v, m in pairs:
        by_mode.setdefault(m, []).append(v)
    for m in [161, 3, 230, 60] + [int(x) for x in sys.argv[1:]]:
        print(f'  mode {m}: {[hex(v) for v in by_mode.get(m, [])] or "no pair"}')
    print(f'  modes with a pair: {sorted(by_mode)}')
    w = rd(0xC043BAB0)[0]
    off = w & 0xFFFFFF
    off -= (1 << 24) if off & 0x800000 else 0
    ven = 0xC043BAB0 + 8 + 4 * off
    S = rd(ven + 4)[0] - 504 + 0x1400
    vm = S + rd(S + 0x44)[0]
    v = rd(vm, 18)
    print(f'core vm {vm:#x}: id {v[0]} donor {v[1]} filled {v[2]}  R10 {v[VM_R10 // 4]:#x}  R10OK {v[VM_R10OK // 4]}')


main()
