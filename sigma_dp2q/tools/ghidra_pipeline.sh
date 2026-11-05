#!/bin/bash
# Full headless Ghidra pipeline for one dp2q image, from scratch:
#   seeds -> import + setup + extra seeds (call targets, pointer-referenced prologues) + task-table
#   pointers + repetitive-data marking -> analyse (repeated until it converges) ->
#   Thumb pointer refs -> names (dry csv, then apply) -> manual renames -> task ownership -> module hints
# Run from the repo root. Refuses to overwrite an existing project.
# usage: sigma_dp2q/tools/ghidra_pipeline.sh <master|loader> <ram_cfg_src> <ram_cfg_len> [heap]
#   2.03: master 0x40C40628 0x79C8, loader 0x40C304F8 0x791C
set -euo pipefail
name=$1; src=$2; len=$3; heap=${4:-16G}
R=$(pwd); T=$R/sigma_dp2q; S=$T/ghidra_scripts; O=$R/out_dp2q/ghidra
G=~/tools/ghidra_12.2_PUBLIC/support/analyzeHeadless; PY=$R/projects/fpl-port/.venv/bin/python
P=dp2q_$name
mkdir -p "$O"; cd "$O"
[ -e "$P.gpr" ] && { echo "$O/$P.gpr exists; move it away first"; exit 1; }
step() { echo "== $(date +%T) $1"; }
run() { GHIDRA_HEADLESS_MAXMEM=$heap $G "$O" $P "$@" -scriptPath $S -log "$O/pipe_$name.log" > /dev/null; }
$PY -I $T/tools/ghidra_seeds.py $name > seeds_$name.csv
$PY -I $T/tools/ghidra_more_seeds.py $name seeds_$name.csv > more_seeds_$name.csv
$PY -I $T/tools/data_regions.py $name > data_regions_$name.csv
# known fixes (addr,name,comment); the cfg routine is at the same runtime address in both 2.03 images
printf '%s\n' "0x01000984,cfg_create_kernel_objects,creates the static kernel objects from the tables in ram_cfg (mailboxes, 50 tasks via tk_cre_tsk, ...)" > renames_$name.csv
step import
run -import "$R/out_dp2q/${name}_40000000.bin" -loader BinaryLoader -loader-baseAddr 0x40000000 \
    -processor ARM:LE:32:v7 -noanalysis \
    -preScript DP2QSetup.java "$O/seeds_$name.csv" $src $len \
    -postScript DP2QSeeds.java "$O/more_seeds_$name.csv" \
    -postScript DP2QData.java "$O/data_regions_$name.csv"
# analysis does not converge in one pass: functions reached through pointers resolved in pass N show up
# in pass N+1 (master 2.03: 14,860 -> 15,074 -> 15,122 -> 15,142). Repeat until a pass adds < 20, max 6.
prev=0
for pass in 1 2 3 4 5 6; do
  step "analyse pass $pass"
  cnt=$(GHIDRA_HEADLESS_MAXMEM=$heap $G "$O" $P -process -scriptPath $S -postScript DP2QCount.java \
        -log "$O/pipe_$name.log" 2>&1 | sed -n 's/.*dp2q count: \([0-9]*\).*/\1/p')
  echo "   functions: $cnt"
  [ -n "$cnt" ] || { echo "no count from pass $pass"; exit 1; }
  [ $((cnt - prev)) -lt 20 ] && break
  prev=$cnt
done
step "names, ownership, hints"
run -process -noanalysis -preScript DP2QThumbPtrRefs.java \
    -postScript DP2QNameFromStrings.java dry "$O/names_dry_$name.csv" \
    -postScript DP2QNameFromStrings.java apply "$O/names_applied_$name.csv" \
    -postScript DP2QRename.java "$O/renames_$name.csv" \
    -postScript DP2QTaskOwner.java apply "$O/owner_$name.csv" 12 \
    -postScript DP2QCalleeHints.java apply "$O/hints_$name.csv" \
    -postScript DP2QReport.java
step done
grep -E "\.java> " "$O/pipe_$name.log" | sed 's/.*java> //; s/ (GhidraScript)//'
