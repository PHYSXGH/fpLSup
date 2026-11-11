"""Decode the dp2 Quattro UI icons to PNG (out_dp2q/extract/icons/).

Master 2.03: icon table at RAM 0x41051A80 (.data, image 0x40C28C84), 12-byte entries indexed by icon ID
1..797: {u8 format, u8, u16 width, u16 height, u16, u32 data}. Pixels (from the draw code at 0x4011E7CA):
  format 1: 16 bpp, nibbles R | A | B | G (bits 15-12, 11-8, 7-4, 3-0)       (FUN_4011E672 / FUN_4011E6C0)
  format 0:  8 bpp, high nibble = grey (R=G=B), low nibble = alpha            (FUN_4011E79E)
Rows are tightly packed (width pixels). Writes icon_<id>.png, an index TSV and a contact sheet.

usage: python -I extract_icons.py
"""
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dp2q_lib import BASE, load, OUT
from PIL import Image, ImageDraw

TABLE = 0x40C28C84
N = 797
n4 = lambda v: v * 17


def main():
    d, used = load('master')
    out = Path(OUT, 'extract', 'icons'); out.mkdir(parents=True, exist_ok=True)
    rows, ims = [], []
    for i in range(1, N + 1):
        fmt, _, w, h, _, ptr = struct.unpack_from('<BBHHHI', d, TABLE - BASE + i * 12)
        bpp = 2 if fmt else 1
        o = ptr - BASE
        if not (w and h and 0 <= o and o + w * h * bpp <= len(d)):
            rows.append((i, fmt, w, h, ptr, 'skipped')); continue
        im = Image.new('RGBA', (w, h))
        px = im.load()
        for y in range(h):
            for x in range(w):
                if fmt:
                    v = struct.unpack_from('<H', d, o + (y * w + x) * 2)[0]
                    r, a, b, g = v >> 12, (v >> 8) & 15, (v >> 4) & 15, v & 15
                else:
                    v = d[o + y * w + x]
                    r = g = b = v >> 4; a = v & 15
                px[x, y] = (n4(r), n4(g), n4(b), n4(a))
        im.save(out / f'icon_{i:03d}.png')
        rows.append((i, fmt, w, h, ptr, 'ok')); ims.append((i, im))
    (out / 'icons.tsv').write_text('id\tformat\twidth\theight\tdata\tstatus\n' +
                                  ''.join(f'{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\t{r[4]:#x}\t{r[5]}\n' for r in rows))
    # contact sheet of small icons (<= 96 px), on a mid-grey background so grey/alpha icons show
    small = [(i, im) for i, im in ims if im.width <= 96 and im.height <= 96]
    cols, cell = 20, 104
    sheet = Image.new('RGBA', (cols * cell, ((len(small) + cols - 1) // cols) * cell), (60, 60, 60, 255))
    dr = ImageDraw.Draw(sheet)
    for k, (i, im) in enumerate(small):
        x, y = (k % cols) * cell, (k // cols) * cell
        sheet.alpha_composite(im, (x + (cell - im.width) // 2, y + 4))
        dr.text((x + 2, y + cell - 12), str(i), fill=(255, 255, 0, 255))
    sheet.save(out / 'contact_sheet.png')
    print(f'{len(ims)} icons decoded, {sum(1 for r in rows if r[5] != "ok")} skipped, sheet {len(small)} -> {out}')


if __name__ == '__main__':
    main()
