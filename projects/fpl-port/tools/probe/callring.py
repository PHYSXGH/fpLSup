"""Log the calls that reach one instruction (RAM only).  install ADDR | read | remove

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 callring.py install 0xC0437D64
    ... read | remove

A stub replaces the word at ADDR (it must not depend on the pc: checked against a short list),
records {r0, r1, r2, lr, [r2+8], [r2+0xC], S.FLAG, S.CUR} of every call in a 64-entry ring, runs the
replaced word and goes on at ADDR + 4.  Made for the resolution-name function 0xC0437D60 (r2 = the
sizes): the core's `name` hook owns its first word, so the probe sits on the second, where every call
the core lets through arrives with the caller's lr.
"""
import json, os, sys
import putfile as P, cave
from recdiag import find_s, rd, setw, flush

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'callring.json')
NREC = 64
SAFE = {0xE24DD008}                      # sub sp, sp, #8 (0xC0437D64)


def stub_words(base, rec, s, addr, w0):
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
    src = f"""
        push {{r3, r12}}
        ldr r12, lit_rec
        ldr r3, [r12]
        add r3, r3, #1
        str r3, [r12]
        and r3, r3, #{NREC - 1}
        add r3, r12, r3, lsl #5
        str r0, [r3, #4]
        str r1, [r3, #8]
        str r2, [r3, #12]
        str lr, [r3, #16]
        ldr r12, [r2, #8]
        str r12, [r3, #20]
        ldr r12, [r2, #12]
        str r12, [r3, #24]
        ldr r12, lit_s
        ldr r12, [r12, #8]
        str r12, [r3, #28]
        ldr r12, lit_s
        ldr r12, [r12, #16]
        str r12, [r3, #32]
        pop {{r3, r12}}
        .word {w0}
        ldr pc, lit_back
    lit_rec: .word {rec}
    lit_s: .word {s}
    lit_back: .word {addr + 4}
    """
    enc, _ = Ks(KS_ARCH_ARM, KS_MODE_ARM).asm(src, base)
    b = bytes(enc)
    return [int.from_bytes(b[i:i + 4], 'little') for i in range(0, len(b), 4)]


def install(addr):
    w0 = rd(addr)[0]
    if w0 not in SAFE:
        raise SystemExit(f'{addr:#x} holds {w0:#x}: not a known pc-independent word')
    S, _ = find_s()
    n = len(stub_words(0, 0, 0, addr, w0))
    base = cave.claim('callring', 4 * n + 4 + 32 * NREC)
    rec = base + 4 * n
    for i in range((4 + 32 * NREC) // 4):
        setw(rec + 4 * i, 0)
    for i, x in enumerate(stub_words(base, rec, S, addr, w0)):
        setw(base + 4 * i, x)
    flush()
    setw(addr, 0xEA000000 | (((base - (addr + 8)) >> 2) & 0xFFFFFF))
    flush()
    json.dump({'addr': addr, 'w0': w0, 'rec': rec}, open(STATE, 'w'))
    print(f'installed at {base:#x}, ring {rec:#x}, S {S:#x}')


def read():
    st = json.load(open(STATE))
    r = []
    for a in range(0, 1 + 8 * NREC, 128):                 # the shell returns at most ~256 words
        r += rd(st['rec'] + 4 * a, min(128, 1 + 8 * NREC - a))
    n = r[0]
    print(f'{n} calls')
    for k in range(max(0, n - NREC), n):
        j = 1 + 8 * ((k + 1) & (NREC - 1))
        r0, r1, r2, lr, w, h, flag, cur = r[j:j + 8]
        print(f'  #{k + 1:5d}  lr {lr:#010x}  {w}x{h}  r0 {r0:#010x} r1 {r1:#x}  FLAG {flag} CUR {cur}')


def remove():
    st = json.load(open(STATE))
    setw(st['addr'], st['w0'])
    flush()
    print('restored')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'install':
        install(int(sys.argv[2], 16))
    else:
        {'read': read, 'remove': remove}[cmd]()
