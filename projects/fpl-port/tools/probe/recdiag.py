"""fp L res-custom recording crash probe (RAM only; a power-off removes it).

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 recdiag.py install|state|poll|remove

install: hook the firmware's assertion routine 0xC0011100 (first word push {r4, r5, lr}): a stub in a
         cave block counts calls and keeps r0 (file string), r1 (line), lr of the first and the last call.
state:   the res-custom core's live state (found from the pick8 site's veneer) and the entry it last picked.
poll:    state + the assertion capture, repeatedly, until the shell stops answering.
"""
import json, struct, sys, time
import putfile as P, cave

F_DCACHE, F_ICACHE = 0xC000E91C, 0xC000EABC
ASSERT = 0xC0011100
ASSERT_W0 = 0xE92D4030                     # push {r4, r5, lr}
ASSERT_FLAG = 0xC3033465                   # the routine's "already asserting" byte
PICK8 = 0xC043BAB0
PICK8_SHIM_OFF, S_FROM_SHIMS = 504, 0x1400
S_OFF = dict(FLAG=0x8, ASPECT=0xC, CUR=0x10, BITLATCH=0x1C, PICKOK=0x20, FPSLATCH=0x24, PBROW=0x28,
             LAST_ENT=0x2C, NROWS=0x30, NENT=0x38, NVM=0x40, HITS=0x50, SEL=0x220, VRATE=0x6E0)
STATE = __file__.replace('recdiag.py', 'recdiag.json')


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


def cstr(a, n=48):
    if not 0xC0000000 <= a < 0xC8000000:
        return f'<{a:#x}>'
    b = struct.pack(f'<{n // 4}I', *rd(a & ~3, n // 4))[a & 3:]
    return b.split(b'\0')[0].decode('latin1')


def install():
    w0 = rd(ASSERT)[0]
    if w0 != ASSERT_W0:
        raise SystemExit(f'{ASSERT:#x} starts {w0:#x}, not push {{r4, r5, lr}} (already hooked?)')
    base = cave.claim('recdiag', 17 * 4 + 32)
    cap = base + 17 * 4
    w = [0xE92D000C,            # push {r2, r3}
         0xE59F2034,            # ldr r2, [pc, #0x34]  -> cap (word 16)
         0xE5923000,            # ldr r3, [r2]
         0xE3530000,            # cmp r3, #0
         0x05820010,            # streq r0, [r2, #16]   first: file
         0x05821014,            # streq r1, [r2, #20]   first: line
         0x0582E018,            # streq lr, [r2, #24]   first: caller
         0xE2833001,            # add r3, r3, #1
         0xE5823000,            # str r3, [r2]          count
         0xE5820004,            # str r0, [r2, #4]      last: file
         0xE5821008,            # str r1, [r2, #8]      last: line
         0xE582E00C,            # str lr, [r2, #12]     last: caller
         0xE8BD000C,            # pop {r2, r3}
         ASSERT_W0,             # the replaced instruction
         0xE51FF004,            # ldr pc, [pc, #-4]
         ASSERT + 4,
         cap]
    assert len(w) == 17
    for i, x in enumerate(w):
        setw(base + 4 * i, x)
    for i in range(8):
        setw(cap + 4 * i, 0)
    flush()
    setw(ASSERT, 0xEA000000 | (((base - (ASSERT + 8)) >> 2) & 0xFFFFFF))
    flush()
    json.dump({'base': base, 'cap': cap}, open(STATE, 'w'))
    print(f'assertion hook installed: stub {base:#x}, capture {cap:#x}')


def remove():
    setw(ASSERT, ASSERT_W0)
    flush()
    print('restored', hex(rd(ASSERT)[0]))


def find_s():
    w = rd(PICK8)[0]
    if w & 0x0F000000 != 0x0B000000:
        raise SystemExit(f'pick8 site holds {w:#x}: res-custom did not hook it this boot')
    off = w & 0xFFFFFF
    off -= (1 << 24) if off & 0x800000 else 0
    ven = PICK8 + 8 + 4 * off
    v = rd(ven, 2)
    if v[0] != 0xE51FF004:
        raise SystemExit(f'veneer {ven:#x} holds {v[0]:#x}, not ldr pc, [pc, #-4]')
    return v[1] - PICK8_SHIM_OFF + S_FROM_SHIMS, ven


def state(quiet=False):
    S, ven = find_s()
    vals = {k: rd(S + o)[0] for k, o in S_OFF.items()}
    out = {'S': hex(S), 'veneer': hex(ven), **vals}
    if vals['LAST_ENT']:
        e = S + vals['LAST_ENT']
        ent = rd(e, 16)
        out['entry'] = {'type': ent[0], 'pid': ent[1], 'mode': ent[2], 'keyptr': hex(ent[3]),
                        'key': cstr(ent[3], 16), 'w0': hex(ent[9]), 'w1': hex(ent[10]),
                        'engfps': hex(ent[11]), 'nominal': ent[12]}
    vm = S + rd(S + 0x44)[0]
    v = rd(vm, 0x40 // 4)
    out['vm'] = {'id': v[0], 'donor': v[1], 'filled': v[2], 'regfilled': v[3], 'zfilled': v[4],
                 'ptr': [hex(x) for x in v[8:15]], 'r10ok': v[0x44 // 4] if False else None}
    out['assert_flag'] = rd(ASSERT_FLAG & ~3)[0] >> (8 * (ASSERT_FLAG & 3)) & 0xFF
    try:
        cap = json.load(open(STATE))['cap']
        c = rd(cap, 7)
        out['asserts'] = c[0]
        if c[0]:
            out['first'] = f'{cstr(c[4])}:{c[5]} from {c[6]:#x}'
            out['last'] = f'{cstr(c[1])}:{c[2]} from {c[3]:#x}'
    except FileNotFoundError:
        pass
    print(json.dumps(out), flush=True)
    return out


def poll():
    while True:
        t = time.strftime('%H:%M:%S')
        try:
            print(t, end=' ', flush=True)
            state()
        except SystemExit as e:
            print(t, 'no answer:', e, flush=True)
            return
        except Exception as e:                      # noqa: BLE001
            print(t, 'error:', repr(e), flush=True)
        time.sleep(0.5)


def entries():
    S, _ = find_s()
    base, n = S + rd(S + 0x3C)[0], rd(S + 0x38)[0]
    out = []
    for i in range(n):
        e = base + 64 * i
        w = rd(e, 16)
        out.append((e, w, cstr(e + 20, 16)))
    return out


def setent():
    """setent PID MODE [KEY]: set the plain (non-virtual-rate) entry with KEY (default *23_98FPS)"""
    pid, mode = int(sys.argv[2], 0), int(sys.argv[3], 0)
    key = sys.argv[4] if len(sys.argv) > 4 else None
    for e, w, k in entries():
        print(f'  entry {e:#x}: type {w[0]} pid {w[1]} mode {w[2]} key {k!r} vrate {w[15]}')
    hit = [(e, w, k) for e, w, k in entries() if w[15] == 0 and (k == key if key else k.endswith('23_98FPS'))]
    if len(hit) != 1:
        raise SystemExit(f'{len(hit)} entries match')
    e, w, k = hit[0]
    setw(e + 4, pid)
    setw(e + 8, mode)
    print(f'set {k!r} at {e:#x}: pid {w[1]} -> {pid}, mode {w[2]} -> {mode}')


if __name__ == '__main__':
    {'install': install, 'state': state, 'poll': poll, 'remove': remove, 'setent': setent}[sys.argv[1]]()
