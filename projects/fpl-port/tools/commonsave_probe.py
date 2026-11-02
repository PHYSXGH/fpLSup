"""Persistence test for XC_CommonSaveData's free region on the fp L (the Fast Start store).

    commonsave_probe.py check            read the region, classify every word
    commonsave_probe.py arm              write 0xA5000000|offset into +0x28..+0x1FC, read back
    commonsave_probe.py restore          write the region back from the backup (zeros), read back

Run from fpSup/fp_usb_shell with FPSUP_CAMERA=fpl and FPSHD_SOCKET set; one daemon.
Only +0x28..+0x200 is ever written: the fp's measured free run (research/firmware/
notes/PERSISTENT_STORE_COMMONSAVE.md), read zero on the fp L 2026-11-02.
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'fpSup' / 'fp_usb_shell'))
import putfile as P                                           # noqa: E402

BASE = 0xC30751FC                     # fp L XC_CommonSaveData (fp 0xC307523C)
LO, HI = 0x28, 0x200
BACKUP = Path(__file__).resolve().parents[1] / 'private' / 'commonsave_fpl_20261102.json'
mark = lambda off: 0xA5000000 | off


def read_region():
    w = P.mem_get(BASE + LO, (HI - LO) // 4)
    if any(x is None for x in w):
        raise SystemExit('a word did not come back; not deciding anything on a partial read')
    return w


def write_checked(values):
    for i, v in enumerate(values):
        a = BASE + LO + 4 * i
        for _ in range(8):
            P.mem_set(a, v)
            got = P.mem_get(a)
            if got and got[0] == v:
                break
        else:
            raise SystemExit(f'{a:#x}: could not write {v:#x}')


def check():
    w = read_region()
    zero = sum(1 for x in w if x == 0)
    ok = sum(1 for i, x in enumerate(w) if x == mark(LO + 4 * i))
    other = [(LO + 4 * i, x) for i, x in enumerate(w) if x and x != mark(LO + 4 * i)]
    print(f'region +{LO:#x}..+{HI:#x}: {len(w)} words: {ok} hold their marker, {zero} zero, {len(other)} other')
    for off, x in other[:20]:
        print(f'   +{off:#05x}: {x:#010x}' + (f'  (marker of +{x & 0xFFFF:#x})' if x >> 24 == 0xA5 else ''))


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'check':
        check()
    elif cmd == 'arm':
        if any(read_region()):
            raise SystemExit('the region is not empty; not writing over something unknown')
        write_checked([mark(LO + 4 * i) for i in range((HI - LO) // 4)])
        check()
    elif cmd == 'restore':
        saved = json.load(open(BACKUP))['words']
        write_checked(saved[LO // 4: HI // 4])
        check()
