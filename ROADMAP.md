# QD-DFD: debug architecture analysis and design-for-debug implementation

## Intended product (scope clarified 2026-09-23)

QD-DFD will both analyze hardware debug architecture and implement design-for-debug by inserting the necessary design elements into RTL or netlists for an explicitly supported scope. Debug access, observation/trace, registers and lifecycle controls are design outputs, alongside structural and reachable-state verification. The current executable only checks observed VCD policy; insertion is not implemented today.

## Current capability

Baseline `28883fb7413e3e02452429d34b5c913fbb45bd3b`: seven Python tests;
CI runs `python3 -m unittest -v`. Scalar VCD observations are checked against
required and forbidden combinations with timestamp/X/Z/vacuity diagnostics.
It samples final values per timestamp, not delta ordering, and has no structural
or reachability proof. This is hardware design verification, not a generic
software security scanner or a secure-debug signoff product.

## Stages and interfaces

1. **Next useful slice:** width-aware lifecycle values and a reviewed architectural
   policy mapping. OpenTitan lifecycle enables are encoded multi-bit values;
   treating them as booleans is insufficient. Inputs: immutable RTL hierarchy,
   register map, policy and trace. Outputs: exercised/unexercised policy clauses,
   precise path/width/value/timestamp evidence and UNKNOWN for missing mappings.
   Preserve scalar policy compatibility and fail decisive X/Z observations.
2. **Pinned pilot:** OpenTitan `lc_ctrl` lifecycle decode and debug/TAP isolation
   cones, then Caliptra `soc_ifc` debug lock and JTAG integration. Enumerate real
   access paths, register visibility, lock states, test modes and trace outputs
   from each pinned architecture. Select a small cone and owner-reviewed reset/
   transition assumptions. Missing traces or signal mappings block the pilot;
   do not infer a lock policy from signal names alone.
3. **Structural and reachable evidence:** elaborate with an established frontend;
   connect lifecycle controls to every selected debug endpoint and identify
   bypass/test paths. Bind properties outside application RTL and run bounded
   model checking plus cover checks. Report bound, reset assumptions and reachable
   witnesses. Add induction only where proven; distinguish bounded-no-counterexample,
   unreachable exercise, counterexample, timeout and unbounded proof. Extend to
   register read/write visibility, lock persistence, test modes and trace enable
   transitions one architectural requirement at a time.
4. **DFD implementation:** consume an explicit debug architecture and endpoint
   selection; insert the required observation points, debug registers/access
   fabric, trigger/trace buffers and lifecycle/test-mode gating for that scope.
   Start with one reviewed observation/register block before wider debug fabrics.
   Emit separate derived RTL/netlists, register/interface descriptions, constraints
   and a source-linked insertion manifest. Preserve normal-mode functional
   behavior by equivalence checks under documented debug-disabled assumptions;
   prove access/lock/reset properties with debug enabled and replay witnesses in
   simulation. Check CDC/reset crossings introduced by debug infrastructure.
   Do not infer an access policy from signal names or insert unrestricted bypasses.
5. **Production qualification:** only the named lifecycle states, endpoints,
   register ranges, reset modes and properties in the qualified matrix. Require
   design-owner policy review, structural endpoint completeness and independently
   replayed counterexamples/covers. Analog attacks, debug timing side channels,
   unmodeled firmware and unbounded liveness remain outside the initial scope.
   Require both analyzer evidence and correct generated architecture: complete
   endpoint mapping, normal-mode equivalence, verified lifecycle access behavior,
   synthesizable outputs and area/timing/trace-capacity budgets. Analysis-only
   qualification does not complete the DFD product goal.

## Evidence and release criteria

- Inputs: RTL/netlist and source map, register descriptions, lifecycle policy,
  formal environment and optional VCD. Outputs: endpoint inventory, source-linked
  properties/assumptions, access matrix, proof status/bound, traces and vacuity
  report. Never collapse observed-trace PASS and reachable-state proof into one flag.
  Insertion also consumes the approved debug architecture and emits derived design
  sources/netlists, register maps, interfaces, constraints and transformation records.
- Corpus: existing seven tests plus lifecycle encodings/invalid states, lock
  transitions, resets during access, lifecycle escalation, omitted endpoints,
  test bypass, hidden registers, missing trace enable, vector X/Z, VCD aliases,
  no reachable required exercise and timeout. Faults belong in QD fixtures.
  Add original/transformed design pairs, lock/reset/trace faults in inserted
  structures, disabled-debug equivalence, repeated-insertion policy and interface
  integration regressions without changing golden application sources.
- Oracles: upstream lifecycle/access specifications, independently reviewed
  properties, another solver/engine, and four-state simulation of every generated
  witness. Agreement on an incorrectly constrained environment is not proof.
- Version matrix: Python 3.9/3.14; named SV frontend, synthesis/formal tool and
  two solver versions pinned before proof claims; four-state simulator for X/Z.
  Scalar VCD CLI remains a distinct supported lane until vector work qualifies.
- Targets: 1M trace changes <=30 s/512 MiB using streaming where needed; selected
  <=1k-flop cone bounded to 50 cycles <=10 min/4 GiB. Timeout is UNKNOWN, never pass.
  Initial insertion target: 1k selected observation endpoints <=60 s/2 GiB,
  excluding synthesis/proof time; report area, critical-path and trace-bandwidth
  costs against architecture-specific budgets agreed before qualification.
- Release: every selected endpoint and state appears in the policy matrix; every
  required cover has a witness; forbidden mutations are detected; no missing
  assumptions or unexplained independent-engine disagreements; two reproducible
  runs and owner approval. A passing VCD alone never earns qualification.

## Qualification contract

This is a staged plan, not a production qualification claim. No stage is earned
by a green unit suite alone. Keep existing passing behavior and raw diagnostics.
Preserve the immutable application RTL/DV inputs. Intentional DFT/DFD insertion
is authorized product work: emit a separate derived design with an explicit
transformation manifest. Never edit the golden inputs, disable assertions or
introduce dummy VIP merely to manufacture a passing pilot. A failed pilot is an artifact to retain, not a test to remove.

Named pilot pins (full SHAs, never floating branches):
- Caliptra RTL v2.1.2: `49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e`, generic simulation primitives;
  Adams Bridge v2.0.3: `b77e3d899e828d626cfc2a0d26a6b5704cc121e0` when needed.
- OpenTitan: `7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`; select the named IP fileset, generic technology,
  and record all FuseSoC flags, parameters, generated files, and their digests.
  The later configuration-blocker evidence at `a78922f14a8cc20c7ee569f322a04626f2ac6127`
  is a separate revision, not interchangeable qualification evidence.

Every release candidate needs an immutable evidence bundle: tool Git SHA and
binary hashes; OS/architecture, Python/compiler/simulator/solver versions;
design and submodule SHAs; top, parameters, defines, ordered files/includes,
constraints, libraries, seeds; input/output hashes; exact argv, raw stdout/stderr,
exit codes, wall time and peak RSS. Repeat twice in clean independent workspaces;
compare canonical findings and explain any nondeterminism. Archive the bundle
with the release and publish a supported/unsupported configuration table.

Review every expected finding and every oracle disagreement. Seed known defects
in separate test fixtures and require their detection; never alter golden pilot RTL to manufacture a pass. Derived insertion outputs
are permitted and must be verified against the golden input and approved policy.
Unknowns and exclusions remain counted and visible. Waivers require a stable
finding/configuration identity, owner, independent reviewer, rationale, evidence
hash/link, expiry, and revalidation on any relevant input change. A waiver is a
review disposition, not a proof. No unreviewed waiver or unexplained oracle
mismatch is allowed in the qualified scope. Outside that scope report UNKNOWN
or a clear unsupported error. A version or dependency change reopens qualification.

Performance numbers below are acceptance targets, not measurements. Measure on
a named Linux x86-64 runner with 8 cores and 16 GiB RAM; record hardware and
median of five runs. No automatic threshold relaxation. macOS arm64 is a second
portability lane, not a substitute for the qualification runner.

## Portfolio priority and real-flow blockers

1. **QD-Lint first:** source/configuration fidelity is prerequisite evidence for
   every downstream analysis. OpenTitan pinmux's conditional `fileset_ip` versus
   `fileset_top` selects different register packages. A local pinned matrix probe
   at `a78922f...` reproduced an omitted-package failure from wrong setup flags;
   it was not an RTL defect. Caliptra's generic/technology primitive roots also
   select different sources. Audit these choices before caching or baselining.
2. **QD-BFM second:** Caliptra's README requires licensed Avery AXI and QVIP AHB
   dependencies in full UVMF flows. A bounded independent AXI adapter is useful,
   but cannot cure simulator/UVM/firmware dependencies or replace their APIs.
3. **QD-CDC, then QD-DFD:** real reset/synchronizer and lifecycle/debug cones are
   available; getting complete elaboration and constraints is the next blocker.
   VCD observations and cell annotations cannot establish safety on their own.
4. **QD-UPF and QD-DFT:** do standards/library/topology inventory now; owner-approved
   power intent and scan-mapped collateral are unverified. Do not invent these
   inputs or mistake lack of collateral for a demonstrated design failure.

Primary source anchors (review pinned source, not just current web documentation):
- [Caliptra dependency and configuration README](https://github.com/chipsalliance/caliptra-rtl/blob/49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e/README.md).
- [OpenTitan pinmux fileset selection](https://github.com/lowRISC/opentitan/blob/a78922f14a8cc20c7ee569f322a04626f2ac6127/hw/ip/pinmux/pinmux_reg.core).
- [OpenTitan lifecycle architecture](https://github.com/lowRISC/opentitan/tree/7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19/hw/ip/lc_ctrl/doc).
- [OpenTitan TL DV agent](https://github.com/lowRISC/opentitan/tree/7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19/hw/dv/sv/tl_agent).
