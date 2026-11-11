# dp2 Quattro — porting the fp USB shell (feasibility and gap map)

Static analysis only; nothing here has been checked on a camera. Addresses are **master** 2.03 unless
marked **loader**. Companion notes: [`DEBUG_SURFACES.md`](DEBUG_SURFACES.md) (the non-destructive
host-reachable surfaces) and [`FIRMWARE_MAP.md`](FIRMWARE_MAP.md) (boot path, task table, memory map).

The question: can the fp's USB shell (`fpSup/fp_usb_shell/`) be made to work on the dp2 Quattro? **Not as a
port.** Different SoC (Milbeaut M7 / Cortex-A9 vs. the fp), different firmware, different addresses — every
offset and the worker binary are fp-specific. What can transfer is the *architecture*. This note maps each
pillar of that architecture to its dp2q equivalent (found or missing) so the work has a spine.

## What the fp shell actually is (the three pillars)

From `fpSup/fp_usb_shell/README.md` and the `fp-usb-shell` skill. The shell is not one thing; it is three
independent capabilities stacked:

1. **A USB device-mode transport.** The fp already exposes a PTP gadget. The shell changes *seven words*
   of descriptor to repurpose PTP's endpoints into three bulk pipes (EP 0x01 OUT, 0x82 IN, 0x83 IN) — the
   firmware still owns and re-creates them, so recording no longer tears the channel down. No new USB stack
   is written; an existing one is bent.
2. **A way to run our own ARM code without flashing.** The fp's disposable **AutoRun loader card** writes
   the seven descriptor patches *and* a resident worker into RAM at boot. The power switch is a warm
   restart that keeps firmware in memory, so a loader hook re-applies every patched word on power-off.
   Nothing is flashed; pull the card and stock firmware is back.
3. **A command surface the host can drive.** `shl <line>` hands a line to the firmware's *own* shell and
   returns what it printed; `mem set/save`, file transfer, and the resident-code swap are built on that
   plus the worker.

A dp2q shell needs an equivalent of **all three**. Pillar 2 is the wall.

## Pillar-by-pillar map

### Pillar 1 — USB device-mode transport: ✅ a real target exists

The dp2q firmware carries a full PTP device stack, the direct analog of the fp's PTP gadget:

| evidence | where |
|---|---|
| Tasks `PTP_CAM` (pri 36), `USB_PTP` + `USB_CTL` (pri 42), `STORAGE` | task table + `USBLLD`/`USB` event flags, FIRMWARE_MAP §4 |
| `task_PTP_CAM` bodies | `FUN_4005d4d0`, `FUN_4005d52e`, `FUN_4005d53a`, `FUN_4005d586` |
| `task_USB_CTL` entry | `FUN_4005c6ec` |
| PTP command handlers (`USBPtpCmd_OpenSession`, `GetDeviceInfo`) | `task_USB_PTP` cluster `0x4006c80a`..`0x40074218` (see `funcs_master.tsv`) |
| Milbeaut USB device controller | strings `<<MWUSB4>>`, `[USB Driver] Register value at 0xC300061C`, `USBLLD`; MMIO at `0xC300_xxxx` |
| Mode select / menu | `Ui_USB_Start_Menu`, `USB Mode`, "Mass Storage", `Now Connecting...` (msg id 535) |

So the transport pillar is *plausible*: there is a PTP endpoint set and an MWUSB device controller to
repurpose, exactly like the fp. **Not yet done** — the descriptor table, the `wMaxPacketSize` normaliser,
and the `DALEPENA`-equivalent "endpoints now exist" gate all have to be found in MWUSB before a patch of
"N words" can be written. This is tractable static work (see Next steps).

### Pillar 2 — run our own code without flashing: ❌ the hard blocker

This is what the fp's AutoRun loader card provides and the dp2q has **no proven equivalent of**. Per
[`DEBUG_SURFACES.md`](DEBUG_SURFACES.md), the dp2q's non-destructive surfaces are:

- **`S0:\Camfile.bin` read-and-apply** (`FUN_4007d278` / `FUN_4007d350`): **traced end to end — it is a
  persistent calibration writer, not code execution.** See below.
- **UART Debug Terminal** (loader image only): a real REPL, but entered through the **crash/abort handler**
  (`FUN_4000856c`), and its runtime command table at `0x41000024` is empty in the static image — whether a
  poke/call command exists is unknown. Nothing references `0x41000024` as a literal except the dispatcher,
  so the registrar is **not statically recoverable**; resolving it needs a RAM dump from a running camera.
  Not reachable over USB regardless.
- The flash updater (`FUN_4009c226`, reads `S0:\DP2QVxxx.BIN` → DRAM `0x4e000000` → sub-controller
  programs flash) is persistent and brick-risky — the opposite of what the shell is for.

Without a non-destructive code-execution path there is nowhere to install descriptor patches or a worker,
so pillars 1 and 3 have no host.

#### Camfile.bin apply — traced (master 2.03, 2026-11-11)

Decompiled the whole chain (`ghidra_scripts/DP2QDecomp.java`; cache in `out_dp2q/ghidra/decomp/camfile_*.c`):

```
FUN_4007d278  open S0:\Camfile.bin, read ≤0x600000 into *_DAT_4007d624 + 4, pad with 0xFF,
              store size, then FUN_4007bc3e(2, buf)
FUN_4007bc3e(mode=2, buf)
  → FUN_4007bb90(2, &a,&b,&c)   a,b,c = { 0x400, 0x3400, 0x3000 }  ← HARDCODED by mode, not from the card
  → FUN_4007baca(a=0x400, b=0x3400, c=0x3000, buf)
FUN_4007baca   for each of two logical regions (a>>8, b>>8): FUN_401cd3c8(idx) looks up a logical→physical
               block in a translation table (DAT_401cd1a0+idx*2), then FUN_4007ba34(region, len=0x3000, buf)
FUN_4007ba34   writes buf in ≤0x100-sector runs via FUN_401cb460(dev=DAT_4007bda8, blk, count, src);
               src advances by count*0x200 → 512-byte sectors on a block device (serial-flash/NAND FTL)
```

The STLASM variant (`FUN_4007d350` → `task_STLASM::FUN_4007d1ec`) only sets a "camfile present" flag
(`FUN_40134f9e` builds queue objects; no buffer bytes become an address).

**Verdict:** the card controls only the *payload bytes*. The destination (logical blocks 0x4 and 0x34, two
0x3000-byte regions) is **fixed in firmware**, selected by the constant mode `2` — nothing parsed from the
card becomes an address, a length, or a branch target. So this is a **persistent calibration-data writer**
(the `CamCal.bin`/`CamSys.bin` regions), block-remapped through an FTL. It is **neither code execution nor
volatile** — strictly worse than hoped for a shell bootstrap: you cannot run ARM code through it, and what
it *does* write is persistent. Remove it from the injection candidate list.

**Net: no non-destructive code-execution path exists in what is statically knowable.** Camfile is data +
persistent; the UART poke/call surface is unrecoverable without hardware; the only code path is the
brick-risky flash updater. Pillar 2 is therefore **not demonstrated feasible** — and it is the foundation,
so as of today a dp2q USB shell on the fp model is **not feasible**. What could still change this (all need
the camera in hand): a RAM dump that reveals a UART memory/call command; an engineering/service build with
a card-code hook; or accepting a one-time flash of a minimal loader (persistent, brick-risky — a different
risk class from the fp's disposable card, and off the table while there is no dp2q to recover a brick on).

### Pillar 3 — a command surface to drive: ❌ missing / unproven

The fp `shl` drives the firmware's own shell. On the dp2q the only interactive shell found is the UART
Debug Terminal — **loader-only, crash-entered, command table unrecovered** (DEBUG_SURFACES §1). It is not
reachable over USB and may have no memory/call commands at all. So even with pillars 1+2 solved, there is
no ready-made command interpreter to expose; a dp2q shell would likely have to ship its *own* tiny command
loop in the worker (the fp worker already contains command handling — `UP01`, `mem`, file routines — so
this is less of a blocker than it looks, *if* pillar 2 gives us somewhere to run it).

## Summary table

| pillar | fp mechanism | dp2q equivalent | status |
|---|---|---|---|
| 1. Transport | 7-word patch of PTP descriptors → 3 bulk pipes | PTP stack + MWUSB4 controller (`PTP_CAM`/`USB_PTP`, `0xC300_xxxx`) | ✅ target exists; descriptor table + EP gate not yet found |
| 2. Run our code, no flash | AutoRun loader card + power-off write-back | none; `Camfile.bin` **traced = persistent calibration writer** (not code), UART crash-only + registrar unrecoverable | ❌ **blocker, no path found** |
| 3. Command surface | `shl` → firmware's own shell | UART terminal is loader-only/crash-only; worker could carry its own loop | ❌ needs pillar 2 first |

## Testability

Everything above is static. The fp shell was built through heavy on-camera iteration (three boots failed on
endpoint-enable timing alone; "judge from a clean boot" is a hard-won rule). A dp2q shell cannot be
*developed* that way without a dp2 Quattro in hand. Treat this note as a paper design until hardware and a
proven pillar-2 path both exist.

## Next steps (in dependency order)

1. **Pillar 2 (the gate) — Camfile path is now closed** (traced above: data-only, persistent, fixed
   destination). The remaining pillar-2 leads all need the camera: (a) dump RAM at `0x41000024` on a running
   loader build to recover the UART command table and check for a memory/call command; (b) look for an
   engineering/service build with a card-code hook; (c) decide whether a one-time flash of a minimal loader
   is acceptable (persistent, brick-risky). Until one of these lands, pillars 1 and 3 have no host — do not
   invest in them first.
2. **Map the PTP transport** (parallel-safe static work): find the configuration/endpoint descriptor table
   the PTP task emits, the per-speed `wMaxPacketSize` normaliser, and the MWUSB "endpoints enabled" status
   register (the `DALEPENA` analog) so a minimal "repurpose EP for a bulk IN/OUT" patch can be specified.
   Start from `task_USB_PTP` `0x4006c80a`..`0x40074218` and the `<<MWUSB4>>` / `0xC300061C` driver.
3. **Recover the UART command table** (`0x41000024`) — needs a RAM dump from a running camera or a deeper
   write-xref hunt — to learn whether a poke/call surface exists that could bootstrap pillar 2 instead.
4. Only once 1 is solved: design the worker's own command loop (reuse the fp worker's command set as the
   model) and the host daemon transport over the PTP bulk pipes.
