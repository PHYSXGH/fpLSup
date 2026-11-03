"""Find the sensor mode tables in a firmware image by their shape (no addresses needed).

geometry rows, 0x64 bytes: w0 = mode id (< 256), w1 = readout width, w2 = lines,
  w5 == w1 and w9 == w1, w6 == w2 and w10 == w2, +0x44 binning in 1..8
timing rows, 0x20 bytes, same mode ids in the same order: +4 hmax, +6 tail, +8 vmax
    find_mode_tables.py IMAGE
"""
import sys, struct
from pathlib import Path
B = Path(sys.argv[1]).read_bytes(); BASE = 0xC0000000

def geo_ok(o):
    if o + 0x64 > len(B): return False
    w = struct.unpack_from('<25I', B, o)
    return (w[0] < 256 and 64 <= w[1] <= 12000 and 64 <= w[2] <= 9000 and w[5] == w[1] and w[9] == w[1]
            and w[6] == w[2] and w[10] == w[2] and 1 <= w[17] <= 8)

runs = []
o = 0
while o < len(B) - 0x64:
    if geo_ok(o):
        n = 0
        while geo_ok(o + n * 0x64): n += 1
        if n >= 8: runs.append((o, n))
        o += max(n, 1) * 0x64
    else:
        o += 4
for o, n in runs:
    ids = [struct.unpack_from('<I', B, o + i * 0x64)[0] for i in range(n)]
    print(f'geometry table at {BASE + o:#x}: {n} rows, ids {ids[:12]}...')
    # timing table: 0x20 rows with the same id sequence
    pat = b''.join(struct.pack('<I', ids[i]) + b'\0' * 28 for i in range(1))
    hits = []
    for t in range(0, len(B) - n * 0x20, 4):
        if all(struct.unpack_from('<I', B, t + i * 0x20)[0] == ids[i] for i in range(min(n, 12))):
            hits.append(t)
            if len(hits) > 3: break
    for t in hits:
        print(f'   timing table at {BASE + t:#x}')
