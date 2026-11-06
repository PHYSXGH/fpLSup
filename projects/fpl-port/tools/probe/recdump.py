"""Dump camera RAM the moment a recording starts (read-only).

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 recdump.py OUTDIR [now|quick|early]

Waits for the movie-recording flag (byte +0x157 of the object FUN_c035b4e8 returns, 0xC347ED4C on the
fp L; the fp's FUN_c035b2d0 / 0xC347DF38, CAMERA_STATE_SOURCES.md) to turn 1, then dumps RANGES through
MEM1 in 8 MiB pieces
(the worker's limit is 16 MiB - 1 KiB). `now`: dump at once. Made for diffing the recording set-up
of two formats (ISSUES.md 2: UHDC's preview vs stock UHD's crop step).
`quick`: only the recording set-up block (BLOCK), read 0.1 s and 0.3 s after the flag sets -- a take
the card stops after ~1 s (UHDC at 59.94 on SD) is over before the full dump reaches it.
"""
import os, sys, time
import putfile as P
from recdiag import rd, flush

RANGES = [(0xC0B00000, 0xC0E00000), (0xC2D00000, 0xC8000000)]
CH = 8 << 20
BLOCK = (0xC31DD800, 0xC31DDC00)
EARLY = [(0xC31C0000, 0xC3300000), (0xC3700000, 0xC3800000), (0xC3020000, 0xC3030000)]   # `early`: the set-up globals, ~2.3 MiB        # the recording set-up (ISSUES.md 2: +0x15C.. offsets, +0x1BC read)
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
    quick = len(sys.argv) > 2 and sys.argv[2] == 'quick'
    early = len(sys.argv) > 2 and sys.argv[2] == 'early'
    if early:
        for slot, (a, b) in enumerate(EARLY):
            P.mem_window(slot, a - 0x80000000, b - a, 1)
    flag = lambda: (rd(REC_FLAG & ~3)[0] >> (8 * (REC_FLAG & 3))) & 0xFF
    if flag():
        raise SystemExit('the recording flag is already set: stop recording first')
    print('waiting for a recording ...', flush=True)
    while not flag():
        time.sleep(0.05)
    print('record started', flush=True)
    if early:
        os.makedirs(out, exist_ok=True)
        time.sleep(0.15)
        t0 = time.time()
        flush()
        for a, b in EARLY:
            open(os.path.join(out, f'ram_{a:08x}.bin'), 'wb').write(P.mem_read(a - 0x80000000, b - a))
        print(f'early dump in {time.time() - t0:.2f}s', flush=True)
        return
    if quick:
        os.makedirs(out, exist_ok=True)
        t0 = time.time()
        for at in (0.1, 0.3):
            time.sleep(max(0.0, t0 + at - time.time()))
            a, b = BLOCK
            words = rd(a, (b - a) // 4)
            open(os.path.join(out, f'block_{a:08x}_{int(at * 1000)}ms.bin'), 'wb').write(
                b''.join(w.to_bytes(4, 'little') for w in words))
            print(f'block at +{time.time() - t0:.2f}s', flush=True)
        return
    time.sleep(0.3)                       # let the set-up finish
    dump(out)


if __name__ == '__main__':
    main()
