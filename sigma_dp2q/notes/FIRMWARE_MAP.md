# dp2 Quattro 2.03 — firmware map (static analysis only)

Source: `firmware/DP2QV203.BIN` (sha256 a3b88ed4…9713), unpacked with `tools/unpack_dp2q.py` into `out_dp2q/`.
Nothing here has been checked on a camera. Addresses are for **master** 2.03 unless stated.

## 1. Platform

| | |
|---|---|
| SoC | Socionext Milbeaut **M7** (source tree `C:/work/C8x_Local/C81/M7_*/Project/RD_M7/`; C81 = the camera project) |
| CPU | ARM **Cortex-A9** (`DeviceDriver/ARM/Core/CA9/dd_ca9_gic.c`, `_gtmr`, `_tmr`, `_wdog`); "CPU Number" in the abort dump suggests SMP |
| Code | mostly **Thumb-2** (~16k `push {…,lr}` vs ~1k ARM `bx lr`); OS stubs and the kernel are ARM |
| OS | **T-Kernel 1.x** (`T-Kernel/OS`, `T-Kernel/DS` SWI strings, standard function codes, see §3) |
| Driver/ISP layer | Milbeaut `M7_API`: `dd_*` peripherals (adc, audio_if, csio, hdmac0/1, i2c, pwm, tmr32, uart, udc, xdma) and `im_*` image macros (pro, b2y + iridix_wdr, dcc, iza, jpeg, jpegxr, spr, tmi, xch) |
| Formats | X3F (`lib_X3F`, "Created by AhoyOS lib_X3F"), DNG, JPEG, MJPEG/AVI |
| Third party | DigitalOptics / FotoNation (face detection) |

Different from the fp (XZ01, Cortex-A7 class, IAR, Lua): no shared code base. The fp tools and addresses do not apply.

## 2. The update file

See the docstring of `tools/unpack_dp2q.py`. Three chunks: two Cortex-A9 images (`SIGMA_FWb`, `SIGMA_FWc`),
both loading at 0x40000000, and a 128 KB chunk for a sub-controller.

### Loader vs master

The names come from the source paths each image was built from (`M7_Loader`, `M7_Master`). The "loader" is
**not** a small boot stage: both images are complete camera firmware.

- same size class (code used: loader 0xC37E14, master 0xC47FF0); 85 % of 32-byte windows of master occur in loader
- same 50 tasks with identical names, priorities and stack sizes (only entry addresses move; `tools/task_table.py`)
- loader only: a "Welcome to Debug Terminal" banner, a `%s %s ver%d.%d.%d.%04X` banner, a build stamp
  `Apr 20 2020 21:29:45`, coloured log-level formats (`:taskid:mode: This is error message.` …)
- master only: a few file-numbering / DPOF messages

Function-level comparison (Ghidra, `tools/compare_images.py`, 2026-11-05): of 16,338 master / 16,387 loader
functions, 11,946 match one-to-one (by name, masked bytes, or instruction sequence). Most of the rest are
too short to fingerprint, in the RAM block, or ambiguous (identical code present several times). Only
~790 functions per side (~230–250 KB) have no identical code on the other side; they are spread over the
whole code area, and of the 320 that pair up by position, 259 are ≥ 80 % instruction-identical with a median
size change of 0. So the two are **the same code base built twice with scattered small differences**, not
a boot stage plus an application. Named functions present only in master: file delete/protect and DPOF
"select all / cancel all" jobs (`System_Func_FileDelete_*_Exe`, `system_func_file*_select_update_job`,
`System_Func_DPOF_SelectAll_Exe`, `System_Func_DPOF_CancelAll`, `SetCursorPos`).

What changed inside paired functions (`tools/diff_pairs.py`, compared by meaning: calls mapped through the
matches, string text, plain constants; 1,523 pairs = 1,203 same-shape + 320 paired by position):
- 955 of the 1,203 same-shape pairs: no change except addresses (relinked).
- **Icon IDs.** UI functions (0x40151xxx–0x4017Dxxx, mostly task UI_CTRL) pass smaller icon numbers in the
  loader, e.g. master 0x40158D2E calls `IconIf_DrawIcon` (0x4011E274) with 0x2A9 / 0x225 / 0x20B where the
  loader passes 0x296 / 0x21B / 0x201. The shift grows with the ID (0x1EF → −8, 0x20B–0x225 → −10,
  0x243–0x253 → −14, 0x2A9 → −19, 0x310–0x31C → −20, 0x4D5–0x58F → −86): the loader's icon set lacks
  entries spread through the list.
- **A 32-byte smaller structure.** Image-processing functions (0x40052xxx–0x40081xxx, tasks STLIMG,
  PRPRO_S) use field offsets 0x20 lower in the loader (0x17DC → 0x17BC in 17 functions, 0x3F0–0x3F8 →
  0x3D0–0x3D8, 0x180C → 0x17EC) while a field at 0x1731 is unchanged: the master's structure has 32 extra
  bytes before 0x17BC (and before 0x3D0).
- A few call/string changes, e.g. the loader version of one function adds `MDF_W_lseek/read failed`
  messages, another references `X3F` and `ui_wb_corr_change_param`.
- Some position pairs are boundary artefacts (Ghidra split the function differently), e.g. dd_csio_40045116.

Reading: the loader looks like a **different build state of the same firmware** (smaller icon set, smaller
parameter structure, missing some playback file-operation jobs), e.g. an older or reduced build. A
testable way to check: unpack an earlier dp2 Quattro update (2.02 or before) and see whether its master
matches this loader.

Why the update carries two full builds, and which one runs when, is **not known**.

### Chunk 2 — sub-controller firmware (inferred)

Layout fits a Fujitsu/Socionext **F2MC-8FX (MB95xxx)** 8-bit MCU, with high but not complete confidence:
- 64 KB address space used: data at 0x1002–0x11C2 and 0x1FFC–0x203C, code 0x8000–0x9F00 (~8 KB)
- vector table 0xFFC0–0xFFFF, big-endian 16-bit, unused vectors all → 0x83BB, reset vector (0xFFFE) → 0x8000,
  0xFFFC–0xFFFD = `FF 00` (mode data)
- reset code starts `E4 01 7E` / `E1` = `MOVW A,#0x017E` / `MOVW SP,A`

The main firmware talks to a "SubMicom" (`SubMicom init failed`, `[SubM]Hand Shake failed`,
`[SubM]Failed get version`, task `SUBM`, mailbox `SUBM`), and references `C81Sub.bin`. That this chunk is
that MCU's firmware is an inference from these strings and the layout.

### Image headers (0x14C bytes before each image)

| offset | value (both images) | reading |
|---|---|---|
| 0x00 | `SIGMA_FW` + `b` / `c` | tag; the only byte that differs between loader (`b`) and master (`c`) |
| 0x0C | 2 | ? |
| 0x10–0x73 | 0x64-byte block | **DRAM controller parameters** (inferred): `05 05 04 05` (latencies), 0x1010 / 0x2020 / 0x1E1E / 0x0F0F (per-lane pairs), 0x420 and 0x40 (DDR3 mode-register-like), 100000, 0x618 = 1560 = 7.8 µs refresh at 200 MHz |
| 0x94–0xD0 | 0x4000, 7, 3, 3, 1, 3, 0x143F, 0x3F, 0x1432, 0x3F, …, 8, 1 | ? (clock/PLL-like) |
| 0xD4 | 0x40000000 | load address |
| 0xD8–0x13B | same 0x64 bytes as 0x10–0x73 | second copy of the DRAM block |

Neither image contains the string `SIGMA_FW`, so the headers are read by something outside both images
(the SoC boot ROM or a first-stage loader in flash that is not part of this update). DRAM parameters
before the image fit that: DRAM must be up before the image can be copied to 0x40000000.

## 3. OS call layer

- `svc #6` (T-Kernel/OS) stub at **0x401C3224**, `svc #9` (T-Kernel/DS) stub at 0x401C3218, both ARM.
- One ARM wrapper per call: arguments stored to the stack, `r0` = pointer to them, `r1` = function code,
  `r2` = caller's `lr`, then `bl` the stub. 285 wrappers, each code used once.
- Codes: 110 core calls `0x80NN__00` (NN = 0x01…0x6E, byte 1 = argument count), 47 DS calls `0x80NN__00`
  via svc 9, and extended SVCs for subsystems 0x28 and 0x09 (`0x00NN__28`, `0x__NN__09`).
- The argument counts of NN = 0x01…0x17 (1,1,2,0,0,1,0,0,2,2,1,1,0,2,2,1,2,4,4,3,3,3,2) follow T-Kernel's own
  ordering, so 0x80010100 = `tk_cre_tsk` (wrapper **0x401BA9E4**). Other names follow the same table;
  only `tk_cre_tsk` and `tk_cre_mbx` (0x80380100, wrapper 0x401BAC28) were checked against how they are used.
- Thumb code reaches the ARM wrappers through 445 linker veneers (`ldr pc,[pc,#-4]` and `movw/movt ip; bx ip`)
  around 0x40C437xx. `tools/dp2q_lib.py` resolves them.

## 4. Static configuration (RAM block at 0x01000000)

A block of the image starting at **0x40C40628** (loader: 0x40C304F8, length 0x791C) is copied to **0x01000000** (by `FUN_4003C982` during kernel init, see §5).
The routine `cfg_create_kernel_objects` (runtime 0x01000984; loop at 0x01000A58) creates objects from tables in that block, in order,
storing the IDs in BSS (0x4106xxxx) and spinning forever if a create fails:

| table (runtime) | entries | record | created with |
|---|---|---|---|
| … | 3 | 20 B | code 0x804B0100 (wrapper 0x401BAD74) |
| 0x010068FC | 39 | 16 B `{exinf, attr, dsname[8]}` | 0x80380100 — mailboxes (FS_IF, IMG_API, H264_IF, IM_PRC1–4, SND/RCV_REQ/RES, HDMISYC, SUBM, PTPCAMP, UI_DRAW, MOTOR, AF, AE, AWB…) |
| **0x01006B6C** | **50** | 52 B T_CTSK | `tk_cre_tsk` — the task table below |
| 0x01003BDC | 0xCB | 20 B | code 0x80490200 (wrapper 0x401BAD4C), not identified |

A further 10 system tasks (priorities 1–10, no names) are created at run time through a helper at
0x400E48C0 (`create_task(start, entry, pri, stksz)`, tskatr 0x1001). Entries found from the call sites
(`dp2q_lib.callers(d, used, 0x400E48C0)` plus constants just before each call): 0x401AFCD0 pri 1,
0x401B54EC pri 3, 0x401A4AB0 / 0x401A49D0 / 0x401A507C pri 5, 0x401A6FBC pri 5, 0x401A73DC pri 6,
0x401BB80C pri 10 (stacks 0x800–0x1000); two more call sites pass non-constant arguments.

### Tasks (master 2.03, `tools/task_table.py master`)

Priority (lower = more urgent), system stack size. All entries are Thumb. tskatr 0x43; 0x145 = with a
caller-supplied stack (AE, FS_RCV, UI_CTRL, AWB_LV, AWB_STL).

| pri | tasks |
|---|---|
| 20 | RLS_OBS (release observer) |
| 21 | BOOT, RELEASE, MBX, RROBIN |
| 24 | SYS_STS, STLCAP, INTRCAP, EVEOBS, KEYCTRL, DIALCTR, DISPML |
| 25 | SCCHILD |
| 27 | PREPRO, PRPRO_S, AF, MOTOR, SUBM, VIEWIMG, MFRING |
| 29 | EEF |
| 30 | STLASM, STLIMG, MJPCODE, PLAY, AE, EVP, AWB_LV |
| 31 | MJPMAIN, MJP_SUP, StImChd |
| 33 | AUDIO, AWB_STL |
| 36 | FS_RCV, PTP_CAM |
| 39 | MSCPRCV, MSCPSND (mass storage) |
| 42 | STORAGE, USB_PTP, USB_CTL, EYEICTL, EYFIOBS (eye sensor) |
| 52 | UART, UI_CTRL, MENUCTR, UI_BUFF, UI_HIST |
| 54 | FD (face detection), LCD |
| 55 | MONITOR |

## 5. Boot path and memory map (master 2.03; the loader is the same layout)

Reset handler 0x40000088 (ARM):
1. only CPU core 0 continues (MPIDR check); others wait in WFI. Enables VFP/NEON.
2. copies `.data` 0x40BD8674 → 0x41001470 (0x5328E bytes) and 0x40BD8348 → 0x41000000 (0x32C);
   zero-fills 0x4100032C (0x1144) and 0x41054700 (0x127E74, up to 0x4117C574).
3. copies a prebuilt 16 KB MMU L1 table from the image (0x40BD4000) to 0x41C00000, adjusts it, enables
   the MMU; Cortex-A9 private peripherals at 0xF8100000.
4. jumps to the kernel start 0x4003A4E4 (stacks, T-Kernel init).

Kernel-side init 0x4003CA08 calls the on-chip SRAM setup `FUN_4003C982`: copies 0x40C40628 → 0x01000000
(0x7633 + 0x39B bytes, contiguous) and zero-fills 0x010079C8 (0x417F bytes); then further inits,
`cfg_create_kernel_objects` (in SRAM), and starts the BOOT task (first ID in 0x41062B90).

MMU map (flat, VA = PA; from the table in the image):

| range | attributes | reading |
|---|---|---|
| 0x01000000–0x010FFFFF | normal, cacheable, executable | 1 MB on-chip SRAM (config block, kernel objects) |
| 0x02000000–0x11FFFFFF | normal, privileged read-only, executable | 256 MB window, flash/ROM-like (guess) |
| 0x12000000–0x3FFFFFFF | device, XN | peripheral registers |
| 0x40000000–0x40FFFFFF | cacheable, executable | firmware image |
| 0x41000000–0x418FFFFF | cacheable, XN | data, BSS, heap |
| 0x41900000–0x41AFFFFF | non-cacheable | DMA buffers (guess) |
| 0x41B00000–0x41EFFFFF | write-through | holds the live MMU table (0x41C00000) |
| 0x41F00000–0x42EFFFFF | cacheable | |
| 0x42F00000–0x5FFFFFFF | non-cacheable | image buffers (guess) |
| 0x60000000–0x7FFFFFFF | cacheable | ? |
| 0x80000000–0xC0FFFFFF | non-cacheable | DRAM channel 1 at 0x80000000 |
| 0xC1000000–0xFFFFFFFF | strongly ordered, XN | peripherals incl. Cortex-A9 private region |

DRAM: `SDRAM_Common_Get_Addr2Ch` maps 0x40000000–0x5FFFFFFF → channel 0 and 0x80000000–0x9FFFFFFF →
channel 1 (anything else asserts): two 512 MB windows. Fitted size not determined.

Master and loader have the same RAM layout (data 0x41001470, BSS to ~0x4117C5xx), an identical MMU table,
and the same kernel entry 0x4003A4E4: they are alternatives occupying the same memory, not stages that
hand over to each other. The choice between them is made before either is loaded, by whatever reads the
`SIGMA_FWb` / `SIGMA_FWc` headers.

## 6. Sub-controller (SubM)

Link protocol (`task_SUBM::FUN_40077BAE`): send 2 bytes `[cmd, checksum]`, expect 1 byte `0xF1` (accept),
then `n + 1` bytes (data + checksum); 3 tries; errors: no response / not accepted / checksum.
Commands seen: 0x21 = get boot mode (1 byte reply), 0x24 = no data reply.

SUBM task request handlers (table 0x4020DCF0, 10 entries; dispatcher near 0x4004C378):

| # | handler | does |
|---|---|---|
| 1 | 0x4004BFAA | exchanges a 3-byte value with the SubM, keeps a copy |
| 2 | 0x4004BFD2 | SubM call, then sets event bit 3 |
| 3 | 0x4004BFE2 | SubM poll; clears event bit 3 when flagged |
| 4 | 0x4004C008 | **SubM firmware update**: accepts the image only if the u16 at offset 0x1FFC is `TS`, `ES`, `CS` or `MP` (board stages); logs "SubM FW update board type error" otherwise |
| 5 | 0x4004C076 | cmd 0x24, then sets event bit 3 |
| 6 | 0x4004C094 | **get boot mode** (cmd 0x21) into the caller's buffer |
| 7 | 0x4004C0AC | get battery voltage |
| 8 | 0x4004C0CA | save media info |
| 9 | 0x4004C0E2 | load media info |

Chunk 2 of the update has `CS` at 0x1FFC (followed by `1E 11`, probably a version): this confirms chunk 2
is the SubM firmware. What the boot-mode values mean, and who asks for them, is not traced yet.

## 7. SD card initialisation (master 2.03, static reading)

Host: **SDHCI-compatible controller at 0xC6000000** (standard register layout: Present State 0x24, Host
Control 0x28, Power Control 0x29, Clock 0x2C, Software Reset 0x2F, interrupt status / enables 0x30 /
0x34 / 0x38, command register values `index << 8 | flags`) plus vendor registers 0x100, 0x124, 0x210.
Driver strings say `SD0`; an `SD1 (ch1)` second channel also exists (not traced).

Call chain, top down:

| function | does |
|---|---|
| `FUN_4007990C` | media start: file-system layer (`MDF_W_init`, protection mode, `setConSecMax`) |
| `FUN_400D78B8` | `SD0_sdio_init` |
| `FUN_4007BF52` | SDIO0 init: LED off, ~30 ms wait, card power on, release host reset, LED on; up to 5 attempts of `MWSDIO0_Init`, first with UHS enabled, dropping to non-UHS (`SD0 UHS Disable`) after two failures |
| `FUN_400E17D0` | `MWSDIO0_Init`: lock; card-detect poll (≤ 2000); power + identify (2 tries); status checks (error / not ready / write-protect); read MBR (sector 0), take the first entry with boot flag 0x80 or 0; read the partition boot record and its parameters; card capacity from the CSD; **SD spec version** 0–3 from the SCR (see below); type 7 + OEM `EXFAT` → exFAT |
| `FUN_400FFE9C` | detect + identify: mask interrupts, reset driver state (`FUN_400FD204`), host init (`FUN_400FD7A6`); if Present State bit 16 (card inserted): vendor reg 0x210 \|= 2, **CMD0 ×2, CMD8** (arg 0x1AA; old cards: CMD0 ×2 again), then **CMD55** accepted → SD init `FUN_400FFA10`, else MMC init `FUN_400FED56`; records ready and write-protect (Present State bit 19); no card → power off, "not inserted" |
| `FUN_400FFA10` | SD init (`SD0_Card_Init`), below |

`FUN_400FFA10` (SD init), with the commands identified from the command-register values the helpers use:
1. **ACMD41** loop (CMD55 + ACMD41, arg = voltage window \| HCS bit 30 \| XPC bit 28 \| S18R bit 24) until
   OCR bit 31, 50-unit delay between tries, 1.5 s timeout (`Timeout1`); records CCS (high capacity) and
   S18A (card accepts 1.8 V). A re-try path at 400 kHz exists (`Timeout2`).
2. if 1.8 V accepted and UHS enabled: **CMD11** voltage switch (`FUN_400FF82C`, checks DAT[3:0] low then
   high); on failure power off and fail (caller then retries without UHS).
3. **CMD2** (CID), **CMD3** (RCA, ≤ 2 tries).
4. loop (twice): **CMD7** deselect, **CMD13** until state = stand-by (1 s, `Timeout3`), **CMD9** (CSD),
   **CMD7** select; clock from CSD TRAN_SPEED; **CMD16** (block length); **ACMD51** (SCR, 8 bytes);
   **ACMD6** 4-bit bus (falls back to 1-bit), host high-speed bit; then
   - UHS: CMD6 query of supported modes, then CMD6 switch from the highest allowed mode downwards
     (`SD0_Set_Switch_Func`: UHS-I mode, driver strength, current limit; requires 1.8 V bus power);
   - otherwise: CMD6 high-speed switch if enabled.
   Other helpers: **ACMD42** (DAT3 pull-up off), **ACMD13** (SD status, 64 bytes).

| helper | command value | command |
|---|---|---|
| `FUN_400FEF74` | 0x0000 | CMD0 |
| `FUN_400FE4BE` | 0x081A (arg …AA) / 0x083A | CMD8 (MMC: 512-byte EXT_CSD read) |
| `FUN_400FF29C` | 0x371A | CMD55 |
| `FUN_400FF990` | 0x2902 | ACMD41 |
| `FUN_400FEC36` | 0x0209 | CMD2 |
| `FUN_400FEB54` | 0x031A | CMD3 |
| `FUN_400FE9CE` | 0x071B | CMD7 |
| `FUN_400FEAD8` | 0x0909 | CMD9 |
| `FUN_400FDE4E` | 0x0D1A | CMD13 |
| `FUN_400FE242` | 0x101A | CMD16 |
| `FUN_400FF4DC` | 0x333A | ACMD51 |
| `FUN_400FF32A` | 0x061A | ACMD6 |
| `FUN_400FF7AE` | 0x2A1A | ACMD42 |
| `FUN_400FF6EE` | 0x0D3A | ACMD13 |
| `FUN_400FF82C` | — | CMD11 (from its error strings) |
| `FUN_400FF162` | — | CMD6 switch (from its error strings) |

Host bring-up `FUN_400FD7A6`: host reset; bus power at the card voltage; high-speed off; card power on;
clock 400 kHz; 20 ms wait; SD clock on; clear interrupt status; enable card insert/remove interrupts
(0x34/0x38 bits 6–7); vendor regs 0x100 (bit 6 cleared), 0x124 (\|= 0x200).
Bus power `FUN_400FD51C`: SDHCI Power Control, 0xF = 3.3 V, 0xD = 3.0 V, 0xB = 1.8 V (from OCR bits), or off.

Card power `Media_Driver_SD_Power_On` (0x4007234E): GPIO block at 0xD0000000 (set/clear bit n in the
word array at 0xD0002000: `FUN_4013250E` / `FUN_401324F0`): pins **0x47** then **0x22** set with short
delays, then `FUN_40071E76` configures pins **0x183–0x187 and 0x2E0** (six pins: presumably the SD bus,
CLK/CMD/DAT0–3) through three per-pin functions.

Interrupt handler `FUN_4007BDB8`: status (0x30) & signal enable (0x38): bit 7 = removal (`SDIO0 Ejected.`),
bit 6 = insertion (`SDIO0 Inserted.`), bit 0 / 1 = command / transfer complete, plus error bits.

SD spec version (media struct 0x410698DC, byte 0x41): `FUN_400E144E` splits SCR bytes 0–2 into
SCR_STRUCTURE, SD_SPEC, DATA_STAT_AFTER_ERASE, SD_SECURITY, SD_BUS_WIDTHS, SD_SPEC3; the stored value is
3 = SD 3.0x (SD_SPEC 2 + SD_SPEC3), 2 = SD 2.00, 1 = SD 1.10, 0 = SD 1.0 (or forced 0 by a global flag).
Then SCR byte 3 bit 0 (card supports CMD20, speed-class recording control) is cleared, except for SD 3.0x
cards whose media-struct field 0x24 is > 14: CMD20 code exists (`CMD20 command error`) but is mostly not used.
(Readers of byte 0x41: only three functions in the whole image load a byte at offset 0x41 — one on a stack
local in task_AE, two field-by-field structure copies in task_BOOT (0x4016EFA2, 0x4016F3B8). No code was
found that acts on the version; it may be unused or only read through such a copy.)

Vendor registers, matched against Linux `sdhci_f_sdh30.h` / `sdhci-milbeaut.c` (Fujitsu/Socionext F_SDH30):

| offset | firmware | Linux name |
|---|---|---|
| 0x100 | clear bit 6 at host init | `F_SDH30_AHB_CONFIG`, bit 6 `AHB_BIGED` (little-endian AHB; Linux clears it too) |
| 0x108 | set / clear bit 16 around tuning (`FUN_400FF638`) | `F_SDH30_TUNING_SETTING`, bit 16 `CMD_CHK_DIS` |
| 0x124 | set bit 9 at host init | `F_SDH30_ESD_CONTROL`, bit 9 `CMD_DAT_DELAY` |
| 0x210 | set bit 1 at detect | `MLB_WP_CD_LED_SET` (Linux names only bit 2, LED invert) |
| 0x104 | set bit 0 before CMD11; bits 0–1 read in `FUN_400FE89E` | not in Linux |
| 0x118 / 0x11C | CMD11: 0x11C \|= 3; wait 0x118 bit 0, write 1; … wait bit 1, write 1 | not in Linux: behaves as a voltage-switch event status (write-1-to-clear) / enable pair |

`FUN_400FF638` is **tuning** (64-byte block = CMD19 tuning pattern; run only for bus-speed modes > 3).

CMD11 sequence (`FUN_400FF82C`): 0x104 bit 0, 0x11C bits 0–1; CMD11 (≤ 10 tries, R1 error bits checked);
SD clock off (0x2C bit 2); DAT[3:0] must read 0 (Present State bits 20–23); Host Control 2 *1.8V Signaling
Enable* (0x3E bit 3); wait/clear 0x118 bit 0; check the 1.8 V bit stuck; SD clock on; wait/clear 0x118 bit 1;
DAT[3:0] must read 1111. Same order as the SD spec; the Linux Milbeaut driver instead toggles
`F_SDH30_IO_CONTROL2` (0x114) in software, so this host revision appears to sequence the switch itself.

File-system media (`Fsc_Format(media)` 0x4007A30E; presence `FUN_400E1102(media)`, debounced by
`FUN_400E113A`; the medium in use comes from `FUN_400E10CA`, not traced):

| media | drive | presence | low-level driver |
|---|---|---|---|
| 2 | `S0:\` SD card | GPIO pin 0x180 (0xD0002030 bit 0) | full SD0 driver (above) |
| 4 | `NF:\` NAND flash | always present | real: `MWNF_BasicInit` / `MWNF_Format` (`FUN_400D7986`), FTL with bad-block handling, ECC, retries; format uses `MDF_W_Qformat` |
| 5 | `CF:\` CompactFlash | `FUN_401ECB08`: 0xD0002010 bits 3 and 4 both low (CD1/CD2-style, two active-low pins) | real: `MWCF_Init`, `MWCF_MBRFormat` (`FUN_400D7A46`), write cache |
| 6 | `S1:\` SD channel 1 | GPIO pin 0x3C0, active low | stub (`FUN_400D7938` returns 0) |

Every fixed file path in the firmware is on `S0:\`; `NF:\` and `CF:\` appear only as drive roots. The dp2
Quattro has one SD slot and no CF slot: CF and SD1 are driver code shared with other models. Whether the
camera mounts its NAND as `NF:` in normal use is not established.

Second channel `SD1 (ch1)`: file-system media 6, drive `S1:\` (the card is media 2, `S0:\`). Presence =
GPIO pin 0x3C0 active-low (word 0xD0002078 bit 0), debounced 5 reads 25 ms apart (`FUN_400E113A` /
`FUN_400E1102`; media 2 = pin 0x180, 0xD0002030 bit 0). Its mount `FUN_40079FFA` is reached only from
`Fsc_Format` (media 2, 4, 5, 6), and its low-level init `FUN_400D7938` is an empty stub returning 0. The dp2
Quattro has one card slot: this is code shared with other models, not a working second slot.

Read/write: `SD0_Send_Command17/18/24/25` (single/multi block read/write, DMA for 25) at
0x40100DFE / 0x40100AF0 / 0x401017E8 / 0x401013D8, with `SD0_Err_Recovery` (CMD12 etc.) on errors.

## 8. Open

- SD: names of vendor regs 0x104/0x118/0x11C (not public); whether NF: is mounted in normal use (`FUN_400E10CA`)
- the 0x94–0xD0 header fields; what reads the headers (not in this update)
- which of loader/master boots, and when (decided before either image runs); the SubM boot-mode values
- the 3-entry and 203-entry config tables
- checksum or signature of the update file (none found in the header, nor as a plain sum/CRC of chunks)
