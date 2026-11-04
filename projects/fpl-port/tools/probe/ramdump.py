"""Dump camera RAM to files for offline searching (read-only).

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 ramdump.py OUTDIR [START END]

Uses MEM1 (MEMR) when the shell's worker offers it, else word reads.  Writes OUTDIR/ram_<start>.bin in
1 MiB pieces, so an interrupted dump keeps what it got.
"""
import os, struct, sys, time
import putfile as P

out = sys.argv[1]
start = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0xC2E00000
end = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0xC4000000
os.makedirs(out, exist_ok=True)
caps = None
try:
    caps = P.mem_caps(refresh=True)
except Exception as e:                                       # noqa: BLE001
    print('MEM1 unavailable:', e)
print('MEM1' if caps else 'word reads', flush=True)
CH = 1 << 20
t0 = time.time()
for a in range(start, end, CH):
    path = os.path.join(out, f'ram_{a:08x}.bin')
    if os.path.exists(path) and os.path.getsize(path) == CH:
        continue
    if caps:
        data = P.mem_read(a, CH)
    else:
        buf = bytearray()
        for b in range(a, a + CH, 1024):
            for _ in range(5):
                r = P.mem_get(b, 256)
                if r and None not in r:
                    break
            else:
                raise SystemExit(f'read {b:#x} failed')
            buf += struct.pack('<256I', *r)
        data = bytes(buf)
    open(path, 'wb').write(data)
    print(f'{a:#x} done, {time.time() - t0:.0f}s', flush=True)
