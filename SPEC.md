# QD-DFD v0 scope

Build an executable design-for-debug policy checker for VCD traces. Target Caliptra-style debug/JTAG lock behavior without modifying released RTL. This validates observed traces only; it does not prove all states or replace secure debug signoff.

CLI: `qd-dfd check trace.vcd --policy policy.json [--json]`. Policy names exact hierarchical VCD signals for reset, debug lock, debug request/grant or enable, and optional lifecycle state. Require the policy to state forbidden combinations and required exercise (e.g. one locked request and one unlocked grant). Parse times and 0/1/X/Z values correctly, including same-timestamp changes, and fail on a forbidden grant, missing signal, unknown value at a decisive check, or vacuous trace that never exercises required cases. Emit timestamp, signal values, and deterministic diagnostics. Do not infer security from a passing trace.

Tests: allowed unlocked access, denied locked request, forbidden locked grant, missing hierarchy, X/Z boundary, same-timestamp ordering, and vacuity. Use standard library. If practical, document how to generate a Verilator VCD for the pinned Caliptra release; do not alter the release. Add README, Apache-2.0 license, and test command. Own only this repo; no commit/push/remote creation.
