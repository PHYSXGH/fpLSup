"""Overwrite UHDC's preview-window offsets while a take records (RAM only; ISSUES.md 2).

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 winpoke.py [DX DY]

The recording set-up's canvas copy at 0xC31DD8C8 holds +0x94 / +0x98 = read size - the window the
firmware took from the still-size table (UHDC: 6288 - 3840, 2174 - 2552). This waits for the
movie-recording flag, then writes DX / DY (default 2448 / 14: a 3840x2160 window) every 20 ms until
the flag clears, and logs what it found and whether the firmware wrote them back.
"""
import sys, time
import putfile as P
from recdiag import rd

REC_FLAG = 0xC347ED4C + 0x157
OFFS = 0xC31DD95C


def flag():
    return (rd(REC_FLAG & ~3)[0] >> (8 * (REC_FLAG & 3))) & 0xFF


def s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


def main():
    dx, dy = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (2448, 14)
    if flag():
        raise SystemExit('the recording flag is already set: stop recording first')
    print(f'waiting for a recording (will write {dx} / {dy}) ...', flush=True)
    while not flag():
        time.sleep(0.01)
    t0 = time.time()
    before = [s32(v) for v in rd(OFFS, 2)]
    print(f'record started; found {before}', flush=True)
    n, rewritten = 0, 0
    while flag():
        cur = [s32(v) for v in rd(OFFS, 2)]
        if n and cur != [dx, dy]:
            rewritten += 1
            print(f'  +{time.time() - t0:.2f}s the firmware wrote {cur} back', flush=True)
        P.mem_set(OFFS, dx & 0xFFFFFFFF)
        P.mem_set(OFFS + 4, dy & 0xFFFFFFFF)
        n += 1
        time.sleep(0.02)
    print(f'record stopped after {time.time() - t0:.2f}s; {n} writes, {rewritten} times rewritten', flush=True)


if __name__ == '__main__':
    main()
