"""Which per-mode table loop searches for our virtual mode id (RAM only).  install | read | poll | remove

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 cmpprobe.py CMD

The compare inside every inline per-mode scan on the fp L (the row's id against the wanted id), and the
firmware loops inside the lookups res-custom hooks (they run only when the core passes a lookup down), are
replaced by a branch to a stub: count all, count those whose wanted id is VMID, then the original compare
(flags as before) and back.  Unlike wideprobe, an id read from memory is caught too.  `poll` keeps what
arrives before the shell dies.
"""
import json, os, struct, sys, time
import putfile as P, cave

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'cmpprobe.json')
F_DCACHE, F_ICACHE = 0xC000E91C, 0xC000EABC
VMID = 230
REGS = {f'r{i}': i for i in range(13)} | {'sl': 10, 'fp': 11, 'ip': 12}
# (compare site, the register holding the wanted id, what it is)
SITES = [
    (0xC0088F20, 'r8', 'scan 0x2c'), (0xC008AA9C, 'r3', 'scan 0x2c'), (0xC021DC1C, 'ip', 'scan 0x38'),
    (0xC0221FE4, 'r2', 'scan 0x38'), (0xC0222068, 'r2', 'scan 0x38'), (0xC02DB928, 'r7', 'scan 0x38'),
    (0xC0310700, 'r3', 'scan 0x38'), (0xC0312864, 'r5', 'mag scan'), (0xC031321C, 'r5', 'mag scan'),
    (0xC0313E50, 'r8', 'mag scan'), (0xC03141FC, 'r8', 'mag scan'), (0xC0328920, 'r3', 'mag scan'),
    (0xC032C6F4, 'r5', 'mag scan'), (0xC032CF34, 'sl', 'scan 0x38'), (0xC032E0F0, 'r2', 'mag scan'),
    (0xC033E1A4, 'r5', 'scan 0x20'), (0xC034542C, 'r1', 'scan 0xcc'), (0xC050AEE0, 'ip', 'scan 0x20'),
    (0xC0512368, 'r8', 'scan 0x2c'), (0xC0512528, 'ip', 'scan 0x2c'), (0xC056A3E4, 'r5', 'scan 0x20'),
    (0xC0324C84, 'r5', 'lk_meta loop'), (0xC0324CE8, 'r5', 'lk_tim loop'), (0xC0324D4C, 'r5', 'lk_r68 loop'),
    (0xC03250AC, 'r6', 'lk_r38 loop'), (0xC032C628, 'r6', 'lk_reg loop'), (0xC0324FDC, 'r6', 'lk_r28 loop'),
    (0xC0325044, 'r6', 'lk_r14 loop'), (0xC03240E8, 'r6', 'lk_r10 loop'),
]
# the cave holds ~3.4 KB: the loops that ran at record start (cmpprobe v1, 2026-11-04) and the hooked lookups'
ACTIVE = {0xC008AA9C, 0xC021DC1C, 0xC0221FE4, 0xC02DB928, 0xC032C6F4, 0xC032CF34, 0xC033E1A4, 0xC034542C,
          0xC050AEE0, 0xC0324C84, 0xC0324CE8, 0xC0324D4C, 0xC03250AC, 0xC032C628, 0xC0324FDC, 0xC0325044,
          0xC03240E8}
COUNTS = os.environ.get('CMPPROBE_COUNTS') == '1'   # all sites, counts only (hits, total): fits with sdtrig
if not COUNTS:
    SITES = [x for x in SITES if x[0] in ACTIVE]
NW, REC = (15, 8) if COUNTS else (22, 48)                 # stub words; record: hits, total, ring index, the last 8 ids searched


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


def stub_counts(site, reg, orig, rec):
    """the compact stub: hits (wanted id == VMID) at rec+0, total at rec+4"""
    r = REGS[reg]
    get = {2: 0xE59D3000, 3: 0xE59D3004}.get(r, 0xE1A03000 | r)   # r3 = the wanted id (r2/r3 from the stack)
    w = [0xE92D000C,            # 0  push {r2, r3}
         0xE59F202C,            # 1  ldr r2, [pc, #0x2c] -> rec (word 14)
         get,                   # 2
         0xE3530000 | VMID,     # 3  cmp r3, #VMID
         0x05923000,            # 4  ldreq r3, [r2]
         0x02833001,            # 5  addeq r3, r3, #1
         0x05823000,            # 6  streq r3, [r2]       hits
         0xE5923004,            # 7  ldr r3, [r2, #4]
         0xE2833001,            # 8  add r3, r3, #1
         0xE5823004,            # 9  str r3, [r2, #4]     total
         0xE8BD000C,            # 10 pop {r2, r3}
         orig,                  # 11 the replaced compare
         0xE51FF004,            # 12 ldr pc, [pc, #-4]
         site + 4,              # 13
         rec]                   # 14
    assert len(w) == 15
    return w


def stub(site, reg, orig, rec):
    if COUNTS:
        return stub_counts(site, reg, orig, rec)
    r = REGS[reg]
    get = {1: 0xE59D3000, 2: 0xE59D3004, 3: 0xE59D3008}.get(r, 0xE1A03000 | r)  # r3 = the wanted id
    w = [0xE92D000E,            # 0  push {r1, r2, r3}
         0xE59F2048,            # 1  ldr r2, [pc, #0x48] -> rec (word 21)
         get,                   # 2  r3 = the wanted id (r1..r3 from the stack)
         0xE5921008,            # 3  ldr r1, [r2, #8]      ring index
         0xE2011007,            # 4  and r1, r1, #7
         0xE0821101,            # 5  add r1, r2, r1, lsl #2
         0xE581300C,            # 6  str r3, [r1, #12]     ring[i]
         0xE5921008,            # 7  ldr r1, [r2, #8]
         0xE2811001,            # 8  add r1, r1, #1
         0xE5821008,            # 9  str r1, [r2, #8]
         0xE5921004,            # 10 ldr r1, [r2, #4]
         0xE2811001,            # 11 add r1, r1, #1
         0xE5821004,            # 12 str r1, [r2, #4]      total
         0xE3530000 | VMID,     # 13 cmp r3, #VMID
         0x05921000,            # 14 ldreq r1, [r2]
         0x02811001,            # 15 addeq r1, r1, #1
         0x05821000,            # 16 streq r1, [r2]        hits
         0xE8BD000E,            # 17 pop {r1, r2, r3}
         orig,                  # 18 the replaced compare (sets the flags)
         0xE51FF004,            # 19 ldr pc, [pc, #-4]
         site + 4,              # 20
         rec]                   # 21
    assert len(w) == NW
    return w


def install():
    orig = [rd(s)[0] for s, _, _ in SITES]
    for (s, reg, what), w in zip(SITES, orig):
        if w & 0x0FF00000 not in (0x01500000, 0x03500000) or w >> 28 != 0xE:
            raise SystemExit(f'{s:#x} ({what}) holds {w:#x}, not a cmp (already hooked?)')
    n = len(SITES)
    base = cave.claim('cmpprobe', n * (NW * 4 + REC))
    recs = base + n * NW * 4
    for k, ((s, reg, _), w0) in enumerate(zip(SITES, orig)):
        st, rec = base + k * NW * 4, recs + k * REC
        for i, x in enumerate(stub(s, reg, w0, rec)):
            setw(st + 4 * i, x)
        for i in range(REC // 4):
            setw(rec + 4 * i, 0)
    flush()
    for k, (s, _, _) in enumerate(SITES):
        st = base + k * NW * 4
        setw(s, 0xEA000000 | (((st - (s + 8)) >> 2) & 0xFFFFFF))
    flush()
    json.dump({'base': base, 'recs': recs, 'orig': orig}, open(STATE, 'w'))
    print(f'installed {n} compare stubs at {base:#x}, records {recs:#x}')


def snapshot():
    st = json.load(open(STATE))
    n = REC // 4
    r = P.mem_get(st['recs'], len(SITES) * n)
    if not r or None in r:
        return None
    out = []
    for k, (s, _, what) in enumerate(SITES):
        w = r[n * k: n * k + n]
        if COUNTS:
            ring = []
        else:
            i = w[2]
            ring = [w[3 + ((i - 1 - j) & 7)] for j in range(min(i, 8))]   # newest first
        out.append((s, what, w[0], w[1], ring))
    return out


def show(snap):
    for s, what, hits, total, ring in snap:
        if total or hits:
            print(f'  {s:#010x} {what:13s} total {total:8d}  last ids {ring}'
                  + (f'   SEARCHED FOR {VMID}: {hits}' if hits else ''))


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
        key = [(a, h, tot > 0, tuple(sorted(set(rg)))) for a, _, h, tot, rg in s]
        if key != prev:
            print(t, flush=True)
            show(s)
            sys.stdout.flush()
            prev = key


def remove():
    st = json.load(open(STATE))
    for (s, _, _), w in zip(SITES, st['orig']):
        setw(s, w)
    flush()
    print('restored')


if __name__ == '__main__':
    {'install': install, 'read': read, 'poll': poll, 'remove': remove}[sys.argv[1]]()
