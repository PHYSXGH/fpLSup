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

| table (runtime) | entries | record | created with | objects |
|---|---|---|---|---|
| 0x01004BB8 | 191 | 24 B `{exinf, attr, isemcnt, maxsem, dsname[8]}` | 0x80280100 (0x401BAB08) | **semaphores**, one per peripheral channel: CA9PTMR, CA9GTMR, CA9WDOG, IPCEXC/IPCCNT, TMR32_0–9, USIO0–5, HDMAC00–07 / 10–17, XDMACP1/2, DZOOM, SPR0CH/1CH, IZA0/1, ADC0/1, TMR0/1, X0CH/X1CH, RAW, DCC_SND/RCV, JPEG, JPEGENC, JPEGXR, AUDIOIF, I2C0/1, PWM0, … |
| 0x01005DA0 | 11 | 20 B `{exinf, attr, ceilpri, dsname[8]}` | 0x802D0100 (0x401BAB70) | **mutexes**: IM_CAPN, IM_CAP, IM_REST, DRFT_ST, IM_ENC, GUI_ST, MD_ST, MVCTRL, CAPTURE, KEY_TBL, KEY_STS |
| 0x01005E7C | 87 | 20 B `{exinf, attr, iflgptn, dsname[8]}` | 0x80320100 (0x401C32D0) | **event flags**: SLDESHW, PR_PRCS, IM_PROC, …, SD0, SD1, NF, CF, FILESYS, H264, USB, USBLLD, HDMISYC, SBMICOM, PREPRO, STLCAP, DRAWBUF, … |
| 0x01006548 | 37 | 24 B `{exinf, attr, mpfcnt, blfsz, dsname[8]}` | 0x80500100 (0x401BAE20) | **fixed-size memory pools** (count × block): the per-mailbox message pools (SUBM 4×0x20, STLIMG 16×0x20, STLASM 16×0x20, PRPRO_S 16×0x50, FS_MSG 16×0x444, …), IMG_API 32×0x400, DCF_DB 20000×0x14, … |
| 0x010068C0 | 3 | 20 B `{exinf, attr, mplsz, dsname[8]}` | 0x804B0100 (0x401BAD74) | **variable-size memory pools**: FS 0x8AC00, EXIF 0xA000, UI_PRM 0x2000 |
| 0x010068FC | 39 | 16 B `{exinf, attr, dsname[8]}` | 0x80380100 (0x401BAC28) | **mailboxes** (IDs at 0x4106317C; e.g. +0x38 SUBM, +0x40 STLIMG, +0x48 STLASM) |
| **0x01006B6C** | **50** | 52 B T_CTSK | 0x80010100 `tk_cre_tsk` | **tasks** (IDs at 0x41062B90), below |
| 0x01003BDC | 203 | 20 B `{intno − 32, intatr 1, handler, …}` | 0x80490200 (0x401BAD4C), called with (intno, &rest) | **interrupt handlers** for intno 32–251 (Cortex-A9 GIC shared interrupts): 126 distinct handlers, 77 numbers share a default handler (0x401A1F0C); each entry is a Thumb `bx pc` stub in SRAM (0x01000B80 + …) jumping to a small SRAM wrapper that calls the driver's handler |

The ID arrays are BSS at 0x41062C58 (semaphores), 0x41062F54 (mutexes), 0x41062F80 (flags), 0x410630DC (fixed
pools), 0x41063170 (variable pools), 0x4106317C (mailboxes), 0x41062B90 (tasks). The function codes are
consistent with T-Kernel 1.x numbering (cre_sem 0x28, cre_mtx 0x2D, cre_flg 0x32, cre_mbx 0x38, def_int
0x49, cre_mpl 0x4B, cre_mpf 0x50), each checked against the record layout it is given.

Interrupt map (handler → driver module; "name" = the handler itself is named, "near" = nearest named
function within 1 KB, a guess):

| intno | handler | driver |
|---|---|---|
| 59, 62 | 0x400A947E, 0x400A88F8 | dd_ca9 (near) |
| 96 | 0x400C251E | Im_PRO (near) |
| 97, 98, 111, 121 | 0x400C2CC2, 0x400C2D70, 0x400C3EA2 | Im_SPR (near) |
| 101 | 0x400CBD7C | Im_JPEGENC (near) |
| 106–109 | 0x400B1DF4 | Im_DISP (near) |
| 113 | 0x4010C236 | Im_B2Y (near) |
| 118, 119 | 0x401244D2 | im_iza (name) |
| 120 | 0x400C5556 | Im_DCC (near) |
| 122 | 0x400B6BC6 | Im_Xch (near) |
| 124–127, 236, 237 | 0x400AC040 | dd_udc (name) |
| **128** | **0x4007BDB8** | **SD0 host** (the SDHCI interrupt handler, §7) |
| 155, 156 | 0x400AD13A | dd_i2c (name) |
| 157, 158 | 0x400AD742 | Dd_ADC (near) |
| 160–161, 163–166, 233 | 0x400424FC | Dd_TMR32 (near) |
| 168–173 | 0x400AFC98, 0x400AFD90 | dd_pwm (name) |
| 175–182 | 0x400AE5AC | dd_hdmac0 (near), 8 channels |
| 183–190 | 0x40046A44 | dd_hdmac1 (near), 8 channels |
| 194–203, 238, 239 | 0x4004363E / 0x400435F4 alternating | dd_uart (name/near), 6 channels × 2 |
| 224, 225 | 0x400AB25E | dd_ca9 (name) |
| 228–231 | 0x400AA2BC | dd_xdmafasp (name) |
| 100, 102, 112, 115–117, 134, 136–143, 162, 167, 204–206, 216, 222, 223, 232, 243, 247, 250, 251 | various | not labelled (136/137 "near Ui_Setup" is not credible) |

The full list is generated into `out_dp2q/ghidra/irq_labels_master.tsv`.

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
is the SubM firmware.

Request path: SUBM task main loop 0x4004C232 receives 0x1C-byte messages on mailbox `SUBM` (ID array
0x4106317C + 0x38), request number at +8, reply buffer at +0x10, callback +0x14, sync object +0x18; on
receive timeout it runs request 1 (poll). Senders: `FUN_4004C212` → `FUN_4004C1B8` (post); one wrapper per
request, e.g. `FUN_40077784` = get boot mode (request 6, returns 1 byte), `FUN_400777A4` = get battery
voltage (request 7; caller `FUN_4009B8FC` scales ×8/3 − 1428), `FUN_400777DA` = load media info (9).
**Get boot mode is never called** in either build (master `FUN_40077784`, loader 0x40077108: no calls, no
pointers; the one apparent caller at 0x405FB9C0 is data). Its values cannot be read from this firmware;
if anything uses the SubM boot mode it is the earlier boot stage, which is not in this update.

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
Quattro has one SD slot and no CF slot: CF and SD1 are driver code shared with other models. The active
medium (byte 0x4101D5C4; per-medium write-protect at +1..+4) is set only by `Fsc_Start_Media(media)`
(0x4007A4D6), `FUN_4007A54C` (register a medium's drive names) and a reset to 0; the medium number comes
from file-system request messages. The UI text only ever mentions a memory card ("No memory card.",
"Memory Card Format", …), no internal memory: `NF:` is not a user-facing medium on this camera.

Second channel `SD1 (ch1)`: file-system media 6, drive `S1:\` (the card is media 2, `S0:\`). Presence =
GPIO pin 0x3C0 active-low (word 0xD0002078 bit 0), debounced 5 reads 25 ms apart (`FUN_400E113A` /
`FUN_400E1102`; media 2 = pin 0x180, 0xD0002030 bit 0). Its mount `FUN_40079FFA` is reached only from
`Fsc_Format` (media 2, 4, 5, 6), and its low-level init `FUN_400D7938` is an empty stub returning 0. The dp2
Quattro has one card slot: this is code shared with other models, not a working second slot.

Read/write: `SD0_Send_Command17/18/24/25` (single/multi block read/write, DMA for 25) at
0x40100DFE / 0x40100AF0 / 0x401017E8 / 0x401013D8, with `SD0_Err_Recovery` (CMD12 etc.) on errors.

## 8. Still saving: X3F, X3I, JPEG, DNG

Pipeline (master 2.03): **STLCAP** (capture control, 0x40086A58–0x400870A6) → **PREPRO** (send helper
`FUN_40055D68`, 14 call sites in that module) → **PRPRO_S** (send helper `FUN_400583DE`, called from the PREPRO
handlers at 0x40053844–0x4005554A; handler table 0x4020E430) → **STLIMG** → **STLASM** → file-system service →
format writers.

1. **Still pre-processing** (PRPRO_S handlers 6, 11, 12: `FUN_40058FF8`, `FUN_4005939A`, `FUN_400593E8`) posts to the **STLIMG** mailbox (`FUN_4005A3E6`, 0x14-byte messages, request at +8):
   request 0/1/8 for normal shots, 5–9 chosen by shot-type flag bits (0x102, 0x10, 0x8000000, 0x4000000,
   0xE0000000), 10 or 11 by the resolution-mode byte +0x1731 (4 or 0xF → 11).
2. **STLIMG** (handler table 0x4020E47C, entries 0–11) does the image processing and posts to the **STLASM**
   mailbox (`FUN_4005B1C8`, 0x18-byte messages). Handlers 0/1 choose the save: request **1** if the shot is
   raw (`FUN_401314C4`), else **2** if the quality is DNG (`FUN_40131084`, "is qual DNG"), else **0**. Others
   post 4, 5, 6, 7, 8, 9, 10.
3. **STLASM** (task 0x4005B1F6, handler table 0x4020E4AC, 11 entries) saves:

| STLASM request | handler | FS commands |
|---|---|---|
| 0 | `FUN_4005A702` | 0x39 JPEG |
| 1 | `FUN_4005A8BA`: copies three metadata blocks (0xF1 @+0x2A2, 0xFB @+0x1A7, 0x360 @+0x393) into the per-shot parameter structure, builds the save descriptor | 0x37 X3F; quality byte +0x1736 = 3 → also 0x39 (RAW+JPEG); flag +0x1B → **0x38 X3I** instead |
| 2 | `FUN_4005AB50`, same metadata steps | 0x82 DNG |

4. **File-system service** (table 0x4020DDF0, 81 entries; command = index + 0x32; posted by `FUN_400F0A38` →
   `FUN_400E1002`; one wrapper per command at 0x400F0A76–0x400F1DDC):

| FS command / index | handler | save function | writers |
|---|---|---|---|
| 0x37 / 5 Save Raw (X3F) | `FUN_400790C6` | `FUN_401309DE` | mode 1 `FUN_4012D736`, 2/3 `FUN_4012DA04` |
| 0x38 / 6 Save X3I | `FUN_400790FC` | `FUN_40130A74` | mode 1 `FUN_4012E334`, 2/3 `FUN_4012E38E` |
| 0x39 / 7 Save Jpeg | `FUN_40079132` | `FUN_4012EB8A` | mode 1 `FUN_4012BFB4`, 2/3 `FUN_4012C200` |
| 0x82 / 80 Save DNG | `FUN_40079890` | `FUN_40130B98` | mode 1 `FUN_4012DC4A` |

Mode 3 = save, then copy (`Copy X3F/Jpeg/DNG` routines; `Copy X3I` (`FUN_40130B76`) only returns success for
mode 3 and copies nothing). Raw saves refuse "APP1 SIZE OVER" when thumbnail + headers + 0x1B60 ≥ 64 KB
(the embedded JPEG's EXIF). The per-shot parameter structure is the one whose fields sit 0x20 lower in the
loader (§2).

Format templates live in `.data` (image 0x40BD8674.. → RAM 0x41001470..), so code refers to RAM addresses.

**X3F** (template RAM 0x410111B0 / image 0x40BE83B4; reached only from the X3F writers):

| offset | block |
|---|---|
| 0x000 | `FOVb` header, version 4.1; filled by `FUN_400DCDFA`: image size **5424 × 3616** (0x1530 × 0xE20, Quattro top layer) or **2712 × 1808** when +0x1731 is 4 or 0xF; unique ID from `%08ld` of a counter (+0x16D0) and a date/time value; rotation 180/90/270 (0xB4/0x5A/0x10E) |
| 0x5D0 | `SECi` v2.0, type 2, format 18: processed preview (JPEG) |
| 0x5EC | `SECc` v2.0, type 5: CAMF, stored obfuscated (`X3FCamfile.cpp` has `FCEb` / `pDecrypt`), see below |
| 0x628 | `SECi` v2.0, type 3, format 35 (0x23): the raw image: **three planes** (save descriptor pointers +0x20 / +0x24 / +0x28, sizes +0x60 / +0x64 / +0x68, each padded to 16 bytes), i.e. the Quattro's three sensor layers; the writer streams them as they are, so any encoding happens earlier in the pipeline (kernel objects `RAW`, `CP_RAW`) |
| 0x688 | `SECd` v2.0 directory, 3 entries `IMA2`, `CAMF`, `IMA2` (offsets/lengths filled at write time) |

X3F write order (`FUN_4012D736`): free-space check (sizes + 0x214C) → create file → header (`FUN_400DD628`
fills the template) → a fixed 0x214C-byte block → section header, aligned to 32 → preview (+0x44, size +0x48,
padded to 4) → raw section header → the three planes → directory.

CAMF content: record template in the data area from 0x402A3424 (Sigma record types `CMbM` matrix ×144,
`CMbP` property list ×9, `CMbT` text ×2). Matrix records include: CamsysVersion, ContentVersionNumber,
SensorISO, SensorTemperature, SensorBoardTemperature, Capture{Aperture,Shutter,ExpTime,ExpComp,ISO},
ExpEstimate, Bracket, Burst, CAMERAID, FPNSuppression, ImageDepth, RawOffset, TempGainFact, BadnessTable,
BadClusterMargin, Despeckle/Highlight* thresholds, *ColorShadingRatio, *WBGain and *CCMatrix per light
source (Sunlight, Shade, Overcast, Incandescent, Fluorescent, Flash, Auto, AutoLSP, Custom), ColorTemp*,
CMCM_* / MultiAxisTable_* / CMCC_* per colour mode (Standard, Vivid, Neutral, Portrait, Landscape, FCBlue,
FCYellow, Cinema, ForestGreen, SunsetRed, Monochrome), AF/AE/histogram data, denoise / slider sensitivities,
EstimatedISO*, AutoTone*, sRGB multi-axis tables, KeepImageArea / ActiveImageArea / DarkShield* (twice).
Property lists: IncludeBlocks, ColorShadingGainRatio, WhiteBalanceGains, WhiteBalanceColorCorrections,
ColorModeCompensations, ColorModeMultiAxisTableCompensations, ColorModeContrastCompensations,
InCameraMultiAxis; text: CamsettingsInfo. A converted camfile (`ConvCamfile_v022`) is looked up by PREPRO,
STLIMG and StImChd during processing.

**X3I** (template RAM 0x41011EC4 / image 0x40BE90C8; reached only from the X3I writer): the same layout, plus
a `FOVi` info block and a `SECf` section with a frame list (14 `FRAM` slots; used by 0x400DDF9A,
0x400DE45C, 0x400DE4A2): the multi-exposure container.

**DNG** (template RAM 0x41014CB0 / image 0x40BEBEB4, used by 0x400DEE5A–0x400E0BAE): little-endian TIFF,
**DNG 1.3.0.0** (backward 1.3).
- IFD0 (43 tags): 8-bit JPEG preview (NewSubfileType 1, Compression 7, YCbCr), Make `SIGMA`, Model and
  UniqueCameraModel `SIGMA dp2 Quattro`, Software `SIGMA dp2 Quattro ver%01d.%02d.%d.%04X`, Exif IFD,
  3 SubIFDs, ColorMatrix1/2, ForwardMatrix1/2, AnalogBalance, AsShotNeutral, BaselineExposure (0),
  BaselineNoise/Sharpness, LinearResponseLimit, ShadowScale, CalibrationIlluminant1/2 = 17 / 15, tag 0xC6F5
  (6 values), ProfileName `Original`, ProfileToneCurve (129 points), ProfileEmbedPolicy.
- SubIFD 0: the main image: NewSubfileType 0, uncompressed, **Photometric 34892 LinearRaw, 3 samples, 12
  bits**, WhiteLevel 4095 ×3, BlackLevel (template 0), DefaultCrop, ActiveArea, AntiAliasStrength,
  BestQualityScale.
- SubIFDs 1, 2: 8-bit JPEG (YCbCr) previews with PreviewColorSpace.
- **ColorMatrix1/2 are the standard sRGB→XYZ (D50) matrix** (0.4361 0.3851 0.1431 / 0.2225 0.7169 0.0606 /
  0.0139 0.0971 0.7142) and **ForwardMatrix1/2 identity** (off-diagonals stored as 0/0). The five writer
  functions fill AnalogBalance (1.0), AsShotNeutral, the tone curve, crop size and active area, but not the
  matrices: the DNG carries camera-rendered linear RGB with fixed sRGB-based matrices; per-shot white
  balance and tone curve only.
- A second `II*` header in `.data` (RAM 0x4100DDA0) is not referenced at its start; likely the EXIF/TIFF
  block inside JPEGs (not checked).

## 9. Extracted data (master 2.03; tools in `tools/extract_*.py`, output in `out_dp2q/extract/`, ignored)

| what | where in the image | tool | result |
|---|---|---|---|
| UI messages | pointer run 0x40BF53CC (.data → RAM 0x4101E1C8); per-language base list 0x4014CBD8 | `extract_strings.py` | 17 languages × 586 strings, UTF-8: en, ja, de, fr, es, it, zh-Hans, zh-Hant, ko, ru, nl, pl, pt, da, sv, no, fi; plus 332 untranslated strings (debug menu, apertures, shutter speeds) |
| UI icons | table RAM 0x41051A80 / image 0x40C28C84, 12-byte entries {u8 format, u16 w, u16 h, u32 data}, IDs 1–797 | `extract_icons.py` | 797 PNGs + contact sheet. Pixels (draw code 0x4011E7CA): format 1 = 16 bpp nibbles **R \| A \| B \| G**; format 0 = 8 bpp, high nibble grey, low nibble alpha. Screen layer 640 × 480 × 16 bpp. Only 10 colour icons (hourglass, thermometer/warning, colour-adjust grid, SFD badge) |
| CAMF records | 0x402A3424 | `extract_camf.py` | 146 records (`camf.json` / `camf.txt`). Real built-in values in 61: ImageDepth 14, RawOffset 2048, CAMERAID 81, `CamsettingsInfo` = "Camsettings-F23-DP2Quatro", BadnessTable, highlight / denoise parameters, colour-mode matrices and multi-axis tables (Vivid, Neutral, Cinema, …), contrast compensations, AutoToneGain (32 × 11), in-camera sRGB multi-axis set (`gausMACC_sRGB_MCK`: 1080 values, 1024 = 1.0). WB gains and CC matrices are identity placeholders, filled from the camera's calibration |
| file templates | X3F 0x40BE83B4, X3I 0x40BE90C8, DNG 0x40BEBEB4 | `extract_camf.py` | binaries |
| curves | data area | `extract_curves.py` | 32 monotonic u16 runs: two 2048-entry gamma-type curves (0x402C198E, used by FUN_4008F040), a 4096-entry log-like curve (0x402CAC3A, FUN_400CC3A8), R/G/B 256-entry expansion curves (0x40457408 …), identity ramps |
| images | — | `extract_images.py` | none in standard formats: one BMP header template (0x402C4C14, debug screenshot header, no image behind it), an EXIF APP1 template (0x40BE4F98) |

Fonts (not extracted): text is UTF-8; `FUN_4015A50E` (per character, via `Fontdrv_Font_Measure` 0x4015A9BC) routes by
Unicode block: ASCII / Latin-1 / Cyrillic (0x400–0x4FF) / punctuation (0x2000–) / arrows (0x2190–) use blocks in the
image (glyph blocks starting `02 00 31 02 03 00` at 0x407E0518, 0x407E9134, 0x407F1CD4, 0x4058C474, 0x4060BFDC, …;
`BP4 ` metric blocks at 0x407E8A24, 0x407F15C4, 0x407FA18C, 0x40746320: 8-byte entries per character, first field the
advance width, e.g. digits all 0x89); CJK symbols, kana and ideographs (0x4E00–0x9FFF, variant by UI language) come
from RAM 0x6300A000–0x6306A400, loaded at run time from outside the image. Glyph data is compressed or
outline-based in a custom format and was not decoded.

Not found in the image: lens distortion / vignetting tables by name (colour-shading factors are calibration keys, e.g.
`SunlightColorShadingFactorR`); the CJK fonts.

## 10. Open

Host-reachable surfaces that do **not** touch flash (UART Debug Terminal, card files read-and-applied):
[`DEBUG_SURFACES.md`](DEBUG_SURFACES.md). Summary: the loader has an interactive UART command shell
(`TM>`), but it is entered mainly from the exception handler (crash console) and its command table is
filled at runtime, so the command set — and thus whether it allows poke/call — is unknown without a RAM
dump. `S0:\Camfile.bin` is read (≤6 MB) from the card and applied — now traced (2026-11-11) and **ruled out**
as an injection/code surface: it is a persistent calibration writer to firmware-fixed logical blocks, the
card controls only payload bytes. So **no non-destructive code-execution path is statically knowable**; the
UART command set (needs a RAM dump) is the only remaining lead. USB-shell-port consequence:
[`USB_SHELL_PORT.md`](USB_SHELL_PORT.md).

- saving: how the three raw planes are encoded (upstream of the writer)
- UART terminal command set: the table at RAM `0x41000024` is registered at runtime; the registrar was not
  found statically (needs a RAM dump or a write-xref hunt) — see [`DEBUG_SURFACES.md`](DEBUG_SURFACES.md) §1
- `S0:\Camfile.bin` apply path: traced (persistent calibration writer, not code) — only what *triggers* it
  (service menu vs. automatic) is still open, and moot for injection — see [`DEBUG_SURFACES.md`](DEBUG_SURFACES.md) §2

Blocked on material that is not in this update:
- SD vendor regs 0x104/0x118/0x11C names: Socionext M7 SD host documentation or vendor source (not public)
- image-header fields 0x94–0xD0, which image boots, SubM boot-mode values: the first-stage boot code
  (boot ROM / flash loader) or a flash dump
- loader = previous version?: an older update file (DP2QV202.BIN or earlier)

Not pursued: checksum or signature of the update file (none found in the header, nor as a plain sum/CRC
of chunks).

