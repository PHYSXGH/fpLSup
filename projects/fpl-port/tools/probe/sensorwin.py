"""Narrow UHDC's sensor read in RAM (ISSUES.md 2; nothing on the card; a reboot undoes it).

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 sensorwin.py WIDTH [START] [undo.json]
    ... sensorwin.py undo undo.json

UHDC records 3856x2170 from the middle of mode 196's 6288x2174 read; its live view while recording
scales the whole read (~1.63x squeeze). This makes the sensor read WIDTH columns instead, in:
  - mode 196's register record (0xC0BAA188, RES-Custom clones it at record start): +0xB0/+0xB4
    and +0xB8/+0xBC = WIDTH + 16, low byte / high byte;
  - mode 196's size rows (0xC0B93338 / 48 / 58) and its row in the 0x3C-byte table at 0xC0BB33xx
    (the last column 6287 twice, the size 6288);
  - RES-Custom's copies: UHDC's canvas entries (0xF4, 6288) and mode 233's size rows (heap, found).
START: mode 196's record +0x10 (32 for the 6304-wide window, 16 for 8224: ~60 columns a step,
camera 2026-11-06: the width alone keeps the window's left edge, A001_210).
"""
import json, struct, sys
import putfile as P
from recdiag import rd, flush

REC196 = 0xC0BAA188
ROWS196 = (0xC0B93338, 0xC0B93348, 0xC0B93358)
OLD_W = 6288


def heap():
    a, b = 0xC5000000, 0xC5800000
    P.mem_caps(refresh=True)
    flush()
    P.mem_window(0, a - 0x80000000, b - a, 1)
    data = b''.join(P.mem_read(p - 0x80000000, min(8 << 20, b - p)) for p in range(a, b, 8 << 20))
    return a, struct.unpack(f'<{len(data) // 4}I', data)


def table_row():
    a = 0xC0BB2000
    w = rd(a, 0x2000 // 4) if False else None
    base, words = 0xC0BB2000, []
    for off in range(0, 0x2000, 0x400):
        words += rd(base + off, 256)
    for i in range(len(words) - 15):
        if words[i] == 196 and words[i + 7] == OLD_W - 1 and words[i + 9] == OLD_W - 1 and words[i + 13] == OLD_W:
            return base + 4 * i
    raise SystemExit('mode 196 table row not found')


def plan(width, start=None):
    hi, lo = (width + 16) >> 8, (width + 16) & 0xFF
    out = [(REC196 + 0x10, 32, start)] if start is not None else []
    out += [(REC196 + 0xB0, 0xA0, lo), (REC196 + 0xB4, 0x18, hi), (REC196 + 0xB8, 0xA0, lo), (REC196 + 0xBC, 0x18, hi)]
    out += [(a, OLD_W, width) for a in ROWS196]
    t = table_row()
    out += [(t + 4 * 7, OLD_W - 1, width - 1), (t + 4 * 9, OLD_W - 1, width - 1), (t + 4 * 13, OLD_W, width)]
    base, w = heap()
    for i in range(1, len(w) - 8):
        if w[i] == OLD_W and w[i - 1] == 0xF4 and w[i + 1] == 0xF8 and w[i + 2] == 2174:
            out.append((base + 4 * i, OLD_W, width))                # a canvas entry (0xF4, 6288)
        if w[i - 1] == 233 and w[i] == OLD_W and w[i + 1] == 2174:
            out += [(base + 4 * (i + k), OLD_W, width) for k in (0, 4, 8) if w[i + k] == OLD_W]
    return out


def main():
    if sys.argv[1] == 'undo':
        for a, v in json.load(open(sys.argv[2])):
            P.mem_set(a, v)
        flush()
        print('restored')
        return
    width = int(sys.argv[1])
    start = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None
    undo_path = sys.argv[-1] if sys.argv[-1].endswith('.json') else 'sensorwin_undo.json'
    undo = []
    for a, old, new in plan(width, start):
        cur = rd(a, 1)[0]
        if cur != old:
            print(f'skip {a:#x}: holds {cur}, expected {old}')
            continue
        P.mem_set(a, new)
        undo.append((a, old))
    flush()
    json.dump(undo, open(undo_path, 'w'))
    print(f'{len(undo)} words changed for a {width}-wide read; undo: {undo_path}')
    for a, _ in undo:
        print(f'  {a:#x} = {rd(a, 1)[0]}')


if __name__ == '__main__':
    main()
