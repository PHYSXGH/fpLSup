"""Log every CHANGE of the profile the camera builds (RAM only).  install | read | poll | remove

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 pidring.py CMD

FUN_c04398f0 (r1 = the profile id) builds a profile's canvas; live view calls it continuously with
the same id (p51 video, p1 photo).  A stub at its first instruction keeps the last id and, when an
id differs from it, appends {id, lr, S.FLAG, S.CUR} to a 64-entry ring -- so a short switch (the
autofocus half-press, the way back from a menu) survives the thousands of calls that follow.
S (the res-custom core's state) is found as recdiag.py finds it.
"""
import json, os, sys
import putfile as P, cave
from recdiag import find_s, rd, setw, flush

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'pidring.json')
FN = 0xC04398F0
FN_W0 = 0xE92D4070                       # push {r4, r5, r6, lr}
NREC = 64
S_FLAG, S_CUR = 0x8, 0x10


def stub_words(base, rec, s):
    """the stub at `base`; records at `rec`: [0] last id, [1] changes, then NREC x {id, lr, flag, cur}"""
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
    src = f"""
        push {{r2, r3, r12}}
        ldr r12, lit_rec
        ldr r3, [r12]
        cmp r3, r1
        beq done
        str r1, [r12]
        ldr r3, [r12, #4]
        add r3, r3, #1
        str r3, [r12, #4]
        and r3, r3, #{NREC - 1}
        add r3, r12, r3, lsl #4
        str r1, [r3, #8]
        str lr, [r3, #12]
        ldr r12, lit_s
        ldr r2, [r12, #{S_FLAG}]
        str r2, [r3, #16]
        ldr r2, [r12, #{S_CUR}]
        str r2, [r3, #20]
    done:
        pop {{r2, r3, r12}}
        push {{r4, r5, r6, lr}}
        ldr pc, lit_back
    lit_rec: .word {rec}
    lit_s: .word {s}
    lit_back: .word {FN + 4}
    """
    enc, _ = Ks(KS_ARCH_ARM, KS_MODE_ARM).asm(src, base)
    b = bytes(enc)
    return [int.from_bytes(b[i:i + 4], 'little') for i in range(0, len(b), 4)]


def install():
    w0 = rd(FN)[0]
    if w0 != FN_W0:
        raise SystemExit(f'{FN:#x} starts {w0:#x}, not push {{r4, r5, r6, lr}} (another probe?)')
    S, _ = find_s()
    probe = stub_words(0, 0, 0)
    base = cave.claim('pidring', 4 * len(probe) + 8 + 16 * NREC)
    rec = base + 4 * len(probe)
    words = stub_words(base, rec, S)
    for i in range((8 + 16 * NREC) // 4):
        setw(rec + 4 * i, 0)
    setw(rec, 0xFFFFFFFF)
    for i, x in enumerate(words):
        setw(base + 4 * i, x)
    flush()
    setw(FN, 0xEA000000 | (((base - (FN + 8)) >> 2) & 0xFFFFFF))
    flush()
    json.dump({'base': base, 'rec': rec, 'S': S}, open(STATE, 'w'))
    print(f'installed at {base:#x}, ring {rec:#x}, S {S:#x}')


def read(since=0):
    st = json.load(open(STATE))
    rec = st['rec']
    r = rd(rec, 2 + 4 * NREC)
    n = r[1]
    print(f'last id {r[0]}, {n} changes')
    for k in range(max(since, n - NREC), n):
        j = 2 + 4 * ((k + 1) & (NREC - 1))
        pid, lr, flag, cur = r[j:j + 4]
        print(f'  #{k + 1:4d}  p{pid:<5d} lr {lr:#010x}  FLAG {flag}  CUR {cur}')
    return n


def poll():
    import time
    n = 0
    while True:
        n = read(n) if n else read()
        time.sleep(1)


def remove():
    setw(FN, FN_W0)
    flush()
    print('restored')


if __name__ == '__main__':
    {'install': install, 'read': read, 'poll': poll, 'remove': remove}[sys.argv[1]]()
