"""Point the core's virtual-mode rows at the donor's real rows (RAM only).  show | apply [KINDS]

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 realidx.py show
    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 realidx.py apply [TIM,META,R28,R38,R14,R68,REG]

res-custom answers a lookup for its virtual mode with a "fake index": base + index * stride lands on
the virtual mode's cloned row (vm.PTR[k]).  Pointing vm.PTR[k] at the donor's own row in the firmware's
table makes the same lookup return the donor's real index (0..84) instead -- the rows are the donor's
anyway for UHDX.  If recording then works, the culprit uses the fake index, and doing this table by
table (KINDS) narrows it.  Marks the record filled so the core does not clone over it.
"""
import json, os, struct, sys
import putfile as P

HERE = os.path.dirname(os.path.abspath(__file__))
SENSOR_OBJ = 0xC343C4C0          # r0 of the index getters (fnprobe, 2026-11-04)
REG_OBJ = 0xC343C5B4             # r0 of the register-record handler
KINDS = [('TIM', 0x00, 0x04, 0x20), ('META', 0x08, 0x0C, 100), ('R28', 0x24, 0x28, 0x28),
         ('R38', 0x40, 0x44, 0x38), ('R14', 0x48, 0x4C, 0x14), ('R68', 0xF4, 0xF8, 0x68),
         ('REG', 0x00, 0x04, 0x460)]
VM_ID, VM_DONOR, VM_FILLED, VM_REGFILLED, VM_PTR = 0x00, 0x04, 0x08, 0x0C, 0x20


def setw(a, v):
    for _ in range(8):
        P.mem_set(a, v & 0xFFFFFFFF)
        r = P.mem_get(a)
        if r and r[0] == (v & 0xFFFFFFFF):
            return
    raise SystemExit(f'write {a:#x} did not stick')


def rd(a, n=1):
    for _ in range(8):
        r = P.mem_get(a, n)
        if r and None not in r:
            return r
    raise SystemExit(f'read {a:#x} failed')


def find_vm():
    """the core's S (from the pick8 veneer), then its first virtual mode record"""
    w = rd(0xC043BAB0)[0]
    off = w & 0xFFFFFF
    off -= (1 << 24) if off & 0x800000 else 0
    ven = 0xC043BAB0 + 8 + 4 * off
    v = rd(ven, 2)
    assert v[0] == 0xE51FF004, hex(v[0])
    S = v[1] - 504 + 0x1400
    return S + rd(S + 0x44)[0]


def rows(donor):
    out = {}
    for name, fb, fc, stride in KINDS:
        desc = rd(REG_OBJ if name == 'REG' else SENSOR_OBJ)[0]
        base, count = rd(desc + fb)[0], rd(desc + fc)[0]
        if not 0 < count < 200:
            raise SystemExit(f'{name}: count {count} at desc {desc:#x}+{fc:#x} -- wrong object?')
        ids = [rd(base + stride * i)[0] for i in range(count)]
        if donor not in ids:
            raise SystemExit(f'{name}: mode {donor} not in the table at {base:#x}')
        i = ids.index(donor)
        out[name] = (base, count, i, base + stride * i)
    return out


def show():
    vm = find_vm()
    v = rd(vm, 16)
    print(f'vm {vm:#x}: id {v[0]} donor {v[1]} filled {v[2]} regfilled {v[3]} ptr {[hex(x) for x in v[8:15]]}')
    for name, (base, count, i, row) in rows(v[1]).items():
        print(f'  {name:4s} table {base:#x} x{count}: donor row {i} at {row:#x}')


def apply():
    want = sys.argv[2].split(',') if len(sys.argv) > 2 else [k for k, *_ in KINDS]
    vm = find_vm()
    donor = rd(vm + VM_DONOR)[0]
    r = rows(donor)
    for k, (name, *_) in enumerate(KINDS):
        if name in want:
            setw(vm + VM_PTR + 4 * k, r[name][3])
    setw(vm + VM_FILLED, 1)
    if 'REG' in want:
        setw(vm + VM_REGFILLED, 1)
    print('vm.PTR ->', {n: hex(r[n][3]) for n in want})
    show()


{'show': show, 'apply': apply}[sys.argv[1]]()
