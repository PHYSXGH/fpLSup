"""Who calls the fp L's magnifier-table scanners, with which arguments (RAM only).  install | read | remove

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 magprobe.py CMD

The five functions scan descriptor +0x128 (stride 0x5C) for a mode id with the index starting at -1;
an id that is not there leaves -1 and they read the row before the table (2026-11-04, RESCUSTOM_PORT.md).
Each gets a stub at its first instruction (a push, run from the stub): count, and for the last eight
calls r0..r3 and lr (32-byte slots); then an r0 / r1 equal to our virtual mode id becomes the donor's.  Read it after the colourful lines: the shell outlives them.
"""
import json, os, struct, sys
import putfile as P, cave

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'magprobe.json')
F_DCACHE, F_ICACHE = 0xC000E91C, 0xC000EABC
FNS = [0xC0312338, 0xC0313E00, 0xC03141B8, 0xC03288E0, 0xC032E060]
STUB, REC = 23 * 4, 256
VMID, DONOR = 230, 161             # UHDX on card r4: our virtual mode, its donor


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


def install():
    first = [rd(f)[0] for f in FNS]
    for f, w in zip(FNS, first):
        if w & 0xFFFF0000 != 0xE92D0000:
            raise SystemExit(f'{f:#x} starts {w:#x}, not a push (already hooked?)')
    base = cave.claim('magprobe', len(FNS) * (STUB + REC))
    for k, (f, w0) in enumerate(zip(FNS, first)):
        s = base + k * STUB
        rec = base + len(FNS) * STUB + k * REC
        words = [0xE92D000C,            # push {r2, r3}
                 0xE59F204C,            # ldr r2, [pc, #0x4c] -> rec (word 22)
                 0xE5923000,            # ldr r3, [r2]
                 0xE2833001,            # add r3, r3, #1
                 0xE5823000,            # str r3, [r2]          count
                 0xE2033007,            # and r3, r3, #7
                 0xE0823283,            # add r3, r2, r3, lsl #5 slot
                 0xE5830004,            # str r0, [r3, #4]
                 0xE5831008,            # str r1, [r3, #8]
                 0xE583E00C,            # str lr, [r3, #12]
                 0xE59D2000,            # ldr r2, [sp]          caller's r2
                 0xE5832010,            # str r2, [r3, #16]
                 0xE59D2004,            # ldr r2, [sp, #4]      caller's r3
                 0xE5832014,            # str r2, [r3, #20]
                 0xE3510000 | VMID,     # cmp r1, #VMID         (logged as it came; then fixed:)
                 0x03A01000 | DONOR,    # moveq r1, #DONOR      our id -> the donor's
                 0xE3500000 | VMID,     # cmp r0, #VMID
                 0x03A00000 | DONOR,    # moveq r0, #DONOR
                 0xE8BD000C,            # pop {r2, r3}
                 w0,                    # the replaced push
                 0xE51FF004,            # ldr pc, [pc, #-4]
                 f + 4,
                 rec]
        assert len(words) * 4 == STUB
        for i, x in enumerate(words):
            setw(s + 4 * i, x)
        for i in range(REC // 4):
            setw(rec + 4 * i, 0)
    flush()
    for k, f in enumerate(FNS):
        s = base + k * STUB
        setw(f, 0xEA000000 | (((s - (f + 8)) >> 2) & 0xFFFFFF))
    flush()
    json.dump({'base': base, 'first': first}, open(STATE, 'w'))
    print(f'installed at {base:#x}')


def read():
    st = json.load(open(STATE))
    base = st['base']
    for k, f in enumerate(FNS):
        rec = base + len(FNS) * STUB + k * REC
        r = rd(rec, REC // 4)
        n = r[0]
        print(f'{f:#010x} calls {n}')
        for j in range(min(n, 8)):
            s = (n - j) & 7                         # newest first
            w = r[8 * s + 1: 8 * s + 6]
            print(f'    r0 {w[0]:#010x}  r1 {w[1]:#010x} ({w[1]})  r2 {w[3]:#010x}  r3 {w[4]:#010x}  lr {w[2]:#010x}')


def remove():
    st = json.load(open(STATE))
    for f, w in zip(FNS, st['first']):
        setw(f, w)
    flush()
    print('restored')


{'install': install, 'read': read, 'remove': remove}[sys.argv[1]]()
