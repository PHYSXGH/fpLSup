"""Extract the IMX455 mode tables from the fp L image and fit the sensor clock.

Rows (layouts from gcsv_json.S / analyze_imx410_modes.py, accessors identical on both cameras):
  geometry 0x64: +0 id, +4 readout width, +8 lines read, +0x40 whole fps, +0x44 binning
  timing   0x20: +0 id, +4 hmax (u16), +6 tail cycles (u16), +8 vmax (u16)
The clock is the one for which clock / (hmax*(vmax-1)+tail) rounds to +0x40 for every mode.
    imx455_modes.py IMAGE GEO_VA TIM_VA COUNT [--csv OUT]
"""
import sys, struct, csv
from pathlib import Path
B = Path(sys.argv[1]).read_bytes()
geo, tim, n = int(sys.argv[2], 16), int(sys.argv[3], 16), int(sys.argv[4])
BASE = 0xC0000000
rows = []
for i in range(n):
    g = struct.unpack_from('<25I', B, geo - BASE + i * 0x64)
    t = struct.unpack_from('<IHHH', B, tim - BASE + i * 0x20)
    assert g[0] == t[0], (i, g[0], t[0])
    rows.append(dict(i=i, id=g[0], width=g[1], lines=g[2], out_w=g[11], out_h=g[12], fps=g[16], binning=g[17],
                     hmax=t[1], tail=t[2], vmax=t[3]))
def cycles(r): return r['hmax'] * (r['vmax'] - 1) + r['tail']
use = [r for r in rows if r['fps'] and cycles(r)]
best = None
for khz in range(10000, 200001):            # 10..200 MHz in 1 kHz steps
    hz = khz * 1000
    bad = sum(1 for r in use if round(hz / cycles(r)) != r['fps'])
    if best is None or bad < best[0]: best = (bad, hz, [hz])
    elif bad == best[0]: best[2].append(hz)
bad, _, cands = best
print(f'{len(rows)} modes, {len(use)} with a frame rate; best clock fits {len(use)-bad}/{len(use)}: '
      f'{cands[0]/1e6:.3f}..{cands[-1]/1e6:.3f} MHz ({len(cands)} kHz steps)')
if '--csv' in sys.argv:
    out = sys.argv[sys.argv.index('--csv') + 1]
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) + ['cycles']); w.writeheader()
        for r in rows: w.writerow({**r, 'cycles': cycles(r)})
    print('wrote', out)
for r in rows[:73]:
    pass
