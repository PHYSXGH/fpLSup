"""Run every hard-coded 0xC0000000-0xCFFFFFFF constant in the code through AddrMap."""
import sys, re
from pathlib import Path
from collections import Counter, defaultdict
sys.path.insert(0, str(Path(__file__).parent))
from addrmap import AddrMap, ROOT
m = AddrMap()
pat = re.compile(r'\b0[xX]([Cc][0-9A-Fa-f]{7})\b')
exts = {'.py', '.c', '.h', '.S', '.s', '.ld', '.js', '.txt', '.json'}
uses = defaultdict(set)
for top in sys.argv[1:]:
    for f in Path(ROOT / top).rglob('*'):
        if f.suffix in exts and f.is_file() and 'node_modules' not in f.parts and '.venv' not in f.parts:
            try: t = f.read_text(errors='ignore')
            except Exception: continue
            for x in pat.findall(t):
                uses[int(x, 16)].add(str(f.relative_to(ROOT)))
cls = Counter(); bad = []
for a in sorted(uses):
    r, how = m.map(a)
    key = how.split('(')[0] if how else 'none'
    if a >= m.img_end_a and how == 'ram-unknown': key = 'ram-unknown'
    cls[key] += 1
    if r is None: bad.append((a, how, len(uses[a])))
print('distinct addresses', len(uses)); print(dict(cls))
print('unmapped, most used:')
for a, how, n in sorted(bad, key=lambda t: -t[2])[:40]: print(f'  {a:#010x} {how:12} used in {n} files')
