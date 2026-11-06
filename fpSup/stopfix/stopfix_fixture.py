"""Independent offline fixture for the reviewed Loader v3 stop-queue patch."""
import hashlib
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'fp_usb_shell/v3'))
import build_v3 as B

SITE, STOCK, PATCH = 0xC0377118, 0xE92D4030, 0xEA000160
SHA256 = 'f9f26a092c5676ead5771ba8be4aac9c3734e9ed0cd144002a73b3f6b657c9d9'


TARGET = 0xC03776A0                    # the native reference-counted release PATCH branches to


def stopfix_sup():
    """Shared patch builder only.  The fp: assert identity with the original 316-byte BIN.
    Another camera (FPSUP_CAMERA, fwtarget): the same patch at its addresses -- the site must hold
    the same stock word, and the branch goes to its own mapped release (fp L: projects/fpl-port/
    LOSSLESS_PORT.md, the two functions compared instruction by instruction)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'fp_usb_shell'))
    import fwtarget
    if fwtarget.target() == 'fp':
        data = B.patch_sup('STFX', [(SITE, struct.pack('<I', PATCH), 2)])
        assert len(data) == 316 and hashlib.sha256(data).hexdigest() == SHA256
        return data
    site, target = fwtarget.fw(SITE), fwtarget.fw(TARGET)
    image = (Path(__file__).resolve().parents[2] / f'out_{fwtarget.target()}' / 'MAIN_c0000000.bin').read_bytes()
    stock, = struct.unpack_from('<I', image, site - 0xC0000000)
    assert stock == STOCK, f'0x{site:08X} holds 0x{stock:08X}, not the stock 0x{STOCK:08X}'
    patch = 0xEA000000 | (((target - (site + 8)) >> 2) & 0xFFFFFF)
    data = B.patch_sup('STFX', [(site, struct.pack('<I', patch), 2)])
    assert len(data) == 316
    return data
