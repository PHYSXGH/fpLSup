"""Unpack a SIGMA fp / fp L update image (FP__Vxxx.bin, FPL_Vxxx.bin).

Same container as research/firmware/notes/FORMAT.md: 0x100-byte ASCII headers,
MAIN body starts with an @DFI table whose segment records are LZSS-compressed.
Writes <SEG>_<loadaddr>.bin for each DFI segment, plus IPL/PTBL/DAT1 raw bodies
and a manifest. Not pinned to a single hash; every checksum is verified instead.

usage: python3 -I unpack_fw.py firmware/FPL_V302.bin out_fpl
"""
import sys, struct, hashlib, json, re
from pathlib import Path


def lzss(src, expected):
    ring = bytearray(4096); r = 0xFEE; out = bytearray(); p = 0
    while len(out) < expected:
        flags = src[p]; p += 1
        for bit in range(8):
            if len(out) >= expected:
                break
            if flags & (1 << bit):
                v = src[p]; p += 1
                out.append(v); ring[r] = v; r = (r + 1) & 4095
            else:
                lo, hi = src[p], src[p + 1]; p += 2
                off = lo | ((hi & 0xF0) << 4); n = (hi & 15) + 3
                for k in range(n):
                    v = ring[(off + k) & 4095]; ring[r] = v; r = (r + 1) & 4095
                    if len(out) < expected:
                        out.append(v)
    return bytes(out)


def main(fw, dest):
    b = Path(fw).read_bytes(); dest = Path(dest); dest.mkdir(parents=True, exist_ok=True)
    info = {'source': Path(fw).name, 'sha256': hashlib.sha256(b).hexdigest(), 'sections': [], 'dfi': []}
    pos = 0
    while pos < len(b):
        hdr = b[pos:pos + 0x100].split(b'\n')[0].decode('ascii', 'replace').strip()
        m = re.search(r'LENGTH=(\d+)', hdr)
        if not m:
            break
        length = int(m.group(1)); body = b[pos + 0x100: pos + length]
        name = hdr.split()[0] if not hdr.startswith('LENGTH') else 'MAIN'
        s = int(re.search(r'SUM=(\d+)', hdr).group(1))
        ok = (sum(body) & 0xFFFFFFFF) == s
        info['sections'].append(dict(name=name, header=hdr, file_off=pos, body_len=len(body), sum_ok=ok))
        if not ok:
            raise SystemExit(f'{name}: checksum mismatch')
        if name != 'MAIN':
            (dest / f'{name}.bin').write_bytes(body)
        pos += length
    assert b[0x100:0x104] == b'@DFI'
    rec = 0x120
    while True:
        size, off, base, csum, method, packed = struct.unpack_from('<6I', b, rec)
        if size == 0 or method not in (1, 0x11):
            break
        src = b[0x300 + off: 0x300 + off + packed]
        if sum(src) & 0xFFFFFFFF != csum:
            raise SystemExit(f'DFI seg @{base:#x}: checksum mismatch')
        out = lzss(src, size)
        fn = f'MAIN_{base:08x}.bin' if base == 0xC0000000 else f'SEG_{base:08x}.bin'
        (dest / fn).write_bytes(out)
        info['dfi'].append(dict(file=fn, load=hex(base), size=size, method=method, packed=packed,
                                sha256=hashlib.sha256(out).hexdigest()))
        rec += 0x18
    (dest / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
