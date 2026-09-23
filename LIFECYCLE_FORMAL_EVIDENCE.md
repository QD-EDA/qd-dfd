# OpenTitan debug-enable bounded proof

Historical initial slice: the current runner extends this scope as described in
[FSM boundary evidence](FSM_BOUNDARY_EVIDENCE.md). The Idle-only results below
record the original pilot.

This optional pilot checks the unchanged `lc_ctrl_signal_decode` hardware and its
real generic sender flops at OpenTitan commit
`7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`. It does not change the VCD checker.
It is not production qualification or secure-debug signoff.

## Reproduce

```sh
python3 run_opentitan_debug_formal.py /path/to/clean/opentitan /tmp/qd-dfd-formal
python3 -m unittest -v
/usr/bin/python3 -m unittest -v
```

The runner requires a clean pinned checkout, Yosys with `read_slang`, and Verilator.
This pilot accepts paths containing only letters, digits, `_ . / : + -` because
`read_slang` does not remove Yosys command-file quotes. Each tool invocation has
a 120-second timeout. Tool failures, warnings, missing outcomes and mismatched
witnesses fail the run. Existing evidence files are overwritten; use a fresh
output directory for each run.

## What the property establishes

The external QD harness selects DEV, PROD or PROD_END, holds the decoder FSM input
at IdleSt, and permits arbitrary binary state-valid and four-bit secrets-valid
inputs on every step. Reset is asserted at step one and released thereafter.
Six discrete sequential steps are checked. After reset history is established,
the registered hardware-debug enable must equal encoded On (`0101`) exactly when
the previous sampled inputs were valid DEV; otherwise it must equal Off (`1010`).
The expected result is a separate one-cycle reference in the QD harness.

Positive evidence: SAT finds no counterexample within the bound. Boundary
coverage includes invalid state-valid gating, both production states, all binary
secrets encodings, and arbitrary changes among these selected inputs. A separate
cover query reaches On at step four and Off at step five, avoiding an always-Off
vacuous success. A negative harness forces the observed grant On and must produce
a counterexample. Neither fault changes application RTL.

Both the cover witness and fault counterexample are replayed against the same
unchanged RTL using Verilator, comparing debug output and the property violation
at every step. A deliberately corrupted expected output must fail this replay at
step one. SAT states are compared before each replay clock edge; the simulator
then supplies the edge represented by the sequential SAT transition.

## Limits and unknowns

This is bounded model checking of a selected output cone, not induction or a
proof of all reachable chip states. Lifecycle state inputs are freely chosen;
the real lifecycle transition FSM, OTP storage, debug requests, JTAG, lock
registers, downstream access enforcement and trace paths are outside the model.
Other decoder outputs are unobserved and may be pruned. No DFD insertion occurs.

Yosys uses its normal synthesis frontend configuration (including SYNTHESIS),
and Verilator defines VERILATOR. Upstream assertion macros select their dummy
implementation under these configurations; those assertions are **not checked**.
The external property and replay comparisons supply this pilot's checks.
`async2sync` provides a discrete clock model: analog reset timing, metastability,
clock relationships, four-state behavior and arbitrary mid-cycle reset are not
proved. Generic flops do not qualify any mapped technology library.

## Evidence and versions

Validated locally with Python 3.14.7 and Apple Python 3.9.6 (14 existing tests each),
Yosys 0.68+80 (`621d943ac-dirty`, installed OSS CAD Suite build), and Verilator
5.050. The dirty development Yosys build limits reproducibility; its exact source
build is not claimed to be recoverable from the version string. Default CI runs
the Python suite only, not this optional installed-tool pilot.

The evidence directory contains tool version logs, generated Yosys scripts,
solver logs, WaveJSON witnesses, replay vectors, build/replay logs, input hashes
and `commands.json` with exact argv, exit status and elapsed seconds. Hashes cover
the explicitly listed RTL and assertion headers, not a proven include closure.
Local validation artifacts live outside the repository at
`../evidence/dfd-lifecycle-formal/`; these are not published release artifacts.
There is no production performance gate yet; timings are measurements on the
local host, not a scalability guarantee. Owner-reviewed architecture policy,
unbounded reasoning, broader configurations, pinned reproducible tool builds
and release evidence remain required by the roadmap.

One local run measured 0.085 s for the bounded proof, 0.087 s for cover and
0.044 s for the fault query; each replay build took about 2.72 s and each
successful replay about 0.03 s. Peak memory was not measured by the runner.

A fresh local clone of commit `acf9731` repeated all three SAT outcomes, both
successful witness replays, the corrupted-expectation rejection, and all 14
Python regressions. This checks workspace independence on the same host and
installed tools; it is not an independent toolchain rebuild.
