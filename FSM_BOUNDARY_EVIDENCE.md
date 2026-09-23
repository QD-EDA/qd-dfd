# Debug-enable and debug-clear FSM boundaries

The earlier pilot fixed IdleSt and observed only debug-enable. The current
runner checks the unchanged pinned OpenTitan decoder and generic sender flops
for arbitrary 16-bit binary FSM inputs at every step. DEV, PROD and PROD_END
remain the only selected lifecycle states. State-valid and all 16 binary
secrets encodings remain unconstrained.

## Property and architecture basis

The pinned `hw/ip/lc_ctrl/doc/interfaces.md` defines debug-clear as the control
that clears retained debug-enable outside lifecycle-controller reset. Its
`lc_ctrl_signal_decode.sv` specifies broadcast, post-transition, escalation and
invalid-state behavior; `lc_ctrl_pkg.sv` supplies the FSM encodings. The external
reference expects debug-enable On for valid DEV in a broadcasting FSM state.
Debug-clear is On outside ResetSt unless broadcasting with a valid selected
lifecycle state. Both outputs are registered; the property compares the previous
sampled inputs after reset history is established. Encodings are On=0101 and
Off=1010. This is an RTL-derived reference, not owner-approved independent policy.

The SAT query checks six steps, initially reset then released, including all
65,536 FSM bit patterns and arbitrary sequences under this environment. It
finds no counterexample. This does not prove that any such sequence is reachable
from the real lifecycle transition FSM or OTP implementation.

Two separate cover queries require debug On at step four then Off with clear
On at step five, using IdleSt at input step three and either PostTransSt or the
invalid zero encoding at step four. Both witnesses replay against unchanged RTL
in Verilator. Separate QD-only forced-grant and suppressed-clear faults must
produce counterexamples and replay successfully. Corrupting a cover witness's
expected output must fail its replay comparator. These are runnable positive,
negative and boundary checks in the pilot, independent of the Python VCD tests.

## Reproduce

```sh
python3 -m unittest -v
/usr/bin/python3 -m unittest -v
python3 run_opentitan_debug_formal.py /path/to/clean/opentitan /tmp/new-fsm-evidence
```

OpenTitan SHA: `7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`. The 14 existing
VCD tests pass on Python 3.14.7 and 3.9.6. Local pilot versions are Yosys
0.68+80 `621d943ac-dirty` and Verilator 5.050; bundled read_slang provenance
is not established. Solver scripts, exact commands, statuses, timings, input
hashes, witnesses and replay logs are retained in the selected evidence directory.
Local bundles are under `../evidence/dfd-fsm/`; they are not release archives.

## Still unknown

This is a bounded decoder-cone check, not full debug-access verification. It
does not include downstream retained-enable flops, TAP/register access, trace,
other lifecycle states, actual transition reachability, technology mapping or
DFD insertion. Two-state synthesis and Verilator replay do not establish X/Z,
metastability or analog reset timing. Upstream assertions remain unavailable in
these frontend configurations, as recorded in the earlier evidence. The default
CI runs Python tests only; the optional proof needs locally installed tools.
The runner returns zero for these specific checks, not production qualification.
