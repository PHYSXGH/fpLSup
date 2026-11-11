"""Carve embedded JPEG and BMP images from a dp2q image into out_dp2q/extract/images/.

JPEG: every SOI (FF D8 FF) is parsed marker by marker up to EOI; only files Pillow can decode are kept.
BMP:  'BM' + plausible header (file size, pixel offset, DIB header size 40/108/124); kept if Pillow decodes.

Result on master 2.03: nothing. The only BMP header (0x402C4C14, 640x480) is a header template followed by
unrelated firmware bytes (debug OSD screenshots are saved as BMP), and the JPEG markers are either noise or
the EXIF APP1 template at 0x40BE4F98. UI graphics are in a custom format (see extract_icons.py).

usage: python -I extract_images.py [master|loader]
"""
import sys, struct, io, re, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dp2q_lib import BASE, load, OUT
from PIL import Image


def jpeg_end(d, o):
    p = o + 2
    while p + 4 <= len(d):
        if d[p] != 0xFF:
            return None
        m = d[p + 1]
        if m == 0xD9:
            return p + 2
        if m in (0x01,) or 0xD0 <= m <= 0xD7:
            p += 2; continue
        ln = struct.unpack_from('>H', d, p + 2)[0]
        if m == 0xDA:                                      # scan: skip entropy data to the next marker
            q = p + 2 + ln
            while q + 1 < len(d):
                if d[q] == 0xFF and d[q + 1] not in (0x00,) and not 0xD0 <= d[q + 1] <= 0xD7:
                    break
                q += 1
            p = q; continue
        p += 2 + ln
    return None


def main(name='master'):
    d, used = load(name)
    out = Path(OUT, 'extract', 'images'); out.mkdir(parents=True, exist_ok=True)
    found = []
    for m in re.finditer(rb'\xff\xd8\xff', d[:used]):
        o = m.start(); e = jpeg_end(d, o)
        if not e or e - o > 4 << 20:
            continue
        blob = d[o:e]
        try:
            im = Image.open(io.BytesIO(blob)); im.load()
        except Exception:
            continue
        fn = f'{name}_jpeg_{BASE + o:08x}_{im.width}x{im.height}.jpg'
        (out / fn).write_bytes(blob); found.append(dict(file=fn, addr=hex(BASE + o), size=len(blob), w=im.width, h=im.height))
    for m in re.finditer(rb'BM', d[:used]):
        o = m.start()
        if o + 54 > used:
            continue
        fsize, _, off, hdr = struct.unpack_from('<IIII', d, o + 2)
        if hdr not in (40, 108, 124) or not 54 <= off < fsize < 8 << 20:
            continue
        blob = d[o:o + fsize]
        try:
            im = Image.open(io.BytesIO(blob)); im.load()
        except Exception:
            continue
        fn = f'{name}_bmp_{BASE + o:08x}_{im.width}x{im.height}.png'
        im.save(out / fn); found.append(dict(file=fn, addr=hex(BASE + o), size=fsize, w=im.width, h=im.height))
    (out / f'{name}_images.json').write_text(json.dumps(found, indent=1) + '\n')
    for f in found:
        print(f)
    print(f'{len(found)} images -> {out}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'master')
