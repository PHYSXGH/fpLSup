"""fnprobe whose records the camera writes to the SD card itself (RAM only).  install | read | remove

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell FNPROBE_FNS=C032C930,... python3 sdprobe.py install
    python3 sdprobe.py decode PROBE1.BIN [FNS]      (on the host, from the card)

The call logger (fnprobe.py, FNPROBE_FNS) plus sd/sdtrig.S on the configurator's dispatcher (0xC043C0B8,
called ~20 times a second from record start, never in live view): on its 5th, 15th and 40th call it
writes the whole logger area (stubs + records) to \\PROBE1.BIN, \\PROBE2.BIN, \\PROBE3.BIN on the card with
the firmware's file calls -- so what happened after the record press survives the camera dying.
"""
import json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'sdprobe.json')
TRIG_AT = 0xC043C0B8
STUB, REC = 19 * 4, 256


def decode(path, fns):
    d = open(path, 'rb').read()
    n = len(fns)
    for k, f in enumerate(fns):
        rec = d[n * STUB + k * REC: n * STUB + (k + 1) * REC]
        r = struct.unpack('<64I', rec)
        cnt = r[0]
        print(f'{f:#010x} calls {cnt}')
        for j in range(min(cnt, 8)):
            s = (cnt - j) & 7
            w = r[8 * s + 1: 8 * s + 6]
            print(f'    r0 {w[0]:#010x}  r1 {w[1]:#010x} ({w[1]})  r2 {w[3]:#010x}  r3 {w[4]:#010x}  lr {w[2]:#010x}')


def chain(path, image):
    """return addresses in a stack dump: words in the code whose previous instruction is a call"""
    d = open(path, 'rb').read()
    img = open(image, 'rb').read()
    w = lambda a: struct.unpack_from('<I', img, a - 0xC0000000)[0]          # noqa: E731
    def fn_of(a):
        for _ in range(4000):
            if w(a) & 0xFFFF0000 == 0xE92D0000:
                return a
            a -= 4
        return None
    for off in range(0, len(d) - 3, 4):
        v = struct.unpack_from('<I', d, off)[0]
        if 0xC0000004 <= v < 0xC0B00000 and not v & 3:
            p = w(v - 4)
            if p & 0x0F000000 == 0x0B000000 or p & 0x0FFFFFF0 == 0x012FFF30:   # bl / blx reg
                print(f'  sp+{off:#05x}  {v:#010x}  in fn {fn_of(v - 4) or 0:#010x}')


def main():
    if sys.argv[1] == 'chain':
        return chain(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else
                     os.path.join(HERE, '..', '..', '..', '..', 'out_fpl', 'MAIN_c0000000.bin'))
    if sys.argv[1] == 'cmpdecode':                   # cmpdecode FILE: the compare counters (CMPPROBE_COUNTS=1)
        os.environ['CMPPROBE_COUNTS'] = '1'
        src = open(os.path.join(HERE, 'cmpprobe.py')).read().split('\ndef setw')[0]
        g = {'__file__': os.path.join(HERE, 'cmpprobe.py'), '__name__': 'x'}
        exec(src.replace('import putfile as P, cave', ''), g)
        d = open(sys.argv[2], 'rb').read()
        for k, (site, reg, what) in enumerate(g['SITES']):
            hits, total = struct.unpack_from('<2I', d, 8 * k)
            if hits or total:
                print(f'  {site:#010x} {what:13s} total {total:8d}' + (f'   SEARCHED FOR {g["VMID"]}: {hits}' if hits else ''))
        return
    if sys.argv[1] == 'decode':
        fns = [int(x, 16) for x in (sys.argv[3] if len(sys.argv) > 3 else os.environ['FNPROBE_FNS']).split(',')]
        return decode(sys.argv[2], fns)
    import putfile as P, cave
    sys.path.insert(0, HERE)
    import fnprobe as F
    os.environ.setdefault('FPSUP_CAMERA', 'fpl')
    if sys.argv[1] in ('install', 'stack', 'cmp'):
        if sys.argv[1] == 'cmp':                      # cmpprobe (CMPPROBE_COUNTS=1): the compare counters
            import cmpprobe as C
            C.install()
            cst = json.load(open(C.STATE))
            area, size = cst['recs'] - C.UNCACHED_DELTA, len(C.SITES) * C.REC   # the uncached alias
        elif sys.argv[1] == 'install':
            F.install()
            fst = json.load(open(F.STATE))
            area, size = fst['base'], len(F.FNS) * (F.STUB + F.REC)
        else:
            area, size = 0, 0x800                   # the stack of whoever calls the hooked function
        # the trigger: assembled as-is (fp L addresses, nothing to map)
        env = os.environ.get('FPSUP_CAMERA')
        os.environ['FPSUP_CAMERA'] = 'fp'
        from armasm import assemble, symbols
        src = os.path.join(HERE, 'sd', 'sdtrig.S')
        code, sym = assemble(src), symbols(src)
        os.environ['FPSUP_CAMERA'] = env
        w0 = F.rd(TRIG_AT)[0]
        if w0 & 0xFFFF0000 != 0xE92D0000:
            raise SystemExit(f'{TRIG_AT:#x} starts {w0:#x}, not a push')
        base = cave.claim('sdtrig', len(code))
        for i in range(0, len(code), 4):
            F.setw(base + i, struct.unpack_from('<I', code, i)[0])
        F.setw(base + sym['orig'], w0)
        F.setw(base + sym['back_p'], TRIG_AT + 4)
        F.setw(base + sym['data_p'], area)
        F.setw(base + sym['len_p'], size)
        F.setw(base + sym['cnt_p'], base + sym['cnt'])
        F.flush()
        F.setw(TRIG_AT, 0xEA000000 | (((base + sym['trig'] - (TRIG_AT + 8)) >> 2) & 0xFFFFFF))
        F.flush()
        json.dump({'base': base, 'sym': sym, 'w0': w0, 'area': area, 'size': size, 'fns': F.FNS}, open(STATE, 'w'))
        print(f'trigger at {base:#x} on {TRIG_AT:#x}; dumps {size} bytes from {area:#x} on calls 5, 15, 40')
    elif sys.argv[1] == 'set':                     # set TH1,TH2,TH3 BASE_N: also resets the count
        st = json.load(open(STATE))
        th = [int(x) for x in sys.argv[2].split(',')]
        for k, t in zip(('th1', 'th2', 'th3'), th):
            F.setw(st['base'] + st['sym'][k], t)
        F.setw(st['base'] + st['sym']['base_n'], int(sys.argv[3]))
        F.setw(st['base'] + st['sym']['cnt'], 0)
        F.flush()
        print('thresholds', th, 'files from', int(sys.argv[3]) + 1)
    elif sys.argv[1] == 'read':
        st = json.load(open(STATE))
        cnt, wrote = F.rd(st['base'] + st['sym']['cnt'], 2)
        print(f'dispatcher calls {cnt}, files written {wrote}')
    elif sys.argv[1] == 'remove':
        st = json.load(open(STATE))
        F.setw(TRIG_AT, st['w0'])
        F.flush()
        if st['area']:
            F.remove()


main()
