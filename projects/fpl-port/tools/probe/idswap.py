"""Give chosen callers of the "recording entry's sensor mode" helper the donor's id (RAM only).

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 idswap.py install SITE[,SITE...] | read | remove

0xC0437290 asks the configurator for the recording entry and returns its sensor mode (+8): our virtual
id (230) for a res-custom row.  At each SITE (a `bl 0xC0437290`) the call goes through a stub that calls
the helper and turns VMID into DONOR; every other caller still sees the virtual id.  Each stub counts
its swaps.  A recording that works with a site swapped names that site's consumer.
"""
import json, os, struct, sys
import putfile as P, cave

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'idswap.json')
F_DCACHE, F_ICACHE = 0xC000E91C, 0xC000EABC
HELPER = 0xC0437290
VMID, DONOR = 230, 161
NW = 12


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


def call(fn):
    assert rd(P.ECHO_SLOT)[0] == P.ECHO_ORIG
    setw(P.ECHO_SLOT, fn)
    try:
        P.sh('echo', retries=0)
    finally:
        setw(P.ECHO_SLOT, P.ECHO_ORIG)


def flush():
    call(F_DCACHE)
    call(F_ICACHE)


def bl(at, to):
    return 0xEB000000 | (((to - (at + 8)) >> 2) & 0xFFFFFF)


def bl_target(at, w):
    off = w & 0xFFFFFF
    off -= (1 << 24) if off & 0x800000 else 0
    return at + 8 + 4 * off


def stub(s):
    w = [0xE92D4010,                 # 0  push {r4, lr}
         bl(s + 4, HELPER),          # 1  bl helper
         0xE3500000 | VMID,          # 2  cmp r0, #VMID
         0x1A000004,                 # 3  bne 9
         0xE3A00000 | DONOR,         # 4  mov r0, #DONOR
         0xE59F100C,                 # 5  ldr r1, [pc, #0xc] -> word 10
         0xE5912000,                 # 6  ldr r2, [r1]
         0xE2822001,                 # 7  add r2, r2, #1
         0xE5812000,                 # 8  str r2, [r1]       swaps
         0xE8BD8010,                 # 9  pop {r4, pc}
         s + 44,                     # 10 -> word 11
         0]                          # 11 the count
    assert len(w) == NW
    return w


def install():
    sites = [int(x, 16) for x in sys.argv[2].split(',')]
    orig = [rd(a)[0] for a in sites]
    for a, w in zip(sites, orig):
        if w & 0xFF000000 != 0xEB000000 or bl_target(a, w) != HELPER:
            raise SystemExit(f'{a:#x} holds {w:#x}, not bl {HELPER:#x}')
    base = cave.claim('idswap', len(sites) * NW * 4)
    for k, a in enumerate(sites):
        s = base + k * NW * 4
        for i, x in enumerate(stub(s)):
            setw(s + 4 * i, x)
    flush()
    for k, a in enumerate(sites):
        setw(a, bl(a, base + k * NW * 4))
    flush()
    json.dump({'base': base, 'sites': sites, 'orig': orig}, open(STATE, 'w'))
    print(f'{len(sites)} sites swapped through stubs at {base:#x}')


def read():
    st = json.load(open(STATE))
    for k, a in enumerate(st['sites']):
        print(f'  {a:#010x} swaps {rd(st["base"] + k * NW * 4 + 44)[0]}')


def remove():
    st = json.load(open(STATE))
    for a, w in zip(st['sites'], st['orig']):
        setw(a, w)
    flush()
    print('restored')


{'install': install, 'read': read, 'remove': remove}[sys.argv[1]]()
