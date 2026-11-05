"""Unpack a SIGMA dp Quattro update image (DP2QVxxx.BIN; checked on DP2QV203.BIN = 2.03.0.10129).

Container (worked out from DP2QV203.BIN, no checksum found yet):

  0x00  char[16]  "SIGMA.CODP2Q"           model tag, NUL padded
  0x10  char[16]  "2.03.0.10129"           version, NUL padded
  0x20  {u32 BE offset, u32 BE size}[]     chunk table, ends at a zero size (or at 0x40)
  0x40  chunks, back to back

  DP2QV203: chunk 0 @0x40       size 0xE20000  "SIGMA_FWb"  M7_Loader image (Cortex-A9)
            chunk 1 @0xE20040   size 0xE20000  "SIGMA_FWc"  M7_Master image (Cortex-A9)
            chunk 2 @0x1C40040  size 0x20000   no tag, not ARM code (unidentified)

An ARM image chunk ("SIGMA_FW" + letter) has a 0x20000-byte header block: the tag and a
parameter block in the first 0x14C bytes (meaning not decoded), 0xFF after it. The code starts at chunk+0x20000 with
an ARM vector table whose literal pool points into 0x40000000, so that offset loads at
0x40000000. The image is padded with 0xFF up to the chunk size.

Writes, into DEST:
  hdr.bin                     the 0x40-byte outer header
  <name>_hdr.bin              each ARM chunk's 0x14C-byte header (the 0xFF fill is dropped)
  <name>_40000000.bin         each ARM chunk's code, load address 0x40000000 (full length, padding kept)
  chunk<N>.bin                any chunk that is not an ARM image, raw
  manifest.json

usage: python3 -I unpack_dp2q.py firmware/DP2QV203.BIN out_dp2q
"""
import sys, struct, hashlib, json
from pathlib import Path

CODE_OFF = 0x20000
HDR_LEN = 0x14C                               # tag + parameters; 0xFF fill up to CODE_OFF
LOAD = 0x40000000
VEC = bytes.fromhex('18f09fe5') * 5          # ldr pc, [pc, #0x18] x5: undef..data abort


def sha(b):
    return hashlib.sha256(b).hexdigest()


def arm_chunk(c):
    """Return (tag, reset) if c is a SIGMA_FW ARM image with the expected vector table."""
    if not c.startswith(b'SIGMA_FW') or len(c) <= CODE_OFF + 0x40:
        return None
    code = c[CODE_OFF:]
    if code[:20] != VEC:
        raise SystemExit('SIGMA_FW chunk without the expected vector table at +0x20000')
    if c[HDR_LEN:CODE_OFF].strip(b'\xff'):
        raise SystemExit(f'SIGMA_FW header block is not 0xFF after {HDR_LEN:#x}; layout differs')
    # vector literal pool at +0x20: reset handler and the others must point into the image
    lits = struct.unpack_from('<8I', code, 0x20)
    used = [v for v in lits if v]
    if not all(LOAD <= v < LOAD + len(code) for v in used):
        raise SystemExit(f'vector literals {[hex(v) for v in lits]} do not fall in {LOAD:#x}+image')
    tag = c[:16].split(b'\0')[0].decode('ascii')
    return tag, lits[0]


def name_for(code, tag):
    if b'/M7_Loader/' in code and b'/M7_Master/' not in code:
        return 'loader'
    if b'/M7_Master/' in code and b'/M7_Loader/' not in code:
        return 'master'
    return tag.lower()


def main(fw, dest):
    b = Path(fw).read_bytes(); dest = Path(dest); dest.mkdir(parents=True, exist_ok=True)
    if not b.startswith(b'SIGMA.CO'):
        raise SystemExit('not a SIGMA.CO container')
    model = b[0x00:0x10].split(b'\0')[0].decode('ascii')
    version = b[0x10:0x20].split(b'\0')[0].decode('ascii')
    chunks = []
    for o in range(0x20, 0x40, 8):
        off, size = struct.unpack_from('>II', b, o)
        if size == 0:
            break
        chunks.append((off, size))
    if not chunks or chunks[0][0] != 0x40:
        raise SystemExit('chunk table does not start at 0x40')
    for (o1, s1), (o2, _) in zip(chunks, chunks[1:]):
        if o1 + s1 != o2:
            raise SystemExit(f'chunks not contiguous at {o1 + s1:#x} / {o2:#x}')
    end = chunks[-1][0] + chunks[-1][1]
    if end != len(b):
        raise SystemExit(f'chunk table ends at {end:#x}, file is {len(b):#x}')

    info = dict(source=Path(fw).name, sha256=sha(b), size=len(b), model=model, version=version,
                chunks=[])
    (dest / 'hdr.bin').write_bytes(b[:0x40])
    names = set()
    for i, (off, size) in enumerate(chunks):
        c = b[off:off + size]
        rec = dict(index=i, file_off=hex(off), size=hex(size), sha256=sha(c))
        arm = arm_chunk(c)
        if arm:
            tag, reset = arm
            code = c[CODE_OFF:]
            name = name_for(code, tag)
            if name in names:
                name = f'{name}{i}'
            names.add(name)
            (dest / f'{name}_hdr.bin').write_bytes(c[:HDR_LEN])
            fn = f'{name}_{LOAD:08x}.bin'
            (dest / fn).write_bytes(code)
            rec.update(kind='arm', tag=tag, name=name, file=fn, load=hex(LOAD), reset=hex(reset),
                       code_len=hex(len(code)), used_len=hex(len(code.rstrip(b'\xff'))),
                       code_sha256=sha(code), hdr_file=f'{name}_hdr.bin')
        else:
            fn = f'chunk{i}.bin'
            (dest / fn).write_bytes(c)
            rec.update(kind='raw', file=fn, nonzero=sum(1 for x in c if x))
        info['chunks'].append(rec)
    (dest / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
