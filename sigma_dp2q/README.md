# SIGMA dp2 Quattro firmware

Not the fp: different SoC (Socionext Milbeaut M7, project "C81", Cortex-A9), different codebase,
Foveon sensor. Nothing in `fpSup/` or the fp address tables applies here.

## Unpack

```
python3 -I sigma_dp2q/tools/unpack_dp2q.py firmware/DP2QV203.BIN out_dp2q
```

`out_dp2q/` is ignored (firmware-derived). Container layout is in the tool's docstring. Results on 2.03:

| file | what |
|---|---|
| `loader_40000000.bin` | M7_Loader image (`SIGMA_FWb`), loads at 0x40000000, reset 0x40000088 |
| `master_40000000.bin` | M7_Master image (`SIGMA_FWc`), loads at 0x40000000, reset 0x40000088 |
| `*_hdr.bin` | 0x14C-byte per-image header (parameters not decoded) |
| `chunk2.bin` | 0x20000 bytes, most likely the 8-bit sub-controller (F2MC-8FX) firmware, see the notes |

Checks: the parts reassemble to the original file byte for byte; with base 0x40000000 about 740 literal
pointers per image land on `push {…, lr}`, against 8–72 for bases ±0x1000 / ±0x20000.

Firmware map (platform, loader vs master, sub-controller chunk, OS call layer, the 50-task table):
[`notes/FIRMWARE_MAP.md`](notes/FIRMWARE_MAP.md).

```
python3 -I sigma_dp2q/tools/task_table.py master   # or loader; --csv
```

Not known yet: any checksum (none found in the header or as a plain sum/CRC of the chunks), the header
parameters, and how the loader and master images are used at boot.

## Ghidra (headless, 12.2)

The project lives in `out_dp2q/ghidra/` (ignored). Steps that worked for master 2.03:

```
cd out_dp2q/ghidra; T=~/my_code/fpLSup/sigma_dp2q; G=~/tools/ghidra_12.2_PUBLIC/support/analyzeHeadless
python3 -I $T/tools/ghidra_seeds.py master > seeds_master.csv              # needs capstone
python3 -I $T/tools/data_regions.py master > data_regions_master.csv
# 1. import + setup (maps ram_cfg at 0x01000000, seeds stubs/wrappers/tasks), no analysis yet
$G "$PWD" dp2q_master -import ../master_40000000.bin -loader BinaryLoader -loader-baseAddr 0x40000000 \
   -processor ARM:LE:32:v7 -scriptPath $T/ghidra_scripts -preScript DP2QSetup.java "$PWD/seeds_master.csv" -noanalysis
# 2. mark repetitive regions as data BEFORE analysing (see below), then analyse
$G "$PWD" dp2q_master -process -noanalysis -scriptPath $T/ghidra_scripts -preScript DP2QData.java "$PWD/data_regions_master.csv"
GHIDRA_HEADLESS_MAXMEM=16G $G "$PWD" dp2q_master -process -scriptPath $T/ghidra_scripts -postScript DP2QReport.java
```

Step 2 matters: 0x40754074..0x4077DFD8 is ~170 KB of `00 FF 00 00` that Thumb decodes as code. Unmarked, Ghidra
builds one huge function from it, and constant propagation / decompiling grows without bound (8 GB heap: OOM
after 2 h; 24 GB: killed by the kernel at 21 GB). `data_regions.py` finds 161 such regions (2.6 MB).
The project in `out_dp2q/ghidra/` was not built in exactly this order (import was analysed first, regions
marked afterwards), so its first-pass constant propagation was cut short; string references look complete
enough (6,415 of 9,308 strings referenced, 3,512 from functions).

Superseded by `tools/ghidra_pipeline.sh` (below), which also seeds pointer-referenced prologues and
repeats analysis until it converges (4 passes): master 16,338 functions, loader 16,387.

Earlier result: 15,089 functions (11,197 Thumb, 530 in ram_cfg); code is 0x40000000..~0x40210000 (~1.8 MB of
instructions), everything above is data (strings, fonts, images, tables). Other scripts: `DP2QSeeds.java`
(extra seeds: `tools/ghidra_more_seeds.py`), `DP2QCoverage.java` (per-MB map), `DP2QBigFuncs.java`,
`DP2QStrRefs.java`.

### Naming (after analysis)

```
$G "$PWD" dp2q_master -process -noanalysis -scriptPath $T/ghidra_scripts -preScript DP2QThumbPtrRefs.java \
   -postScript DP2QNameFromStrings.java dry "$PWD/names_dry.csv"      # review, then: apply names_applied.csv
```

- `DP2QThumbPtrRefs.java`: pointers to Thumb code carry bit 0; adds the reference to the real address
  (master: 3,098 pointers, 997 to function entries, incl. the 50 task-table entries).
- `DP2QNameFromStrings.java` (`dry` | `apply` | `dump`): names `FUN_` functions from strings they reference:
  `self` = own name at the start of a log line (`E:Im_DISP_Set_Addr: …`, `I:Im_PRO_Ctrl error. …`,
  `--- Display_LCD_Set_Addr() : …`); `func` / `func1` = a `__func__` identifier used only by that function
  (with / without a `%s` format; `func1` needs an underscore and rejects ALL_CAPS); `file` = only a source
  path, gives `<module>_<addr>`. A name claimed twice is not applied.
  Master 2.03: 703 applied (self 354, file 207, func1 93, func 49), 45 duplicates held back.
  Two `func1` names were wrong before the ALL_CAPS rule (mailbox name `IM_PRC4`, enum `RES_LOW`) and were
  fixed with `DP2QRename.java` (CSV addr,name[,comment]; empty name = back to `FUN_`).

### Task ownership and module hints

```
$G "$PWD" dp2q_master -process -noanalysis -scriptPath $T/ghidra_scripts -postScript DP2QTaskOwner.java apply owner_master.csv 12
$G "$PWD" dp2q_master -process -noanalysis -scriptPath $T/ghidra_scripts -postScript DP2QCalleeHints.java apply hints_master.csv
```

- `DP2QTaskOwner.java`: from each `task_*` entry, walks direct calls plus function pointers loaded in the body
  (one literal-pool level), through thunks, not into OS wrappers or hubs (> 12 callers). Functions reached
  from exactly one task move into namespace `task_<NAME>` (names unchanged). Master: 48 tasks walked
  (MSCPRCV/MSCPSND entries are 8-byte ARM stubs Ghidra did not make functions of), 4,801 reached,
  2,871 owned, 1,783 shared. Owner = "the only task that reaches it", so a driver can land under a
  task that is merely its only caller found (e.g. `dd_hdmac` under INTRCAP). Message-loop dispatch through
  tables more than one pointer deep is not followed.
- `DP2QCalleeHints.java`: unnamed functions whose ≥ 2 named callees all share one module prefix get a
  comment `module hint: <prefix> (calls …)`; no renames. Master: 151.
- `tools/ghidra_pipeline.sh <image> <src> <len> [heap]` runs import → data marking → analysis → Thumb
  pointers → naming dry run for one image (master `0x40C40628 0x79C8`, loader `0x40C304F8 0x791C`).

### Master vs loader

```
$G "$PWD" dp2q_<image> -process -noanalysis -readOnly -scriptPath $T/ghidra_scripts -postScript DP2QExportFuncs.java funcs_<image>.tsv
python3 -I $T/tools/compare_images.py funcs_master.tsv funcs_loader.tsv [--list]
```

Matches by name, masked bytes, then instruction sequence with immediates removed. Findings in
[`notes/FIRMWARE_MAP.md`](notes/FIRMWARE_MAP.md) §2.

### Decompiling specific functions

```
$G "$PWD" dp2q_master -process -noanalysis -readOnly -scriptPath $T/ghidra_scripts \
   -postScript DP2QDecomp.java 0x40000088 str:GetBootMode some_name "out=$PWD/decomp/x.c"
```

Arguments: addresses, function names, or `str:<text>` (every function referencing a string containing it).

### Data extraction

```
python3 -I sigma_dp2q/tools/extract_strings.py     # UI messages, 17 languages -> out_dp2q/extract/strings/
python3 -I sigma_dp2q/tools/extract_icons.py       # 797 icons -> out_dp2q/extract/icons/ (needs Pillow)
python3 -I sigma_dp2q/tools/extract_camf.py        # CAMF records + X3F/X3I/DNG templates -> out_dp2q/extract/formats/
python3 -I sigma_dp2q/tools/extract_curves.py      # tone/gamma curves -> out_dp2q/extract/curves/ (numpy, Pillow)
python3 -I sigma_dp2q/tools/extract_images.py      # embedded JPEG/BMP (none on 2.03)
```

Formats and addresses: [`notes/FIRMWARE_MAP.md`](notes/FIRMWARE_MAP.md) §9.
