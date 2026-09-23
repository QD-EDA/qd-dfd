# Retained DMI permission: bounded evidence, replay UNKNOWN

OpenTitan `rv_dm_dmi_gate` retains debug permission so a debug session can survive
a lifecycle-controller reset. Its comments and assertions require strap sampling
with strict debug-enable On, then revocation when debug-clear, lifecycle-check
bypass or escalation is anything other than strict Off. The upstream
`lc_ctrl/doc/interfaces.md` describes the debug-clear obligation. These are
pinned source contracts, not design-owner approval of this harness.

## Scope and property

OpenTitan pin: `7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`. The real
`rv_dm_dmi_gate` and generic primitives are elaborated, including lifecycle
synchronizers, hardened OR and sender flop. FuseSoC's RV_DM default target
resolves 190 source entries with explicit `lowrisc:prim_generic:all:0.1` and
`lowrisc:systems:top_earlgrey:0.1` mappings. No RTL is copied into replacement
modules, no application sources are patched, and no modules are stubbed.

The external harness observes `dut.dmi_en`. Its separate Boolean reference
samples the four lifecycle controls through two stages. Permission then becomes
`(previous permission OR (strap AND enable == On)) AND clear == Off AND
bypass == Off AND escalation == Off`. Exact encodings are On=5, Off=10.
Reset initializes all control stages to Off and permission to false.

Yosys SAT checks ten steps with reset asserted at step one and released
thereafter. Strap and all four binary 4-bit controls are otherwise arbitrary.
No counterexample is found. Three covers first acquire permission, then retain
it after live enable drops without a new strap, then revoke it with an invalid
zero encoding on each of debug-clear, bypass and escalation separately. A
QD-only forced observed grant produces a counterexample. All four witnesses
are emitted as WaveJSON and binary vectors. These are solver outcomes, not
independently verified simulation traces.

## Reproduction

Use an environment with FuseSoC 2.4.5, Edalize 0.6.3 and their PyYAML dependency,
plus Yosys with read_slang and Verilator on PATH:

```sh
python3 -m unittest -v
/usr/bin/python3 -m unittest -v
python3 run_opentitan_dmi_formal.py /path/to/clean/opentitan /tmp/new-dmi-evidence
```

The last command currently returns **2 (UNKNOWN)**. Existing output directories
are rejected to preserve evidence. Other unrecognized tool failures return 1.
All commands, exit statuses, elapsed times, tool banners, source/header hashes,
EDAM, solver scripts and raw logs are retained. Hashes cover declared EDAM files
and QD harness/runner files, not a verified frontend include closure.

Local versions: Python 3.13.15 for the FuseSoC environment; Python 3.14.7 and
3.9.6 each pass all 14 existing VCD tests. Yosys is 0.68+80 `621d943ac-dirty`;
bundled read_slang provenance is unestablished. Both Verilator 5.050 and
5.051 development `v5.050-196-g7dcd4e0b6 (mod)` stop with UNOPTFLAT at
`tlul_lc_gate.sv:69`, reporting the `tl_h2d_int` array as circular combinational
logic. The runner preserves this failure and marks every unavailable replay
UNKNOWN. It does not disable the warning or change fatal-warning behavior.
The corrupted-witness replay check is also unexecuted while builds are blocked.
Local evidence is under `../evidence/dfd-dmi/`; it is not a release archive.

## Limits

The full gate elaborates, but unused logic is pruned from the SAT cone. TL-UL
inputs are idle, DMI readiness/responses are tied inactive, and transaction
forwarding, response draining, integrity and access to debug registers are
unverified. The test-chip volatile strap override is disabled. This is not
a composed proof with the lifecycle FSM, secondary live TAP gating, downstream
register visibility or trace availability. No legal strap timing, physical CDC,
metastability, mid-cycle reset, X/Z or unbounded reachability claim is made.
Upstream assertion macros use their dummy synthesis/simulator configuration;
the external property supplies these checks. Independent replay and mapped
technology evidence are still missing. Default CI runs the Python regressions,
not this optional toolchain. The retained-permission property is useful bounded
evidence, but does not qualify the debug architecture for production.
