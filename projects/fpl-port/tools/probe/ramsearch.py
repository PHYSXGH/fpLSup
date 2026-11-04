"""Search a RAM dump (ramdump.py) for structures that know exactly the fp L's real sensor mode ids.

    python3 ramsearch.py DUMPDIR [IMAGE]

The 85 ids are the timing table's (0xC0B90FF8, row order = index i).  Looks for:
  bitmap    32 bytes, bit id set exactly for the real ids
  idx map   element size 1/2/4: A[id_i] == i for every row i
  ptr map   4-byte A[id_i] == X + i * stride (a pointer per mode in table order)
  filled    element size 1/2/4: A[id] != 0 for every real id, == 0 for every other id < 218
"""
import os, struct, sys

d = sys.argv[1]
img = open(sys.argv[2] if len(sys.argv) > 2 else
           os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'out_fpl',
                        'MAIN_c0000000.bin'), 'rb').read()
ids = [struct.unpack_from('<I', img, 0xC0B90FF8 + 0x20 * i - 0xC0000000)[0] for i in range(85)]
R = set(ids)
free = [i for i in range(218) if i not in R]
pieces = sorted(f for f in os.listdir(d) if f.startswith('ram_'))
base = int(pieces[0][4:12], 16)
ram = b''.join(open(os.path.join(d, f), 'rb').read() for f in pieces)
print(f'{len(ram) >> 20} MiB from {base:#x}; {len(R)} real ids, {len(free)} free ids below 218')

bm = bytearray(32)
for i in R:
    bm[i >> 3] |= 1 << (i & 7)
at = ram.find(bytes(bm))
while at >= 0:
    print(f'bitmap at {base + at:#x}')
    at = ram.find(bytes(bm), at + 1)

for size, fmt in ((1, 'B'), (2, 'H'), (4, 'I')):
    span = size * 256
    for off in range(0, len(ram) - span, size if size > 1 else 1):
        v0 = int.from_bytes(ram[off + size * ids[0]: off + size * ids[0] + size], 'little')
        v1 = int.from_bytes(ram[off + size * ids[1]: off + size * ids[1] + size], 'little')
        if v0 == 0 and v1 == 1:
            if all(int.from_bytes(ram[off + size * ids[i]: off + size * ids[i] + size], 'little') == i
                   for i in range(85)):
                print(f'idx map ({size}-byte) at {base + off:#x}')
        if size == 4 and 0xC0000000 <= v0 < 0xD0000000 and v1 > v0:
            stride = v1 - v0
            if stride < 0x1000 and all(
                    int.from_bytes(ram[off + 4 * ids[i]: off + 4 * ids[i] + 4], 'little') == v0 + i * stride
                    for i in range(85)):
                print(f'ptr map at {base + off:#x}: {v0:#x} + i * {stride:#x}')
    # filled: non-zero exactly at the real ids (slow-ish: test a cheap anchor first)
    z = (0).to_bytes(size, 'little')
    for off in range(0, len(ram) - span, size):
        if ram[off + size * free[0]: off + size * free[0] + size] != z:
            continue
        if ram[off + size * ids[0]: off + size * ids[0] + size] == z:
            continue
        if all(ram[off + size * i: off + size * i + size] != z for i in ids) and \
                all(ram[off + size * i: off + size * i + size] == z for i in free):
            print(f'filled ({size}-byte) at {base + off:#x}')
