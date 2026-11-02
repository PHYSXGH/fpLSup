"""Wrap every 0xC0000000..0xCFFFFFFF number literal in a Python file's code as
fw(0x...), leaving comments and strings alone, and add `from fwtarget import fw`
after the line that puts fp_usb_shell on sys.path (or after the imports).
    wrap_fw.py FILE...      (idempotent: already-wrapped literals are skipped)"""
import sys, io, re, tokenize
pat = re.compile(r'0[xX][Cc][0-9A-Fa-f]{7}')
for path in sys.argv[1:]:
    src = open(path).read()
    toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    lines = src.splitlines(keepends=True)
    edits = []
    for i, t in enumerate(toks):
        if t.type == tokenize.NUMBER and pat.fullmatch(t.string):
            prev = toks[i - 1] if i else None
            if prev and prev.string == '(' and i > 1 and toks[i - 2].string == 'fw':
                continue
            edits.append((t.start, t.end, f'fw({t.string})'))
    for (r, c0), (_, c1), new in sorted(edits, reverse=True):
        l = lines[r - 1]; lines[r - 1] = l[:c0] + new + l[c1:]
    out = ''.join(lines)
    if edits and 'from fwtarget import fw' not in out:
        ls = out.splitlines(keepends=True)
        at = None
        for k, l in enumerate(ls):
            if re.match(r'sys\.path\.insert\(0, *str\((SHELL|HERE)', l) or re.match(r'from armasm import', l):
                at = k + 1
                if 'armasm' in l: break
        if at is None:
            imps = [k for k, l in enumerate(ls[:80]) if re.match(r'(import|from) ', l)]
            if imps:
                at = imps[-1] + 1
            else:                       # no imports: right after the module docstring
                doc = next(t for t in tokenize.generate_tokens(io.StringIO(out).readline)
                           if t.type == tokenize.STRING)
                at = doc.end[0]
        ls.insert(at, 'from fwtarget import fw                                       # noqa: E402\n')
        out = ''.join(ls)
    open(path, 'w').write(out)
    print(f'{path}: {len(edits)} wrapped')
