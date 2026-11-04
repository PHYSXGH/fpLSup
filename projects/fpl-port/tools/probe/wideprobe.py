"""Which per-mode table scanners see our virtual mode id at record start (RAM only).

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 wideprobe.py install | read | poll | remove

The fp L functions that walk a per-mode table inline (strided id compare in a loop, outside the
lookups res-custom hooks; found by the scan in RESCUSTOM_PORT.md).  Each gets a stub at its first
instruction (a push, run from the stub): {total calls, calls with r0..r3 == VMID, and the last such
call's r0, r1, r2, r3, lr}.  `poll` reads all records continuously, one line per change, so what
happens before the shell dies is kept.
"""
import json, os, struct, sys, time
import putfile as P, cave

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'wideprobe.json')
F_DCACHE, F_ICACHE = 0xC000E91C, 0xC000EABC
VMID = 230
FNS = [0xC0088EE0, 0xC008AA38, 0xC021D9B8, 0xC0221F80, 0xC02DB8F8, 0xC0310628, 0xC03106A8, 0xC0312338,
       0xC0313E00, 0xC03141B8, 0xC03288E0, 0xC032E060, 0xC032CF00, 0xC033E0E0, 0xC0345330, 0xC050AEB8,
       0xC056A370, 0xC05122D0, 0xC0512498]
NW = 27                                   # stub words
REC = 32                                  # record bytes


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


def stub(fn, first, rec):
    v = VMID
    w = [0xE92D000C,                     # 0  push {r2, r3}
         0xE59F205C,                     # 1  ldr r2, [pc, #0x5c] -> rec (word 26)
         0xE5923000,                     # 2  ldr r3, [r2]
         0xE2833001,                     # 3  add r3, r3, #1
         0xE5823000,                     # 4  str r3, [r2]          total
         0xE3500000 | v,                 # 5  cmp r0, #VMID
         0x13510000 | v,                 # 6  cmpne r1, #VMID
         0x159D3000,                     # 7  ldrne r3, [sp]        caller's r2
         0x13530000 | v,                 # 8  cmpne r3, #VMID
         0x159D3004,                     # 9  ldrne r3, [sp, #4]    caller's r3
         0x13530000 | v,                 # 10 cmpne r3, #VMID
         0x1A000009,                     # 11 bne 22
         0xE5923004,                     # 12 ldr r3, [r2, #4]
         0xE2833001,                     # 13 add r3, r3, #1
         0xE5823004,                     # 14 str r3, [r2, #4]      hits
         0xE5820008,                     # 15 str r0, [r2, #8]
         0xE582100C,                     # 16 str r1, [r2, #12]
         0xE59D3000,                     # 17 ldr r3, [sp]
         0xE5823010,                     # 18 str r3, [r2, #16]     r2
         0xE59D3004,                     # 19 ldr r3, [sp, #4]
         0xE5823014,                     # 20 str r3, [r2, #20]     r3
         0xE582E018,                     # 21 str lr, [r2, #24]     caller
         0xE8BD000C,                     # 22 pop {r2, r3}
         first,                          # 23 the replaced push
         0xE51FF004,                     # 24 ldr pc, [pc, #-4]
         fn + 4,                         # 25
         rec]                            # 26
    assert len(w) == NW
    return w


def install():
    first = [rd(f)[0] for f in FNS]
    for f, w in zip(FNS, first):
        if w & 0xFFFF0000 != 0xE92D0000:
            raise SystemExit(f'{f:#x} starts {w:#x}, not a push (already hooked?)')
    n = len(FNS)
    base = cave.claim('wideprobe', n * (NW * 4 + REC))
    recs = base + n * NW * 4
    for k, (f, w0) in enumerate(zip(FNS, first)):
        s, rec = base + k * NW * 4, recs + k * REC
        for i, x in enumerate(stub(f, w0, rec)):
            setw(s + 4 * i, x)
        for i in range(REC // 4):
            setw(rec + 4 * i, 0)
    flush()
    for k, f in enumerate(FNS):
        s = base + k * NW * 4
        setw(f, 0xEA000000 | (((s - (f + 8)) >> 2) & 0xFFFFFF))
    flush()
    json.dump({'base': base, 'recs': recs, 'first': first}, open(STATE, 'w'))
    print(f'installed {n} stubs at {base:#x}, records {recs:#x}')


def snapshot():
    st = json.load(open(STATE))
    r = P.mem_get(st['recs'], len(FNS) * REC // 4)
    if not r or None in r:
        return None
    out = []
    for k, f in enumerate(FNS):
        w = r[8 * k: 8 * k + 8]
        out.append((f, w[0], w[1], w[2:7]))
    return out


def show(snap):
    for f, total, hits, last in snap:
        if total or hits:
            extra = (f'  HITS {hits}: r0 {last[0]:#x} r1 {last[1]:#x} r2 {last[2]:#x} r3 {last[3]:#x} '
                     f'lr {last[4]:#010x}') if hits else ''
            print(f'  {f:#010x} calls {total}{extra}')


def read():
    s = snapshot()
    if s is None:
        raise SystemExit('read failed')
    show(s)


def poll():
    prev = None
    while True:
        s = snapshot()
        t = time.strftime('%H:%M:%S')
        if s is None:
            print(t, 'no answer', flush=True)
            time.sleep(0.2)
            continue
        key = [(f, tot > 0, h, tuple(l)) for f, tot, h, l in s]
        if key != prev:
            print(t, flush=True)
            show(s)
            sys.stdout.flush()
            prev = key


def remove():
    st = json.load(open(STATE))
    for f, w in zip(FNS, st['first']):
        setw(f, w)
    flush()
    print('restored')


{'install': install, 'read': read, 'poll': poll, 'remove': remove}[sys.argv[1]]()
