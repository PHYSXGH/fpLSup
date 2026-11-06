"""UHDC's recording live-view box, as a RAM-only hook (ISSUES.md 2).  install [XOFF YOFF W H] | remove

    FPSUP_CAMERA=fpl PYTHONPATH=fpSup/fp_usb_shell python3 viewbox.py install 0 0 3856 2170

The box the recording live view is drawn into is computed by 0xC01BA608 from the path's read
(6288x2174 for UHDC: 2.94:1, the ~1.66x squeeze) unless the settings block 0xC31DDCD8 (path 0)
has an override at +0x334/+0x338 (offsets) and +0x33C/+0x340 (width, height). 0xC01CE9D0, the
"configure display" handler, rewrites those from its request on every call. The stub wraps it:
after the handler, if path 0's read width (0xC31DD9BC) is UHDC's 6288, it writes the override.
The handler's first instruction (push.w, 4 bytes, pc-independent) becomes a b.w to the stub; the
stub's trampoline runs that push and goes on at +4.
"""
import json, os, sys
import cave
from recdiag import rd, setw, flush

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'viewbox.json')
SITE = 0xC01CE9D0
STOCK = 0x41F0E92D                       # push.w {r4, r5, r6, r7, r8, lr}
READ_W = 0xC31DD9BC                      # path 0's read width (0xC31DD978 + 0x44)
SETTINGS = 0xC31DDCD8


def asm(src, base, thumb=True):
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM, KS_MODE_THUMB
    enc, _ = Ks(KS_ARCH_ARM, KS_MODE_THUMB if thumb else KS_MODE_ARM).asm(src, base)
    return bytes(enc)


def stub(base, xoff, yoff, w, h):
    src = f"""
        push {{r4, lr}}
        bl tramp
        push {{r0, r1}}
        ldr r1, =0x{READ_W:08X}
        ldr r1, [r1]
        movw r2, #6288
        cmp r1, r2
        bne done
        ldr r1, =0x{SETTINGS:08X}
        ldr r2, ={xoff}
        str.w r2, [r1, #0x334]
        ldr r2, ={yoff}
        str.w r2, [r1, #0x338]
        ldr r2, ={w}
        str.w r2, [r1, #0x33c]
        ldr r2, ={h}
        str.w r2, [r1, #0x340]
    done:
        pop {{r0, r1}}
        pop {{r4, pc}}
    tramp:
        push.w {{r4, r5, r6, r7, r8, lr}}
        b.w #0x{SITE + 4:08X}
        .align 2
    """
    b = asm(src, base)
    b += b'\0' * (-len(b) % 4)
    return [int.from_bytes(b[i:i + 4], 'little') for i in range(0, len(b), 4)]


def install(xoff, yoff, w, h):
    if rd(SITE)[0] != STOCK:
        raise SystemExit(f'{SITE:#x} holds {rd(SITE)[0]:#x}: not the stock push.w (already installed?)')
    n = len(stub(0xC0700000, xoff, yoff, w, h))
    base = cave.claim('viewbox', 4 * n + 16)
    words = stub(base, xoff, yoff, w, h)
    for i, x in enumerate(words):
        setw(base + 4 * i, x)
    flush()
    jump = asm(f'b.w #0x{base:08X}', SITE)
    assert len(jump) == 4
    json.dump({'base': base, 'args': [xoff, yoff, w, h]}, open(STATE, 'w'))
    setw(SITE, int.from_bytes(jump, 'little'))
    flush()
    print(f'installed: stub at {base:#x} ({len(words)} words), site {SITE:#x} -> {rd(SITE)[0]:#x}')


def remove():
    setw(SITE, STOCK)
    flush()
    print('restored', hex(rd(SITE)[0]))


if __name__ == '__main__':
    if sys.argv[1] == 'install':
        a = [int(x) for x in sys.argv[2:6]] if len(sys.argv) > 5 else [0, 0, 3856, 2170]
        install(*a)
    else:
        remove()
