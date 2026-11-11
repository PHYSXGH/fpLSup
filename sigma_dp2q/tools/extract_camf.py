"""Dump the CAMF record set and the file-format templates of a dp2 Quattro image.

CAMF (master 2.03: data area from 0x402A3424): Sigma CAMF records, each
  'CMb?' u32 version, u32 record size, u32 name offset, u32 data offset   (offsets from the record start)
  CMbM (matrix): at data offset: u32 type, u32 ndims, u32 values offset, then ndims x {u32 size, u32 name
        offset, u32 index}; values at the values offset. Element size is taken from the space available
        (4, 2 or 1 bytes); type 3 is decoded as float32, others as signed integers.
  CMbP (property list): at data offset: u32 count, u32 strings offset, then count x {u32 name, u32 value}
        offsets relative to the strings offset.
  CMbT (text): at data offset: u32 length, then text.
These are the firmware's built-in records; the camera fills values per shot / from calibration.

Templates: X3F (image 0x40BE83B4), X3I (0x40BE90C8, both 0xD14 bytes) and DNG (0x40BEBEB4, up to the end of
its last SubIFD block, 0x1180 bytes) are written as binaries.
Output: out_dp2q/extract/formats/{camf.json, camf.txt, x3f_template.bin, x3i_template.bin, dng_template.bin}
usage: python -I extract_camf.py
"""
import sys, struct, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dp2q_lib import BASE, load, OUT

CAMF_START = 0x402A3424
TEMPLATES = {'x3f_template.bin': (0x40BE83B4, 0xD14), 'x3i_template.bin': (0x40BE90C8, 0xD14),
             'dng_template.bin': (0x40BEBEB4, 0x1180)}


def cstr(d, o):
    e = d.find(b'\0', o, o + 256)
    return d[o:e].decode('latin-1')


def main():
    d, used = load('master')
    out = Path(OUT, 'extract', 'formats'); out.mkdir(parents=True, exist_ok=True)
    recs, o = [], CAMF_START - BASE
    while d[o:o + 3] == b'CMb':
        tag = d[o:o + 4].decode(); ver, size, noff, doff = struct.unpack_from('<IIII', d, o + 4)
        if not 0x14 <= size < 0x100000:
            break
        r = dict(addr=hex(BASE + o), tag=tag, name=cstr(d, o + noff), size=size)
        try:
            if tag == 'CMbM':
                typ, nd, voff = struct.unpack_from('<III', d, o + doff)
                dims = []
                for k in range(nd):
                    sz, dn, idx = struct.unpack_from('<III', d, o + doff + 12 + 12 * k)
                    dims.append(dict(size=sz, name=cstr(d, o + dn) if dn else '', index=idx))
                count = 1
                for dm in dims:
                    count *= max(dm['size'], 1)
                room = size - voff
                es = 4 if room >= 4 * count else 2 if room >= 2 * count else 1
                fmt = {4: 'f' if typ == 3 else 'i', 2: 'h', 1: 'b'}[es]
                vals = list(struct.unpack_from('<%d%s' % (count, fmt), d, o + voff)) if count <= 100000 else []
                if fmt == 'f':
                    vals = [round(v, 6) for v in vals]
                r.update(type=typ, dims=dims, elem_bytes=es, values=vals)
            elif tag == 'CMbP':
                cnt, soff = struct.unpack_from('<II', d, o + doff)
                props = {}
                for k in range(cnt):
                    a, b = struct.unpack_from('<II', d, o + doff + 8 + 8 * k)
                    props[cstr(d, o + soff + a)] = cstr(d, o + soff + b)
                r.update(properties=props)
            elif tag == 'CMbT':
                ln = struct.unpack_from('<I', d, o + doff)[0]
                r.update(text=d[o + doff + 4:o + doff + 4 + ln].split(b'\0')[0].decode('latin-1'))
        except struct.error:
            r.update(error='out of range')
        recs.append(r); o += size
    (out / 'camf.json').write_text(json.dumps(recs, indent=1, ensure_ascii=False) + '\n')
    with open(out / 'camf.txt', 'w') as f:
        for r in recs:
            if r['tag'] == 'CMbM':
                dims = ' x '.join(f"{x['size']}{'(' + x['name'] + ')' if x['name'] else ''}" for x in r['dims'])
                v = r['values']; vs = ', '.join(map(str, v[:12])) + (' …' if len(v) > 12 else '')
                f.write(f"{r['tag']} {r['name']:<40} type {r['type']} [{dims}] = {vs}\n")
            elif r['tag'] == 'CMbP':
                f.write(f"{r['tag']} {r['name']:<40} {len(r['properties'])} properties: " +
                        ', '.join(f'{k}={v}' for k, v in list(r['properties'].items())[:8]) + '\n')
            else:
                f.write(f"{r['tag']} {r['name']:<40} {r.get('text', '')[:200]!r}\n")
    for fn, (a, n) in TEMPLATES.items():
        (out / fn).write_bytes(d[a - BASE:a - BASE + n])
    print(f'{len(recs)} CAMF records, templates {list(TEMPLATES)} -> {out}')


if __name__ == '__main__':
    main()
