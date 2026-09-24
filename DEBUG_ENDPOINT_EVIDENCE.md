# Earlgrey lifecycle debug endpoint inventory

`run_opentitan_debug_endpoints.py ROOT REPORT.json` checks direct named-port
connections in the pinned Earlgrey top, main power-domain wrapper and AON wrapper.
It requires a clean OpenTitan checkout at
`7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`. The report records each source path,
line and file SHA-256. Missing or changed connections and newly discovered direct
consumers are `UNKNOWN` until reviewed.
Reviewed instance types and named pins must each occur exactly once; a duplicate
pin or instance is UNKNOWN even if one copy still has the expected connection.

The observed path is `u_lc_ctrl.lc_hw_debug_en_o` to five main-domain consumers
(`u_pinmux`, `u_rv_dm`, `u_csrng`, `u_sram_ctrl_main`, `u_sram_ctrl_sec`), then
through the top-level `earlgrey_pd_main` output and `earlgrey_pd_aon` input to
`u_pwrmgr` and `u_clkmgr`. `lc_hw_debug_clr_o` connects directly to `u_pinmux`
and `u_rv_dm` in the main domain. This yields 13 reviewed direct connections.

The default RV JTAG extension adds six main-wrapper connections: pinmux
`pinmux_hw_debug_en_o` to RV_DM `pinmux_hw_debug_en_i`, pinmux `rv_jtag_o` to
RV_DM `jtag_i`, and RV_DM `jtag_o` to pinmux `rv_jtag_i`. The checker also requires
`RvDmUseDmiInterface = 0` in both `top_earlgrey` and `earlgrey_pd_main`, forwarding
through `earlgrey_pd_main.RvDmUseDmiInterface` and then
`u_rv_dm.UseDmiInterface`. These four contracts and 19 total direct edges have
source lines in the JSON report. Commented, duplicated, changed or missing
contracts remain UNKNOWN. The checker does not detect an external parameter
override or prove that JTAG traffic can reach an unlocked debug register.

```sh
python3 run_opentitan_debug_endpoints.py /path/to/clean/opentitan /tmp/lc-debug-endpoints.json
python3 -m unittest -v test_opentitan_debug_endpoints
```

Tests cover the positive expected wiring, a missing/miswired direct consumer, and
the boundary where a concatenated expression replaces a direct net connection.
The RV path tests also change a debug edge, change the default/forwarding, and
put a default only in a comment alongside a duplicate declaration. On the clean
pinned checkout, the updated pilot reports 19 edges and four contracts with no
unknowns. Its input is read-only; this is structural source evidence only.
Duplicate pins with the same or conflicting nets, duplicate instances, and a
changed module type are negative regression cases.
The checker recognizes only direct named connections in these three files; it
does not elaborate hierarchy, follow combinational logic, enumerate downstream
debug gates or prove endpoint completeness beyond the pinned reviewed list. It
does not establish lifecycle policy correctness or debug-access safety.
