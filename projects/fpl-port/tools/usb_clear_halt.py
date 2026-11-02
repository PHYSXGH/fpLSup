"""Send CLEAR_FEATURE(ENDPOINT_HALT) to the shell's bulk endpoints (0x01 OUT, 0x82 IN).

A standard USB request: both the host controller and the camera reset that
endpoint's data toggle / sequence number.  Used to test whether the shell's
silence after a second daemon is a toggle/sequence mismatch (2026-11-02).
Run with no daemon holding the interface.

    usb_clear_halt.py [--pid 0xc442]
"""
import sys
import usb.core
import usb.util

pid = int(sys.argv[sys.argv.index('--pid') + 1], 0) if '--pid' in sys.argv else 0xC442
dev = usb.core.find(idVendor=0x1003, idProduct=pid)
if dev is None:
    raise SystemExit(f'1003:{pid:04x} not found')
try:
    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
except (NotImplementedError, usb.core.USBError):
    pass
usb.util.claim_interface(dev, 0)
for ep in (0x01, 0x82):
    try:
        dev.clear_halt(ep)
        print(f'clear_halt 0x{ep:02x}: ok')
    except usb.core.USBError as e:
        print(f'clear_halt 0x{ep:02x}: {e}')
usb.util.release_interface(dev, 0)
usb.util.dispose_resources(dev)
