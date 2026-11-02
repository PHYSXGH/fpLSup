"""Set table rows by hand:  set_rows.py 'FP\tFPL\tSTATUS\tNOTE' ..."""
import sys
from pathlib import Path
p = Path(__file__).resolve().parents[3] / 'fpSup/fp_usb_shell/cameras/fpl302.tsv'
fix = {}
for r in sys.argv[1:]:
    f = r.split('\t'); fix[int(f[0], 16)] = f'{int(f[0], 16):#010x}\t' + '\t'.join(f[1:])
out = []
for l in p.read_text().splitlines():
    f = l.split('\t')
    if len(f) > 2 and not l.startswith('#') and f[2] != 'range' and int(f[0], 16) in fix:
        l = fix.pop(int(f[0], 16))
    out.append(l)
out += fix.values()
p.write_text('\n'.join(out) + '\n'); print('ok')
