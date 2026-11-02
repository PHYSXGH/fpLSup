# fp L test cards

Built with `FPSUP_CAMERA=fpl` from the working tree on 2026-11-02. Not booted yet.
Each card is three things in the SD card root: `AutoRun.txt`, `fpSup.BIN`, `FPSUPUI/`.

| card | what it is | AutoRun.txt sha256 | fpSup.BIN sha256 |
|---|---|---|---|
| `20261102-shell-only` | loader + USB shell, no hooks | `d34cb867…2fd9160` | `5d72ea0b…6487f32` |
| `20261102-gyro-base-debug` | gyro Base edition + USB shell, no lens .json | `d34cb867…2fd9160` | `3eec3b40…6a7f32c`¹ |

¹ full: `3eec3b4031a16307ffbdd38b51c7a4b22640aa1ebc1b37d34003c5a06ed6531c`.
Checksums are for traceability only; nothing on the camera checks them.

Build:

```
cd fpSup
FPSUP_CAMERA=fpl python3 -B fp_usb_shell/build_autorun.py --loader --banner 'fpSup-fpl-Shell-dev!' --out OUT/AutoRun.txt
FPSUP_CAMERA=fpl python3 -B gyro/build_base_card.py --edition base --debug --out OUT
```

Offline checks that passed:

- `card_check.py`: compared word by word with the fp card built from the same sources and options (for the
  gyro card, the fp one built with `--no-lens-json`). Every difference is an address the table explains, no
  address-like word was left untranslated, and every firmware word the card overwrites has the same stock
  value on both cameras. A mutation (one Python address left unwrapped) is caught.
- `FPSUP_CAMERA=fpl test_loader_hook.PlainCardRestoreTests`: the real loader and stage2 under unicorn
  against the fp L image. The file loads, the entry gets its ABI, and power-off restores every journaled word
  to the fp L's stock value. Run against the fp image instead, it fails (mutation).

Not yet known: anything on the camera.

## On the camera, in order

1. Shell-only card. Expect the four-box progress screen, then the banner `fpSup-fpl-Shell-dev!`.
   If it freezes: card out, battery out, and the camera is stock (nothing is written to flash).
2. Plug in USB. Read the ID: the fp is 1003:c432; the fp L is 1003:c441 (read 2026-11-02; `fpshd --pid 0xc441`).
3. Over the shell, read the `verify` rows of `fpSup/fp_usb_shell/cameras/fpl302.tsv` live.
4. Gyro debug card: boot, record a short CinemaDNG take, look for `A001_xxx.GYR` in the root of the disk the take went to.
   Then the hook check from SUP_BUILD_RULES §6: boot, don't record, power off, about ten times.

## Camera results

- 2026-11-02, `20261102-gyro-base-debug` (fpSup.BIN `3eec3b40…`), fp L Ver.3.02, reported by the user:
  it boots with the four-box screen and a recorded take produced a `.GYR` file. The shell-only card was skipped.
  Not yet checked: what's in the log, the USB shell, the `verify` rows, the ten-cycle power-off test.
- 2026-11-02, the same card: `A001_096.GYR`, 61,980 bytes, a 3.04 s take (the battery died during it).
  Decoded with the browser converter's 20-byte header layout (`gyr7.py` reads only the older 64-byte v7
  header, and that's true on the fp too):
  7,745 records, none damaged or with a bad tag, no trailing bytes; 7,601 gyro samples and 144 accelerometer readings (~47 Hz, one every 51–70
  gyro samples). Accelerometer magnitude 0.996 g (sd 0.003): same chip, same scale. Gyro live: noise
  0.02–0.07 dps, 0.17% repeated samples, at rest throughout, so its scale is not tested yet. The sample period in the
  header is the build constant, not a measurement. Still to do: a take with a known rotation to check the gyro scale and axes.
- 2026-11-02, the same card: `A001_097.GYR` and `A001_098.GYR`, each a 4.8 s take turned about the lens axis
  between still periods, on purpose ~78° (097) and 90° (098). The accelerometer's tilt agrees: 77.5° and 89.6°.
  The gyro z integral, at the header scale, gives 84.2° and 92.2°. 098 is the clean one: 2.4% over its 90°,
  which is within what a hand-held turn gives. 097 had more off-axis motion (about 19° on x and 27° on y). The
  header gscale is rad/s per count (0.0079 dps), which is how Gyroflow reads a gcsv; the source comment said
  dps and is corrected (comment only, the fp build is unchanged). Same gyro and range as the fp; peak 32,019
  counts (~253 dps) in 097, close to full scale.
- 2026-11-02, the same card: the SUP_BUILD_RULES §6 hook check. Ten cycles of power on with the card in, no
  recording, power off. All ten boots were clean (reported by the user).

## USB shell on the fp L (2026-11-02): not working yet

Same card (`gyro-base-debug`). In PTP mode the camera is `1003:c442` (mass storage: `c441`), and the interface is
vendor class ff/ff, so the IFACE patch landed. `fpshd --pid 0xc442`:

- `ping` round trips work: right sequence number, frame CRC checks out.
- Every data-carrying reply is empty: `shl help` / `shl mem get` return no text, `MCAPS` says "unsupported"
  (n != 112), `display text` + `display osd 1` showed nothing, and `mem save \WSTATE.BIN` wrote no file.
- Offline: the four shell functions are identical on both cameras; SHELL_CTX 0xC3756904 -> 0xC3757744
  agrees at all 15 firmware references. `test_worker_mem` + `test_worker_upload` (made camera-aware) pass
  24/24 against the fp L image, including MCAPS. Suspect: the reply/data path on the real controller, which
  emulation doesn't model. Not determined.
- Then the endpoint wedged (`frame0 LIBUSB_ERROR_IO`) after stray daemons, my mistake, competed for the
  interface (`pkill -f` matched its own shell and left the old daemon running; use `kill` by PID), and the camera
  froze. Recovered with a battery pull. Nothing persistent was written.

Next time: one daemon, started once; check `pgrep -a fpshd` before every session.

### Cause found (2026-11-02): the fp L has 2 GB and no uncached mirror

FUN_c001ed2c (identical code) registers RAM up to 0x80000000 on the fp and up to 0xC0000000 on the fp L.
The worker read and wrote its frames through the fp's uncached mirror (address + 0x40000000). On the fp L
that range is the second gigabyte of ordinary RAM, so the worker never saw a command, and the controller
sent the host's own frame back. That is the "echo" seen as `OK shl help`, as an empty MCAPS reply, and as a
ping that seemed to work. Every command also wrote a few bytes into unrelated memory, the likely cause of
the freeze.

Fix: `FPSUP_NO_UNCACHED_ALIAS`, which every fp L assembly gets (`fwtarget.memory()` / `asm_defines()`).
The worker uses the cached address and flushes the D-cache (0xC000E91C) after clearing the frame, when a
command arrives, and before every IN transfer. The bus address (cached − 0x40000000) is unchanged. The fp
build is byte-identical.

Emulation: the worker tests now have a per-camera memory model. Under the fp L model the old worker fails
(`test_a_command_is_read_where_the_dma_put_it`: empty MCAPS, as on the camera); the fixed one passes
26/26 (fp 25 + 1 skipped). `test_no_mirror_every_transfer_follows_a_flush` fails when one flush is removed.

Cards `-r2` (AutoRun.txt unchanged, `d34cb867…`; only fpSup.BIN changes):

| card | fpSup.BIN sha256 |
|---|---|
| `20261102-gyro-base-debug-r2` | `e86a7775057833914eee516f73c9c8f964c1fdd6e7e16b6322c455d661050d8f` |
| `20261102-shell-only-r2` | `1c8749130a07cb96c33591b86121893d3e71366e0939291c04bd187ad029dbfc` |

card_check passes against fp references built with `FPSUP_REF_NO_ALIAS=1`.

Still to look at: host-side sanity checks expect pool blocks below 0x50000000 (`putfile.py`, `gyro/*_deploy.py`,
`mpool*.py`), and the worker's MEM1 windows stop at DMA_HI 0x80000000. On the fp L a block in the second
gigabyte would be refused (safe, but unusable).

### r2 on the camera (2026-11-02): the USB shell works

`20261102-gyro-base-debug-r2`, one daemon (`fpshd --pid 0xc442`):
`ping` ok; `MCAPS` → `OKMC`, worker pool 0x45319B80 (1 MiB), no windows; `help` lists the fp L's shell commands.
Read live: the echo slot is back to stock (0xC03D9BB8); hooks armed: rec start / rec stop / accel = `bl` to
cave 0xC072BAEC / BAF4 / BAE4; mode hook stock (Base doesn't arm it); gyro pool 0x4541AA00; worker `VSHL`.
`verify` rows confirmed: PATH_MGR_SD (take counter 99 after A001_098), OUT_BUSY (1), AR_TABLE (holds the
interpreter's own functions). XC_CommonSaveData / STORE stay `verify` (Fast Start only, still off).
Not yet done with r2: a recorded take (the `.GYR` path is unchanged code, but the BIN is new).

### r2 froze the camera in live view: whole-cache flush with interrupts off (2026-11-02)

About half a minute after the last command, idle in live view, the camera froze with r2. r2 called F_DCACHE
(0xC000E91C) on every round. That routine masks IRQ and FIQ and walks the whole of L1 and L2 by set/way,
and the idle loop re-arms several times a second. **Do not use r2.**

r3: `DSYNC_RANGE` cleans and invalidates by address (DCCIMVAC, 32-byte steps, to the point of coherency)
only the buffer a transfer uses: the 16 KiB OUT buffer in arm_out and at got_command, the 64-byte frame in
arm_in, and the block in arm_in_block. Interrupts stay on, and F_DCACHE runs only when the host asks for
OPT_SYNC. The fp build is byte-identical.
Tests (fp L model): every StartTransfer's whole buffer is flushed by address since the previous one; the
idle round (arm_out) never calls F_DCACHE. Each fails when its flush is removed or F_DCACHE is put back.

| card | fpSup.BIN sha256 |
|---|---|
| `20261102-gyro-base-debug-r3` | `ee7ec0b8d4749f02dc94616e2a4cc04a6830454b8a69070ea78c8a1cb6280a82` |

Not proven: that r3 doesn't freeze. Emulation can't model interrupt latency; only time on the camera shows it.

### r3 froze too, with nothing sent from the host (2026-11-02)

Booted 15:48, connected in PTP, no daemon, live view. It froze within the 5 minutes. So the freeze comes
from what the card does by itself while USB is connected, not from host commands, and not only from the
whole-cache flush. Ruled out: the USB controller base. All 91 refs to 0x2100Cxxx (DALEPENA included) are
identical in both images.

Bisection, 5 min idle on live view in PTP each, no daemon:

| test | card | fpSup.BIN sha256 | contains |
|---|---|---|---|
| A | none (stock) | — | nothing |
| B | `20261102-B-gyro-noshell` | `8bfed6e2…a8d875a9` | loader + gyro; no worker, no interface patch |
| C | `20261102-C-shell-only-r3` | `44ee9958…7e856b97` | loader + worker (r3) + interface patch; no gyro |

All use AutoRun.txt `d34cb867…`.

**Correction:** the r3 freeze above came after the r2 freeze **with no battery pull in between** (a warm
restart: the patched words of a frozen session are never written back, and RAM that r1/r2 had written in the
second gigabyte isn't necessarily cleared). That r3 result is unreliable. A later r3 run lasted 5 minutes
without a freeze (USB connection during it unconfirmed). Rule from now on: battery out before every camera test.

**Decision (user, 2026-11-02): r3 is taken as working.** Evidence: the shell's reads were correct, and r3 ran
5 minutes without a freeze. Its only freeze followed an r2 freeze with no battery pull. Not done: a 10-minute
idle in PTP after a battery pull. If a freeze shows up, start from the bisection cards B and C above.

Card status:
- `20261102-gyro-base-debug-r3`: current debug card (gyro + USB shell).
- `20261102-B-gyro-noshell`: gyro without the shell or the USB patch, the card for normal shooting.
- `20261102-gyro-base-debug` (r1): the worker writes into the wrong memory once USB is in PTP. Shooting only, no PTP.
- `*-r2-DO-NOT-USE`: whole-cache flush with interrupts off.

### r4: memory limits from the camera's RAM (2026-11-02)

The worker's MEM1 window limit DMA_HI is the camera's top of RAM (`FPSUP_RAM_TOP`, fp L 0xC0000000; fp
unchanged at 0x80000000). The host pool checks use `fwtarget.is_pool()`: fp unchanged (< 0x50000000), fp L the
whole 2 GB. putfile's MEM1 fast path ends at `fwtarget.ram_top()`. r3→r4 is one instruction (cmp #DMA_HI).
The fp is byte-identical; all fp shell and gyro tests give the same results; the window test is camera-aware
and fails on the fp L without the new limit.

| card | fpSup.BIN sha256 |
|---|---|
| `20261102-gyro-base-debug-r4` | `c99d2afb1e3f87a8e234be12c418db2570d5ce2c3dcaafd5d1d98757b50770d7` |

On the camera (battery pulled first): no reply until the USB cable was unplugged and replugged once (as the
shell README says), then ping ok; MCAPS pool 0x45319B80; is_pool ok; MEM1 read of the worker frame returns
the `FPSH` header; read-only window at 0x90000000 GRANTED, 256 B read (`0000ffff…`), revoked; windows empty;
ping ok after.

### Fast Start settings block (2026-11-02): checked, persistence not yet tested

- Static: the save routine fp 0xC0022548 → fp L 0xC0022468 is identical (type id 9, size 0x410, no checksum).
  The surrounding settings code fp 0xC0020860..0xC0025778 differs only by relocations: 709 of 5,062 words,
  435 branches and 274 movw/movt address halves, no constant or offset changed.
- Live (r4, read only): XC_CommonSaveData at 0xC30751FC, 260 words. +0x28..+0x200, the loader's region, is
  all zero; 39 non-zero words (fp 42) at +0x10..+0x20 (timestamps at +0x18/+0x1C as on the fp),
  +0x280..+0x28C and +0x380..+0x40C, i.e. exactly the gaps between the fp's measured safe ranges.
  Backup: `projects/fpl-port/private/commonsave_fpl_20261102.json` (not committed).
- Not done: the fp's persistence measurement (write a pattern into +0x28..+0x200, power cycle with the switch,
  read it back, restore). Until then `--store-boot` / `--loader-hook` stay refused on the fp L.

### Fast Start settings block: persistence confirmed (2026-11-02)

`projects/fpl-port/tools/commonsave_probe.py`, r4 card, one daemon at a time:
1. check: +0x28..+0x200 (118 words) all zero.
2. arm: 0xA5000000|offset written into all 118 words, each read back.
3. Power switch off/on: all 118 markers back at their own offsets, none cleared or moved. The block is inside
   the range boot clears (0xC3000000..0xC38D6A70), so they came from flash. Outside the region only +0x1C
   (the save time) changed.
4. restore: the region written back to zero from the backup, read back.
5. Power switch off/on: all 118 words zero. The camera is as it was.

XC_CommonSaveData and STORE are `camera` rows. Still refused on the fp L: `--store-boot` / `--loader-hook`.
The block is confirmed, but the Fast Start loader hook (site 0xC03DA420, the AutoRun abort) has not run under
emulation or on the fp L.

Open issue (USB shell on the fp L): after some idle time, or after the daemon is restarted, the worker
sometimes stops answering until the USB cable is replugged. Seen 3 times; replugging fixed it every time.
Once the camera did not enumerate at all after a power cycle until the cable was replugged.

### Fast Start 3 / loader hook on the fp L: emulated, test card built (2026-11-02)

- Hook site fp 0xC03DA420 → fp L 0xC03DA638: the same `bl` to the AutoRun starter (0xC03DA970), stock word
  0xEB0000CC on both. The `\AutoRun.txt` string the firmware passes in r0 is at 0xC0BD2024 (`checked`).
- `test_loader_hook` runs all 16 tests against the fp L image (warm hook, cold AutoRun, missing file,
  foreign loader, abort, store seeding, power-off write-back). 7 of the 14 hook tests fail when the fp L build
  is run against the fp image instead.
- `FPSUP_FPL_FASTSTART_TEST=1` is the only way past the fp L refusal; the test sets it for itself.
- card_check knows two derived values: the hook branch (fp `eb0d4e90`, fp L `eb0d44aa`, each to its own
  loader+4) and the store magic (sha256 of each AutoRun's loader words: fp `5c502aa9`, fp L `5665eb93`).
- `loader_hook_check.py` is camera-aware (fp L site, marker 0xC072BAC0, image `out_fpl/`).

| card | AutoRun.txt | fpSup.BIN |
|---|---|---|
| `20261102-fast3-gyro-debug-TEST` (store-boot, loader-hook, four-box, mark 0xC072BAC0) | `1bfd1c39…` | `8fc095e5…` |
| `20261102-fpl-recovery-noBIN` (AutoRun only: puts 0xEB0000CC back at 0xC03DA638) | `9356acb1…` | none |

Note: unlike every card before it, the Fast Start card **writes the loader into the settings block** on its
first boot (STORE = 0xC3075224, magic first). Removing the card does not clear that. To undo: the recovery card
(hook back to stock), then `commonsave_probe.py restore` (store region to zero).

### Fast Start test card on the camera (2026-11-02)

1. First boot (slow path, battery pulled before): the user saw a normal boot. **USB never connected** (no
   kernel event, port "not attached"), with two cables and two ports.
   Without the card the camera connected at once (1-1.2, class 06).
2. Cold start (battery out, card in → fast path): USB connected (1-1.2, class ff). Read:
   store magic 0x5665eb93 (= this build), loader words follow; hook 0xC03DA638 armed → loader+4 (0xEB0D44AA);
   loader+4 = hook entry; journal 6 entries, all = fp L stock words; runs=0 (image reloaded);
   LOAD_DONE_US 2.54 s (the fp skill lists ~11–12 s for this path; not understood yet).
Open: why USB did not come up after the first (slow, provisioning) boot.
3. Warm restart (power switch, USB unplugged → instant path): the boxes appeared already filled (user).
   LOAD_DONE_US 1.15 s; store magic intact; hook armed. The power-off run count was not read yet: the shell
   went silent when the daemon was restarted within the same USB connection.
   `loader_hook_check.py` now reads through its retrying `read()` (a lost reply had crashed it).

Shell silence, refined: every time it happened, the daemon had been restarted while the cable stayed
plugged in. The first daemon after a fresh plug-in has always answered. Workaround: replug after restarting
the daemon. Likely cause: stopping the daemon mid-session leaves the camera's endpoint in a state the worker
doesn't recover from. Not fixed.
4. After a replug (no restart), one daemon: `loader_hook_check.py` (now retrying every read): hook armed,
   loader+4 = hook entry, **power-off routine runs=1** (at 103.4 s of the previous boot = the warm restart),
   journal **7 entries, all = fp L stock words**.

All three paths work on the fp L: slow (stores the loader), fast 2.54 s, instant 1.15 s, and the power-off
write-back runs. Fast Start stays refused for normal fp L builds until the open issue is understood:
**USB did not connect after the first (slow, provisioning) boot**.
