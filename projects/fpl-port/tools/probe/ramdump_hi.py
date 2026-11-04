"""Dump the fp L's upper RAM (physical 0x80000000.., uncached only) through MEM1 (read-only).

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 ramdump_hi.py OUTDIR [START END]

8 MiB pieces: the worker's transfer limit is 16 MiB - 1 KiB, and a request over it wedged the shell
(2026-11-04).  A read window is opened over the range first (all windows are closed after boot).
"""
import os, sys, time
import putfile as P

out = sys.argv[1]
start = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x80000000
end = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0xC0000000
CH = 8 << 20
os.makedirs(out, exist_ok=True)
caps = P.mem_caps(refresh=True)
assert caps and caps['xfer'] >= CH, caps
P.mem_window(0, start, end - start, 1)
t0 = time.time()
for a in range(start, end, CH):
    p = os.path.join(out, f'ram_{a:08x}.bin')
    if os.path.exists(p) and os.path.getsize(p) == CH:
        continue
    open(p, 'wb').write(P.mem_read(a, CH))
print(f'done in {time.time() - t0:.0f}s')
