"""RAM-only CPU fault catcher for the fp L (USB shell).  readcp | vectors | install | read | remove

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 vecprobe.py CMD
"""
import json, os, struct, sys
import putfile as P, cave

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'vecprobe.json')
F_DCACHE, F_ICACHE = 0xC000E91C, 0xC000EABC
VEC = {'und': 0x04, 'pabt': 0x0C, 'dabt': 0x10}


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


def asm(name):
    os.environ.setdefault('FPSUP_CAMERA', 'fpl')
    from armasm import assemble, symbols
    src = os.path.join(HERE, 'vec', name)
    return assemble(src), {k: v for k, v in symbols(src).items() if not k.startswith('$')}


def put(base, code):
    for i in range(0, len(code), 4):
        setw(base + i, struct.unpack_from('<I', code, i)[0])


def load():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}


def save(d):
    json.dump(d, open(STATE, 'w'))


def readcp():
    code, sym = asm('readcp.S')
    base = cave.claim('vecread', len(code) + 16)
    scratch = base + len(code)
    put(base, code)
    setw(base + sym['scratch'], scratch)
    for i in range(3):
        setw(scratch + 4 * i, 0xDEADBEEF)
    flush()
    call(base)
    vbar, sctlr, mpidr = rd(scratch, 3)
    hi = bool(sctlr & (1 << 13))
    d = load()
    d.update(vbar=vbar, sctlr=sctlr, mpidr=mpidr, vectors=0xFFFF0000 if hi else vbar)
    save(d)
    print(f'VBAR {vbar:#010x}  SCTLR {sctlr:#010x} (V={int(hi)})  MPIDR {mpidr:#010x}  -> vectors at {d["vectors"]:#010x}')


def where(vbase, off):
    """(how, address) the handler for vector `off` is reached: a literal pc load or a branch"""
    w = rd(vbase + off)[0]
    if w & 0xFFFFF000 == 0xE59FF000:                       # ldr pc, [pc, #imm]
        return 'lit', vbase + off + 8 + (w & 0xFFF), w
    if w & 0xFF000000 == 0xEA000000:                       # b
        o = w & 0xFFFFFF
        o -= (1 << 24) if o & 0x800000 else 0
        return 'b', vbase + off + 8 + 4 * o, w
    return '?', 0, w


def vectors():
    d = load()
    vb = d['vectors']
    print('vector words', [hex(x) for x in rd(vb, 16)])
    for k, off in VEC.items():
        how, a, w = where(vb, off)
        extra = f' -> handler {rd(a)[0]:#010x}' if how == 'lit' else ''
        print(f'  {k:5s} +{off:#04x}: {w:#010x} {how} {a:#010x}{extra}')


def install():
    d = load()
    vb = d['vectors']
    code, sym = asm('catcher.S')
    base = cave.claim('catcher', len(code) + 128)
    rec = base + len(code)
    put(base, code)
    setw(base + sym['recp'], rec)
    for i in range(32):
        setw(rec + 4 * i, 0)
    flush()
    orig = {}
    for k, off in VEC.items():
        how, a, w = where(vb, off)
        target = base + sym['entry_' + k]
        if how == 'lit':
            orig[k] = ('lit', a, rd(a)[0])
            setw(a, target)
        elif how == 'b':
            orig[k] = ('b', vb + off, w)
            setw(vb + off, 0xEA000000 | (((target - (vb + off + 8)) >> 2) & 0xFFFFFF))
        else:
            raise SystemExit(f'{k}: vector word {w:#x} is neither ldr pc nor b')
    flush()
    d.update(base=base, rec=rec, orig=orig)
    save(d)
    print(f'catcher at {base:#x}, record {rec:#x}; vectors redirected: {orig}')


def read():
    d = load()
    r = rd(d['rec'], 24)
    kind = {1: 'data abort', 2: 'prefetch abort', 3: 'undefined'}.get(r[1], r[1])
    print(f'faults {r[0]}  first: {kind}  lr {r[2]:#010x}  spsr {r[3]:#010x}  DFAR {r[4]:#010x}  DFSR {r[5]:#x}  '
          f'IFAR {r[6]:#010x}  IFSR {r[7]:#x}  MPIDR {r[23]:#x}')
    print('  r0-r12', [hex(x) for x in r[8:21]], ' sp', hex(r[21]), ' lr', hex(r[22]))


def remove():
    d = load()
    for k, (how, a, w) in d['orig'].items():
        setw(a, w)
    flush()
    print('vectors restored')


{'readcp': readcp, 'vectors': vectors, 'install': install, 'read': read, 'remove': remove}[sys.argv[1]]()
