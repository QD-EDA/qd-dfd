# QD-DFD

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

Policy signal paths are exact, case-sensitive, scalar VCD hierarchy names. `reset`, `lock`, `request`, and `grant` are required roles; additional roles such as lifecycle state may be named and referenced by clauses. `forbidden` and `required` are non-empty lists of clauses with expected one-bit values `0` or `1`. Each required clause must match at least one sampled timestamp. Any forbidden match, missing signal, decisive X/Z value, malformed input, or unexercised required clause fails the check. Unknown values are errors only when the other known clause fields still allow it to match.

Updates sharing a timestamp are applied in file order and checked once after the final update at that time; intermediate delta ordering is not modeled. Reported timestamps use raw VCD time units. Text output prints PASS/FAIL findings; `--json` prints `passed` and a deterministic diagnostics array with timestamps and observed signal values.

Exit codes: `0` for a passing trace; `1` for policy violations, malformed/missing VCD or policy input; `2` for command-line usage errors. To use a Verilator trace, compile the existing design/testbench with tracing enabled (commonly `--trace`) and have its harness call `$dumpfile` and `$dumpvars`; copy exact hierarchy paths from that VCD into the policy. Harness commands vary by project and release. Generating a trace does not expand this check into exhaustive verification.

See [the staged qualification roadmap](ROADMAP.md) for named pilots, unsupported
cases, independent oracles, performance targets and release gates.
