"""Find and export monotonic 16-bit curves (tone / gamma / linearisation LUTs) in a dp2q image.

Scans the data area (0x40210000..0x40C40000) for runs of >= 255 non-decreasing little-endian u16 values
spanning >= 200 with mostly distinct entries. Writes curves.csv (address, length, min, max, users) and one
column file per curve plus a preview sheet into out_dp2q/extract/curves/.

Master 2.03 notes: 0x402C198E holds two 2048-entry gamma-type curves (0..4095, used by FUN_4008F040);
0x402CAC3A a 4096-entry log-like curve (0..12287, FUN_400CC3A8); 0x40457408.. R/G/B triplets of 256-entry
expansion curves (8-bit -> ~11-bit); identity ramps at 0x4045E408, 0x40461808, 0x404EFB82..
usage: python -I extract_curves.py [master|loader]
"""
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from dp2q_lib import BASE, load, OUT
from PIL import Image, ImageDraw


def main(name='master'):
    d, used = load(name)
    lo, hi = 0x210000, min(0xC40000, used)
    a = np.frombuffer(d[lo:hi - (hi - lo) % 2], dtype='<u2')
    brk = np.flatnonzero(np.diff(a.astype(np.int32)) < 0)
    starts = np.concatenate(([0], brk + 1)); ends = np.concatenate((brk + 1, [len(a)]))
    runs = []
    for s, e in zip(starts, ends):
        seg = a[s:e]
        if e - s >= 255 and int(seg[-1]) - int(seg[0]) >= 200 and len(np.unique(seg)) > (e - s) * 0.5:
            runs.append((BASE + lo + 2 * int(s), seg))
    out = Path(OUT, 'extract', 'curves'); out.mkdir(parents=True, exist_ok=True)
    with open(out / f'{name}_curves.csv', 'w') as f:
        f.write('addr,length,min,max\n')
        for adr, seg in runs:
            f.write(f'{adr:#x},{len(seg)},{int(seg.min())},{int(seg.max())}\n')
            (out / f'{name}_curve_{adr:08x}.txt').write_text('\n'.join(map(str, seg.tolist())) + '\n')
    W, H, cols = 260, 200, 8
    sheet = Image.new('RGB', (W * cols, (H + 20) * ((len(runs) + cols - 1) // cols)), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for k, (adr, seg) in enumerate(runs):
        v = seg.astype(float); n = len(v); x0, y0 = (k % cols) * W, (k // cols) * (H + 20)
        span = v.max() - v.min() or 1
        dr.line([(x0 + 5 + i * (W - 10) / (n - 1), y0 + H - 5 - (v[i] - v.min()) / span * (H - 10)) for i in range(n)],
                fill=(0, 220, 120))
        dr.text((x0 + 4, y0 + H + 2), f'{adr:#x} n={n} max={int(v.max())}', fill=(255, 255, 0))
    sheet.save(out / f'{name}_curves.png')
    print(f'{len(runs)} curves -> {out}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'master')
