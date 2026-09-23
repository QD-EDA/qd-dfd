#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ot=$(cd "${1:?usage: run_opentitan_decode.sh OPENTITAN_ROOT EVIDENCE_DIR}" && pwd)
mkdir -p "${2:?provide an evidence directory}"
out=$(cd "$2" && pwd)
if [[ $(git -C "$ot" rev-parse HEAD) != 7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19 ]] ||
   [[ -n $(git -C "$ot" status --porcelain) ]]; then
  echo 'Expected clean pinned OpenTitan checkout' >&2; exit 1
fi
verilator --version | tee "$out/version.log"
sources=("$ot/hw/ip/prim/rtl/prim_util_pkg.sv" "$ot/hw/ip/prim/rtl/prim_mubi_pkg.sv"
  "$ot/hw/ip/lc_ctrl/rtl/lc_ctrl_state_pkg.sv" "$ot/hw/ip/lc_ctrl/rtl/lc_ctrl_reg_pkg.sv"
  "$ot/hw/ip/lc_ctrl/rtl/lc_ctrl_pkg.sv" fixtures/opentitan_lc_decode.sv)
command=(verilator --binary --timing --trace --assert --top-module opentitan_lc_decode
  --timescale 1ns/1ps --Mdir "$out/obj" "+incdir+$ot/hw/ip/prim/rtl" "${sources[@]}")
printf '%q ' "${command[@]}" > "$out/command.txt"
printf '\n' >> "$out/command.txt"
shasum -a 256 "${sources[@]}" "$ot"/hw/ip/prim/rtl/prim_assert* qd-dfd \
  fixtures/opentitan_lc_decode.policy.json > "$out/inputs.sha256"
"${command[@]}" > "$out/build.log" 2>&1 || { cat "$out/build.log"; exit 1; }
for mode in good bad; do
  mkdir -p "$out/$mode"
  args=()
  if [[ $mode == bad ]]; then args=(+BAD_GRANT); fi
  (cd "$out/$mode"; "$out/obj/Vopentitan_lc_decode" "${args[@]}") > "$out/$mode/simulation.log" 2>&1
  status=0
  python3 qd-dfd check "$out/$mode/lc_decode.vcd" --policy fixtures/opentitan_lc_decode.policy.json \
    --json > "$out/$mode/report.json" || status=$?
  if [[ $mode == good ]]; then
    [[ $status == 0 ]]
  else
    [[ $status == 1 ]]
    python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); assert any(d["kind"]=="forbidden" for d in r["diagnostics"])' "$out/$mode/report.json"
  fi
done
echo 'PASS: 16 OpenTitan strict decode encodings observed; injected grant rejected'
