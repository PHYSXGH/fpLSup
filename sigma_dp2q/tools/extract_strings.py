"""Dump the dp2 Quattro UI message tables (UTF-8) to out_dp2q/extract/strings/.

Master 2.03: a run of string pointers in .data (image 0x40BF53CC..0x40BFF4A4, copied to RAM 0x4101E1C8..)
holds 17 language tables of 586 entries each (base list at 0x4014CBD8, one RAM pointer per language) and a
further table of 332 entries at entry 9962 (pointer at 0x4014CC84). Pointers may be image or RAM addresses.

Writes messages.tsv (id, then one column per language) and extra.tsv.
usage: python -I extract_strings.py
"""
import sys, struct, csv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dp2q_lib import BASE, load, OUT

LANGS = ['en', 'ja', 'de', 'fr', 'es', 'it', 'zh-Hans', 'zh-Hant', 'ko', 'ru', 'nl', 'pl', 'pt', 'da', 'sv', 'no', 'fi']
RUN = 0x40BF53CC          # image address of entry 0
N_PER_LANG = 586
EXTRA_AT, EXTRA_N = 9962, 332
DATA_IMG, DATA_RAM = 0x40BD8674, 0x41001470


def main():
    d, used = load('master')
    w = lambda a: struct.unpack_from('<I', d, a - BASE)[0]

    def text(v):
        a = v - DATA_RAM + DATA_IMG if DATA_RAM <= v < 0x42000000 else v
        if not BASE <= a < BASE + len(d):
            return f'<{v:#x}>'
        o = a - BASE; e = d.find(b'\0', o, o + 2000)
        try:
            return d[o:e].decode('utf-8')
        except UnicodeDecodeError:
            return '<hex:' + d[o:e].hex() + '>'

    out = Path(OUT, 'extract', 'strings'); out.mkdir(parents=True, exist_ok=True)
    esc = lambda s: s.replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t')
    with open(out / 'messages.tsv', 'w', newline='') as f:
        f.write('id\t' + '\t'.join(LANGS) + '\n')
        for i in range(N_PER_LANG):
            row = [text(w(RUN + (t * N_PER_LANG + i) * 4)) for t in range(len(LANGS))]
            f.write(f'{i}\t' + '\t'.join(esc(x) for x in row) + '\n')
    with open(out / 'extra.tsv', 'w') as f:
        f.write('id\ttext\n')
        for i in range(EXTRA_N):
            f.write(f'{i}\t{esc(text(w(RUN + (EXTRA_AT + i) * 4)))}\n')
    print(f'{N_PER_LANG} messages x {len(LANGS)} languages, {EXTRA_N} extra -> {out}')


if __name__ == '__main__':
    main()
