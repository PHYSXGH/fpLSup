"""Dump camera RAM the moment a recording starts (read-only).

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 recdump.py OUTDIR [now]

Waits for the movie-recording flag (byte +0x157 of the object FUN_c035b4e8 returns, 0xC347ED4C on the
fp L; the fp's FUN_c035b2d0 / 0xC347DF38, CAMERA_STATE_SOURCES.md) to turn 1, then dumps RANGES through
MEM1 in 8 MiB pieces
(the worker's limit is 16 MiB - 1 KiB). `now`: dump at once. Made for diffing the recording set-up
of two formats (ISSUES.md 2: UHDC's preview vs stock UHD's crop step).
"""
import os, sys, time
import putfile as P
from recdiag import rd, flush

RANGES = [(0xC0B00000, 0xC0E00000), (0xC2D00000, 0xC8000000)]
CH = 8 << 20
REC_FLAG = 0xC347ED4C + 0x157          # byte: 1 while a movie records


def dump(out):
    """the cached addresses (0xC...) through their uncached alias (-0x80000000): the shell refuses
    read windows on the cached range (code 2) and MEM1 needs one; the D-cache is cleaned first"""
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    flush()
    for slot, (a, b) in enumerate(RANGES):
        P.mem_window(slot, a - 0x80000000, b - a, 1)
    for a, b in RANGES:
        for p in range(a, b, CH):
            n = min(CH, b - p)
            open(os.path.join(out, f'ram_{p:08x}.bin'), 'wb').write(P.mem_read(p - 0x80000000, n))
    print(f'dumped {sum(b - a for a, b in RANGES) >> 20} MiB in {time.time() - t0:.1f}s', flush=True)


def main():
    out = sys.argv[1]
    caps = P.mem_caps(refresh=True)
    assert caps and caps['xfer'] >= CH, caps
    if len(sys.argv) > 2 and sys.argv[2] == 'now':
        dump(out)
        return
    flag = lambda: (rd(REC_FLAG & ~3)[0] >> (8 * (REC_FLAG & 3))) & 0xFF
    if flag():
        raise SystemExit('the recording flag is already set: stop recording first')
    print('waiting for a recording ...', flush=True)
    while not flag():
        time.sleep(0.05)
    print('record started', flush=True)
    time.sleep(0.3)                       # let the set-up finish
    dump(out)


if __name__ == '__main__':
    main()
