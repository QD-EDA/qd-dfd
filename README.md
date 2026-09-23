# QD-DFD

QD-DFD checks observed debug-lock behavior in a VCD trace. It is a trace policy
checker, not a proof of all reachable states or a replacement for secure debug
signoff. A passing trace only means that this trace met the selected policy.

## Run

```sh
./qd-dfd check trace.vcd --policy policy.json
./qd-dfd check trace.vcd --policy policy.json --json
python3 -m unittest -v
```

The checker uses only Python's standard library. It returns 0 for a passing
trace and 1 for policy violations or invalid inputs.

## Policy

Paths are exact, case-sensitive VCD hierarchy names. `grant` may name a grant
signal or the effective debug enable. Optional roles such as `lifecycle` can
be added and referenced by clauses. Clause expectations are one-bit `0` or
`1`; an observed `X` or `Z` at a decisive check is an error.

```json
{
  "signals": {
    "reset": "tb.rst_n",
    "lock": "tb.debug_locked",
    "request": "tb.debug_request",
    "grant": "tb.debug_grant",
    "lifecycle": "tb.lc_state"
  },
  "forbidden": [
    {"when": {"reset": "1", "lock": "1", "grant": "1"}}
  ],
  "required": [
    {"when": {"reset": "1", "lock": "1", "request": "1", "grant": "0"}},
    {"when": {"reset": "1", "lock": "0", "grant": "1"}}
  ]
}
```

Each required clause must match at least one sampled timestamp. An unknown
value is an error when the other known fields still allow the clause to match.
VCD updates sharing a timestamp are applied in file order and checked once,
after the final update at that timestamp; intermediate delta ordering is not
treated as a separate hardware cycle. Timestamps are reported in the raw VCD
time units.

## Verilator traces

For a pinned Caliptra checkout, use its existing simulation sources and
testbench without editing the release. Compile the testbench with Verilator
tracing enabled (commonly `--trace`) and have the harness call `$dumpfile` and
`$dumpvars` to write the VCD. Then copy the exact hierarchy names from that VCD
into the policy. Harness and top-module commands vary by release and testbench.
