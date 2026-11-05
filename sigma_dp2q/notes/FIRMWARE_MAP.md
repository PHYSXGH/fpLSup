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

A block of the image starting at **0x40C40628** (loader: 0x40C304F8, length 0x791C) is copied to **0x01000000** (inferred: the init code that
uses it runs there and its literal pools hold 0x0100xxxx addresses; the copy routine itself was not found).
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

## 5. Open

- the copy routine for the 0x01000000 block, and what 0x01000000 is (on-chip RAM?); the DRAM map
  (`Map/src/sdram_map_common.c` is only a path string so far)
- the 0x14C-byte image header parameters (contain 100000 = 0x186A0 twice: a clock?)
- which of loader/master boots, and when
- the 3-entry and 203-entry config tables
- checksum or signature of the update file (none found in the header, nor as a plain sum/CRC of chunks)
