# Encoded lifecycle trace evidence

QD-DFD now accepts explicit per-role vector widths while retaining scalar policy
defaults. This is a trace-analysis milestone toward the full hardware debug
analysis/insertion product; it is not a reachable-state or architecture proof.

## Named source and independent expectations

OpenTitan SHA `7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19` defines
`lc_ctrl_pkg::lc_tx_t` as four bits: On=`0101`, Off=`1010`
(`hw/ip/lc_ctrl/rtl/lc_ctrl_pkg.sv:60`). Its
`lc_tx_test_true_strict` function compares the input to On (line 141).
These are not ordinary booleans; nonzero values must not all become grants.

The QD-owned harness calls that actual function from the unmodified package,
with its real utility, multibit, state and register package dependencies. It
enumerates all 16 two-state inputs and independently requires a true output
only for integer 5. The policy separately requires every encoding's expected
grant and forbids its opposite. The `lock` role is a legacy policy-role name
for the encoded input, not an inferred lock signal from the application.

The positive trace passes with no diagnostics. `+BAD_GRANT` changes only the
QD harness's observed grant at encoding `0000`; QD-DFD reports a forbidden
combination at raw VCD timestamp 1000 (1 ns with the emitted 1 ps timescale),
plus an unexercised required clause. The original application source and package
function are never changed. Initial trace binding used an incorrect TOP prefix;
the checked-in policy uses exact declarations inspected in the generated VCD.

## Reproduce

```sh
python3 -m unittest -v
./run_opentitan_decode.sh /path/to/opentitan /tmp/qd-dfd-decode
```

The runner rejects a dirty or wrong-revision checkout. It records ordered source
hashes (including assertion headers), exact compiler argv, version, build output,
both simulation logs/traces and reports. It checks positive exit 0 and negative
exit 1 with a specific forbidden finding, so an input error cannot count as
successful fault detection. No RTL warning suppression is supplied; Verilator
compilation was clean. The reported VCD values remain width-normalized binary
strings; source VCD is retained alongside reports.

Four-state VCD formatting was checked separately with Icarus/vvp 13.0 stable:

```sh
iverilog -g2012 -s tb -o /tmp/qd-vector.vvp fixtures/vector_trace.sv
# Run in separate output directories so vector.vcd files are retained:
vvp /tmp/qd-vector.vvp       # passing encoded transitions
vvp /tmp/qd-vector.vvp +X    # decisive partial X
vvp /tmp/qd-vector.vvp +Z    # decisive partial Z
```

The policy is the `POLICY` constant in `test_vectors.py`, using `tb.rst_n`,
`tb.lc` (width 4), `tb.req` and `tb.grant`. Export it as JSON, then run
`./qd-dfd check vector.vcd --policy policy.json --json`. The normal trace exits
0; X/Z traces exit 1 with `unknown` findings. This fixture tests VCD semantics,
not OpenTitan's four-state behavior.

## Regression and observed performance

All 14 Python tests pass on Python 3.9.6 and 3.14.7 (seven original, seven new).
Cases cover declared-width matching, shortened binary zero/X/Z extension,
partial-known mismatches, missing initialization, selected aliases, final-value
timestamp semantics, invalid policy/value forms, and the 4096-bit upper bound.
Expected values cannot contain unknowns; invalid lifecycle encodings require
explicit policy clauses rather than implicit assumptions.

Native pilot simulator: Verilator 5.050 (`2026-07-01 rev vUNKNOWN-built20260701`).
Host: macOS arm64. Five positive-trace CLI checks took 0.0290–0.0305 s, median
0.0294 s, including Python startup. This tiny trace does not establish the
roadmap's million-change runtime or memory target. Default CI exercises Python
regressions only; the simulator pilot is an additional local lane.

Raw evidence is local at `../evidence/dfd-vector-lifecycle/`, with manifest and
SHA-256 inventory. It is not yet published release evidence.

## What remains unknown

This tests only the package function, not `lc_ctrl_signal_decode`, lifecycle
transitions, JTAG/register access, actual debug locks, trace infrastructure or
DFD insertion. Verilator's two-state run cannot prove X/Z behavior. Upstream
`prim_assert.sv` selects dummy concurrent-assertion macros under VERILATOR;
those are unavailable, not passing checks. The harness's explicit immediate
truth-table checks run, but do not establish architecture assertions.

The VCD parser remains a bounded in-memory parser, not a complete VCD validator
or streaming implementation. No delta-order semantics, symbolic reachability,
independent formal engine, design-owner policy approval or full-chip scope is
claimed. A passing observed trace is never a production qualification claim.
