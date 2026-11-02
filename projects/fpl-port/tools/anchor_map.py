"""Coarse fp(5.02) -> fp L(3.02) address map from unique 32-byte chunks.

Every 4-aligned 32-byte window in the fp image that occurs exactly once in each
image becomes an anchor. Anchors are reduced to a monotonic chain (longest
increasing subsequence), then merged into runs of constant delta.
Output: out_fpl/anchor_runs.json  [[fp_start, fp_end, delta, n_anchors], ...]
"""
import sys, json, bisect
from pathlib import Path
from collections import Counter
import numpy as np

W = 32
A = Path(sys.argv[1]).read_bytes(); B = Path(sys.argv[2]).read_bytes()

def windows(buf):
    a = np.frombuffer(buf[:len(buf)//8*8], dtype='<u8')
    # 32-byte window at each 8-aligned offset, hashed from 4 u8 words
    n = len(a) - 3
    h = a[:n].copy()
    for k in (1, 2, 3):
        h = h * np.uint64(0x9E3779B97F4A7C15) ^ a[k:k+n]
    return h

ha = windows(A); hb = windows(B)
def uniq(h):
    v, idx, cnt = np.unique(h, return_index=True, return_counts=True)
    m = cnt == 1
    return v[m], idx[m]
va, ia = uniq(ha); vb, ib = uniq(hb)
common, pa, pb = np.intersect1d(va, vb, assume_unique=True, return_indices=True)
# skip trivial windows (all zero / all FF / repeated words)
pairs = sorted(zip((ia[pa]*8).tolist(), (ib[pb]*8).tolist()))
print('anchors', len(pairs), file=sys.stderr)

# LIS on fpL offsets
tails = []; tidx = []; prev = [-1]*len(pairs)
for i, (_, b) in enumerate(pairs):
    j = bisect.bisect_left(tails, b)
    if j == len(tails): tails.append(b); tidx.append(i)
    else: tails[j] = b; tidx[j] = i
    prev[i] = tidx[j-1] if j else -1
chain = []; k = tidx[-1]
while k != -1: chain.append(pairs[k]); k = prev[k]
chain.reverse()
print('chain', len(chain), file=sys.stderr)

runs = []
for a, b in chain:
    d = b - a
    if runs and runs[-1][2] == d:
        runs[-1][1] = a + W; runs[-1][3] += 1
    else:
        runs.append([a, a + W, d, 1])
runs = [r for r in runs if r[3] >= 2]
json.dump(runs, open(sys.argv[3], 'w'))
cov = sum(r[1]-r[0] for r in runs)
print('runs', len(runs), 'covered bytes', cov, f'{cov/len(A):.1%}', file=sys.stderr)
for r in runs[:5]+runs[-5:]: print([hex(x) for x in r[:2]], hex(r[2]) if r[2]>=0 else '-'+hex(-r[2]), r[3], file=sys.stderr)
