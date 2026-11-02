"""Write projects/fpl-port/addr_table.csv: every hard-coded firmware address in the
given trees, its fp L counterpart, the method, and a confidence class.

  high    exact byte-aligned run, or data window + pointer evidence agreeing
  medium  single source of evidence (pointer pair / window) or fuzzy code match >= 0.9
  low     guessed from a nearby struct base, or fuzzy match < 0.9 -- RE by hand
  none    no evidence
Only addresses, no firmware bytes, are written.
"""
import sys, re, csv
from pathlib import Path
from collections import defaultdict, Counter
sys.path.insert(0, str(Path(__file__).parent))
from addrmap import AddrMap, ROOT, BASE

m = AddrMap()
pat = re.compile(r'\b0[xX]([Cc][0-9A-Fa-f]{7})\b')
exts = {'.py', '.c', '.h', '.S', '.s', '.ld', '.js', '.txt', '.json'}
uses = defaultdict(set)
for top in sys.argv[1:]:
    for f in Path(ROOT / top).rglob('*'):
        if f.suffix in exts and f.is_file() and not {'node_modules', '.venv', 'fpl-port'} & set(f.parts):
            for x in pat.findall(f.read_text(errors='ignore')):
                uses[int(x, 16)].add(str(f.relative_to(ROOT)))

rows = []; cls = Counter()
for a in sorted(uses):
    r, how = m.map(a)
    how = how or ''
    if how == 'exact' or how.startswith('ram('):
        c = 'high'
    elif r is not None and 'CONFLICT' not in how and ('+' in how):
        c = 'high'
    elif r is not None and 'CONFLICT' not in how and not how.startswith('ptr-base'):
        c = 'medium'
    elif r is not None:
        c = 'low'
    elif BASE <= a < m.img_end_a:
        r, sim, second = m.fuzzy(a)
        how = f'fuzzy {sim:.2f}/{second:.2f}'
        c = 'medium' if sim >= 0.9 and second < 0.8 else 'low'
    else:
        c = 'none'
    cls[c] += 1
    rows.append([f'{a:#010x}', f'{r:#010x}' if r is not None else '', c, how, len(uses[a]), ' '.join(sorted(uses[a])[:3])])
out = ROOT / 'projects/fpl-port/addr_table.csv'
with open(out, 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['fp_502', 'fpl_302', 'confidence', 'method', 'n_files', 'example_files']); w.writerows(rows)
print(len(rows), dict(cls), '->', out.relative_to(ROOT))
