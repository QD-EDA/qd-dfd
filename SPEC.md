# Product scope

QD-DFD will both analyze hardware debug architecture and implement design-for-debug by inserting the necessary design elements into RTL or netlists for an explicitly supported scope. Debug access, observation/trace, registers and lifecycle controls are design outputs, alongside structural and reachable-state verification. The current executable only checks observed VCD policy; insertion is not implemented today.

The historical v0 specification below describes the existing prototype, not a limit on the intended product. The staged implementation and qualification contract is in ROADMAP.md.

# QD-DFD v0 scope

Build an executable design-for-debug policy checker for VCD traces. Target Caliptra-style debug/JTAG lock behavior without modifying released RTL. This validates observed traces only; it does not prove all states or replace secure debug signoff.

CLI: `qd-dfd check trace.vcd --policy policy.json [--json]`. Policy names exact hierarchical VCD signals for reset, debug lock, debug request/grant or enable, and optional lifecycle state. Require the policy to state forbidden combinations and required exercise (e.g. one locked request and one unlocked grant). Parse times and 0/1/X/Z values correctly, including same-timestamp changes, and fail on a forbidden grant, missing signal, unknown value at a decisive check, or vacuous trace that never exercises required cases. Emit timestamp, signal values, and deterministic diagnostics. Do not infer security from a passing trace.

Tests: allowed unlocked access, denied locked request, forbidden locked grant, missing hierarchy, X/Z boundary, same-timestamp ordering, and vacuity. Use standard library. If practical, document how to generate a Verilator VCD for the pinned Caliptra release; do not alter the release. Add README, Apache-2.0 license, and test command. Own only this repo; no commit/push/remote creation.

## Encoded lifecycle trace slice

Add optional per-role widths (1–4096, default 1). Require exact VCD declaration
widths and full-width 0/1 expected strings. Normalize shortened VCD binary values
without treating X/Z as zero, enforce alias width consistency, and evaluate
partial unknowns bitwise. Preserve scalar policy behavior and final-value-per-
timestamp sampling. Validate a pinned OpenTitan strict lifecycle decode function
with all 16 inputs, independent expected truth table and a QD-only injected fault.
Do not claim full lifecycle/debug access verification from the function trace.

## Selected hardware-cone bounded pilot

The optional OpenTitan pilot checks six sequential steps of the real registered
hardware-debug enable for freely selected DEV/PROD/PROD_END states, arbitrary
binary validity/secrets inputs, IdleSt FSM and an initial reset. Require a
non-vacuous On/Off witness, a QD-only grant-fault counterexample, simulation
replay of both witnesses and rejection of a corrupted replay expectation.
Preserve the VCD CLI and application RTL. See LIFECYCLE_FORMAL_EVIDENCE.md for
model limits, including unavailable upstream assertions and two-state semantics.
