# dp2 Quattro 2.03 — host-reachable surfaces (static analysis only)

Nothing here has been checked on a camera. Addresses are **loader** 2.03 for the UART terminal (it is
loader-only) and **master** 2.03 for the card files. Decompiler output via
`ghidra_scripts/DP2QDecomp.java` and `DP2QCallers.java`.

The question this answers: is there a way to **observe** camera state or **inject** data/code *without*
writing flash — the dp2 Quattro equivalent of the fp's USB shell / disposable loader card. The
flash-update path itself (persistent, brick-risky) is in [`FIRMWARE_MAP.md`](FIRMWARE_MAP.md) §2 and the
`FUN_4009c226` reader (opens `S0:\DP2QVxxx.BIN`, reads to DRAM 0x4e000000, hands to the sub-controller to
program). This file is the non-destructive surfaces.

**Status (2026-11-11):** the `Camfile.bin` apply path is now traced and ruled out as a code/injection
surface (§2), so **no non-destructive code-execution path is statically knowable** — the UART command set
(hardware RAM dump) is the only remaining lead. Consequence for a dp2q USB shell:
[`USB_SHELL_PORT.md`](USB_SHELL_PORT.md).

## 1. UART Debug Terminal (loader image only)

A real interactive serial command shell. Banner at 0x4020bc95:
`*** Welcome to  Debug  Terminal !! ***  COPYRIGHT(c) \x1b[31mSIGMA\x1b[0m` (ANSI-coloured).
Present in the **loader** build only; no banner or terminal in master.

### The REPL

| addr | role |
|---|---|
| `FUN_40009a08` | REPL (plain). Prompt `TM>`; read char, echo, handle backspace (0x08) and CR/LF (0x0d/0x0a); accumulate a 256-byte line at RAM `*0x41000024`-area buffer; on Enter call the dispatcher |
| `FUN_40009b04` | REPL (same loop, wrapped in a mutex `FUN_4019e6d8`/`_ec` on `_DAT_40009c24`); registered in the console-ops table |
| `FUN_40009468` | **dispatcher**: strip leading spaces, take first token (≤254 chars, space-delimited), walk the command table, `FUN_401b84fc` (strcmp) the token against each entry's two name pointers, call `handler(full_line)` on match |
| `FUN_400095f4` | mutex-wrapped duplicate of the dispatcher (console-ops entry) |
| `FUN_4000943c` | prints `Unsupported command.` |
| dispatcher returns | `-1` continue, `-2` → prints `Illegal command.`, `-3` → exit terminal |

**Command table** (`DAT_400095e4` → RAM **0x41000024**): array of `{char *name, char *alias, void (*handler)(char *line)}`
triples, zero-terminated (first null name ends the walk). The handler receives the whole typed line and
parses its own arguments.

### I/O path

| addr | role |
|---|---|
| `FUN_40009320` | getchar: read 1 byte from device `*0x41000020` via `FUN_4019e65c(dev,1,buf,&len)`; returns byte or 0xffffffff |
| `FUN_40009398` | putchar (used by puts `FUN_40009870`, which maps `\n`→`\r\n`) |
| `FUN_4004180e` | `UART System Started`: stores a channel number at `DAT_40041868[2]`, inits via `FUN_400417aa`, driver `dd_uart_40043400` |
| `FUN_40041736` | uart getchar via `dd_uart_40043400(channel, …)` |

The device handle (`0x41000020`) and command-table pointer (`0x41000024`) are in on-chip SRAM, in the
`0x41000000`+0x32C block the reset handler copies from image `0x40BD8348` at boot (FIRMWARE_MAP §5). The
console-ops table at `0x4003b068` (entries: `FUN_40009b04`, `FUN_40009710`, `FUN_4000977c`, `FUN_400097dc`,
`FUN_400098d4`, `FUN_400095f4`, …) is installed at kernel init `FUN_4003a4e4` → `0x4003a660`.

### How it is entered — the caveat

The REPL's main caller is `FUN_4000856c`, the **CPU exception / abort handler** (COMPUTED_CALL from the
kernel start `FUN_4003a4e4` @ `0x4003a5f0`). On an unexpected fault it prints
`Unexpected exception/interrupt occurred`, the vector number, a full register dump (R0–R15, SP, LR, PC,
CPSR with decoded N/Z/C/V flags, J/T bits, IRQ/FIQ masks, decoded processor mode: USR/FIQ/IRQ/SVC/ABT/
UND/SYS, Domain Access Control), **then drops into the `TM>` shell**.

So in the loader this is primarily a **crash / post-mortem console**: strong for *observation* (full CPU
state on any fault, interactive prompt afterwards), but no clean normal-boot entry that opens it unprompted
was found. The UART channel number and baud are board config and were not pinned statically — probe on
hardware.

### Open (blocks calling this an injection path)

- **The command table is empty in the static image and filled at runtime.** The registrar was not located
  by static xref (the table address `0x41000024` is loaded only by the dispatcher at `0x400095e4`; nothing
  else references it as a literal). Until the runtime table is recovered, the command set is unknown — so
  whether a memory-poke / call / load command exists (which is what would make the UART shell true code
  injection, not just observation) is **unresolved**. Needs a RAM dump from a running camera at
  `0x41000024`, or a deeper write-xref hunt.

## 2. Card files read-and-applied (master image)

The file-system request layer is `FUN_401319c4(op, 0, args, arglen, out)`. Opcodes identified from the
wrappers: **0xc** open (`FUN_40131ef6(name, mode, …)`), **0xd** close (`FUN_40131f60`), **0xe** read
(`FUN_40131f8c(fd, buf, size, &transferred)`), **0x11** lseek (`FUN_4013201c(fd, off, whence, …)`). Mode 0
on open = read (the file must already exist; handlers log `No file` when open < 0).

### Injection without flash: `S0:\Camfile.bin`

`FUN_4007d278` and `FUN_4007d350` (task area `0x4007dxxx`):
1. open `S0:\Camfile.bin` (mode 0),
2. read up to **0x600000 (6 MB)** into a RAM buffer (`_DAT_4007d624`),
3. size-check (`transferred <= DAT_4007d650` / `DAT_4007d6cc-4`), store the size, pad the rest with 0xFF,
4. apply downstream — `FUN_4007bc3e(2, buf)` in one path; in the other `task_STLASM::FUN_4007d1ec(buf, size,
   FUN_4007f22e(), FUN_4007f228())` then `FUN_4007d188` + a `thunk_FUN_01000118(…, 0x10000)`.

So a crafted `Camfile.bin` on the card is **read into camera state** — but the apply path is now traced
(2026-11-11, master 2.03), and it is **a persistent calibration writer, not a non-destructive data
injection and not code execution**:

```
FUN_4007d278  read ≤6 MB into *_DAT_4007d624 + 4, pad 0xFF, then FUN_4007bc3e(2, buf)
FUN_4007bc3e(mode=2, buf) → FUN_4007bb90(2,…) returns {0x400, 0x3400, 0x3000}  ← HARDCODED by the mode
                          → FUN_4007baca(0x400, 0x3400, 0x3000, buf)
FUN_4007baca  for two logical regions (0x4, 0x34): FUN_401cd3c8(idx) = logical→physical block lookup
              (DAT_401cd1a0+idx*2), then FUN_4007ba34(region, 0x3000, buf)
FUN_4007ba34  writes buf in ≤0x100-sector runs via FUN_401cb460(dev=DAT_4007bda8, blk, count, src);
              src steps by count*0x200 → 512-byte sectors on a block device (serial-flash / NAND FTL)
```

The card controls **only the payload bytes**; the destination (two fixed 0x3000-byte regions at logical
blocks 0x4 / 0x34 — the `CamCal.bin` / `CamSys.bin` calibration areas) is firmware-hardcoded by the mode
constant `2`. **Nothing from the card becomes an address, a length, or a branch target.** The STLASM variant
(`FUN_4007d350` → `task_STLASM::FUN_4007d1ec` → `FUN_40134f9e`) only sets a "camfile present" flag and
builds queue objects — again no buffer byte reaches an address. So this surface: (a) cannot run ARM code,
and (b) writes **persistent** block storage, so it is not even the non-destructive surface it first looked
like. **Removed from the injection-candidate list.** (Decompiled sources cached at
`out_dp2q/ghidra/decomp/camfile_{apply,consume,writer}.c`.) What triggers it (a service/debug menu item vs.
automatic) is still not traced, but is moot for code injection. Full write-up and the USB-shell-port
implications: [`USB_SHELL_PORT.md`](USB_SHELL_PORT.md).

### Observation only (camera writes these; inputs they are not)

`S0:\Debug\AFLOG\%03d_%04…`, `Debug\MeasureLog.txt`, `Debug\PST.txt`, `Debug\%02d.txt`, `Debug\BIG.bin`,
and the `Debug\FirmData.bin` / `Debug\SystemData.bin` / `Debug\AdjustData.bin` dumps. These confirm an
engineering/service build writes diagnostics to the card, but they are outputs.

(For reference, other fixed `S0:\` paths are error-capture RAW dumps `LVERR…`, `PRORAW_*.bin`, the
sub-controller image `C81Sub.bin`, and the main-image name `C81FRM.bin` — see the updater in FIRMWARE_MAP
§2 / §6.)

## Bottom line

- **Observation:** the UART crash console gives full CPU + memory state over serial on any fault, live.
  Lowest-risk, highest-confidence surface.
- **Injection without flash:** `S0:\Camfile.bin` is **now traced and ruled out** — it is a persistent
  calibration writer with a firmware-fixed destination, not code execution and not even volatile (above).
  **No non-destructive code-execution path remains statically knowable.**
- **UART shell as code injection:** only if its runtime command set includes poke/call — unproven, and the
  registrar is **not statically recoverable** (nothing references the command table at `0x41000024` but the
  dispatcher), so confirming it needs a RAM dump from a running camera.

### Next steps (in order)

1. ~~Trace the Camfile apply path~~ — **done** (2026-11-11): persistent calibration writer, ruled out as an
   injection/code surface. See the Camfile section above.
2. Recover the UART command registration (RAM dump of `0x41000024` on a running camera — the static
   write-xref hunt is exhausted) to learn whether poke/call commands exist. This is now the only remaining
   lead for a non-flash code-execution path.
3. Pin the UART channel/baud and whether any non-crash path opens the terminal — needs hardware.
