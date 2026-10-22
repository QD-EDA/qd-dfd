# qd-dfd

Checks a **debug-lock policy against a VCD waveform**. It checks only the trace you give it; it cannot prove all reachable states and is not secure-debug signoff.

| | |
|---|---|
| Language | Python 3 (standard library only) |
| Input | `trace.vcd` + `policy.json` |
| Status | Active prototype (Sep 2026) |
| License | Apache-2.0 |

## How it works

A policy names four signal roles (`reset`, `lock`, `request`, `grant`, plus optional extras) by exact VCD hierarchy path, then lists clauses of expected one-bit values:

| List | Meaning | Fails when |
|---|---|---|
| `forbidden` | states that must never be seen (e.g. locked and granted) | any clause matches |
| `required` | states the trace must exercise (e.g. locked request denied) | a clause never matches |

Missing signals, X/Z values that decide a clause, and malformed input also fail. Same-timestamp updates are applied in file order and checked once.

## Run

```sh
./qd-dfd check trace.vcd --policy policy.json --json
python3 -m unittest -v
```

| Exit | Meaning |
|---|---|
| 0 | trace passes |
| 1 | policy violation, or malformed/missing VCD or policy |
| 2 | command-line usage error |

A complete worked example (policy, tiny trace, optional bounded proof, DMI pilot) is in [docs/usage.md](docs/usage.md). To get a trace from Verilator, build with `--trace` and have the harness call `$dumpfile`/`$dumpvars`.
