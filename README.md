# QD-DFD

## Product direction

QD-DFD will both analyze hardware debug architecture and implement design-for-debug by inserting the necessary design elements into RTL or netlists for an explicitly supported scope. Debug access, observation/trace, registers and lifecycle controls are design outputs, alongside structural and reachable-state verification. The current executable only checks observed VCD policy; insertion is not implemented today.

## Current prototype

`qd-dfd` checks debug-lock policy against values observed in a VCD trace. It checks the supplied trace only; it cannot prove all reachable states or replace secure-debug signoff. A pass means only that the trace exercised the required policy clauses without observing a forbidden one.

## Requirements and quick start

Python 3 is required. This self-contained example writes a policy and a tiny trace, then checks them:

```sh
tmp=$(mktemp -d)
cat > "$tmp/policy.json" <<'EOF'
{"signals":{"reset":"tb.rst_n","lock":"tb.locked","request":"tb.dbg_req","grant":"tb.dbg_grant"},"forbidden":[{"when":{"reset":"1","lock":"1","grant":"1"}}],"required":[{"when":{"reset":"1","lock":"1","request":"1","grant":"0"}},{"when":{"reset":"1","lock":"0","grant":"1"}}]}
EOF
cat > "$tmp/trace.vcd" <<'EOF'
$scope module tb $end
$var wire 1 ! rst_n $end
$var wire 1 " locked $end
$var wire 1 # dbg_req $end
$var wire 1 $ dbg_grant $end
$upscope $end
$enddefinitions $end
#0
0! 0" 0# 0$
#5
1! 1" 1# 0$
#10
0" 0# 1$
EOF
./qd-dfd check "$tmp/trace.vcd" --policy "$tmp/policy.json" --json
python3 -m unittest -v
```

Policy signal paths are exact, case-sensitive VCD hierarchy names; widths default to one bit. `reset`, `lock`, `request`, and `grant` are required roles; additional roles such as lifecycle state may be named and referenced by clauses. `forbidden` and `required` are non-empty lists of clauses with expected binary strings (`0`/`1` bits) of the declared width. Each required clause must match at least one sampled timestamp. Any forbidden match, missing signal, decisive X/Z value, malformed input, or unexercised required clause fails the check. Unknown values are errors only when the other known clause fields still allow it to match.

Updates sharing a timestamp are applied in file order and checked once after the final update at that time; intermediate delta ordering is not modeled. Reported timestamps use raw VCD time units. Text output prints PASS/FAIL findings; `--json` prints `passed` and a deterministic diagnostics array with timestamps and observed signal values.

Exit codes: `0` for a passing trace; `1` for policy violations, malformed/missing VCD or policy input; `2` for command-line usage errors. To use a Verilator trace, compile the existing design/testbench with tracing enabled (commonly `--trace`) and have its harness call `$dumpfile` and `$dumpvars`; copy exact hierarchy paths from that VCD into the policy. Harness commands vary by project and release. Generating a trace does not expand this check into exhaustive verification.

## Encoded lifecycle signals

Add a `widths` object keyed by signal role, for example `"widths": {"lock": 4}`.
Omitted roles remain scalar. Supported widths are integers 1–4096 and must match
the VCD declarations exactly. Expected clause values are full-width binary
strings, such as `"0101"`; X/Z, wildcards and implicit policy-value extension
are rejected. A vector's path names the whole declaration, not an arbitrary slice.

VCD binary updates may omit leading zeroes or repeated leading X/Z bits; the
checker restores the declared width. It rejects oversized values, scalar updates
to vectors and inconsistent selected alias widths. Missing initialization is X
at every bit. A partial X/Z value is decisive only when all its known bits and
the other clause fields could match. A known mismatch makes that clause false.
The checker does not automatically classify an unlisted encoding as invalid:
the policy must explicitly cover invalid encodings and their required behavior.

`fixtures/opentitan_lc_decode.policy.json` checks all 16 inputs of OpenTitan's
four-bit strict lifecycle decoder. Reproduce the bounded package-function pilot:

```sh
./run_opentitan_decode.sh /path/to/clean/opentitan /tmp/qd-dfd-opentitan
```

The checkout must be `7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`. The harness
compiles the real packages, checks the function's truth table, generates VCD,
and requires rejection of a QD-harness grant fault. The legacy `lock` role names
the encoded input in this fixture; it is not a claim about a real lock register.
[Evidence](VECTOR_EVIDENCE.md) records versions and limits. Default CI covers
Python regressions; it does not run the optional simulator pilot. Full lifecycle reachable-state
proof, debug-structure insertion and full-chip qualification remain roadmap work.

See [the staged qualification roadmap](ROADMAP.md) for named pilots, unsupported
cases, independent oracles, performance targets and release gates.

## Optional hardware bounded proof

`python3 run_opentitan_debug_formal.py /path/to/clean/opentitan /tmp/qd-dfd-formal`
checks six steps of the real OpenTitan lifecycle decoder's registered hardware
debug-enable output, with DEV/PROD/PROD_END inputs and arbitrary binary 16-bit FSM inputs.
It requires Yosys with `read_slang` and Verilator, covers post-transition and invalid-FSM debug clearing, rejects
an injected grant and suppressed clear, and independently replays SAT witnesses. See
[LIFECYCLE_FORMAL_EVIDENCE.md](LIFECYCLE_FORMAL_EVIDENCE.md) for the pinned design,
commands, assumptions and unsupported cases. This optional pilot is separate
from the VCD CLI and does not establish full lifecycle reachability or signoff.

The expanded FSM property and exact limits are documented in
[FSM boundary evidence](FSM_BOUNDARY_EVIDENCE.md).

`python3 run_opentitan_debug_endpoints.py ROOT REPORT.json` inventories the
pinned Earlgrey direct connections from `lc_hw_debug_en` and `lc_hw_debug_clr`
to selected consumer ports. Missing or newly added wiring remains UNKNOWN.
See [endpoint evidence](DEBUG_ENDPOINT_EVIDENCE.md); this is source inventory,
not hierarchy elaboration or an architecture proof.

## Retained DMI permission pilot

`python3 run_opentitan_dmi_formal.py OPENTITAN_ROOT NEW_EVIDENCE_DIR` resolves
the real RV_DM generic dependency set with FuseSoC 2.4.5 / Edalize 0.6.3 and checks
ten steps of its retained DMI permission. It needs PyYAML, Yosys with read_slang,
and Verilator. The observed Verilator UNOPTFLAT failure blocks witness replay:
this pilot returns 2 (UNKNOWN), preserving the diagnostic. Other errors return
1; zero would mean all scoped checks and replays completed, not qualification.
See [DMI evidence](DMI_PERMISSION_EVIDENCE.md) for commands, scope and blockers.
