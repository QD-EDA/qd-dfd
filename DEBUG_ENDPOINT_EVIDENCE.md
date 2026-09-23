# Earlgrey lifecycle debug endpoint inventory

`run_opentitan_debug_endpoints.py ROOT REPORT.json` checks direct named-port
connections in the pinned Earlgrey top, main power-domain wrapper and AON wrapper.
It requires a clean OpenTitan checkout at
`7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`. The report records each source path,
line and file SHA-256. Missing or changed connections and newly discovered direct
consumers are `UNKNOWN` until reviewed.

The observed path is `u_lc_ctrl.lc_hw_debug_en_o` to five main-domain consumers
(`u_pinmux`, `u_rv_dm`, `u_csrng`, `u_sram_ctrl_main`, `u_sram_ctrl_sec`), then
through the top-level `earlgrey_pd_main` output and `earlgrey_pd_aon` input to
`u_pwrmgr` and `u_clkmgr`. `lc_hw_debug_clr_o` connects directly to `u_pinmux`
and `u_rv_dm` in the main domain. This yields 13 reviewed direct connections.

```sh
python3 run_opentitan_debug_endpoints.py /path/to/clean/opentitan /tmp/lc-debug-endpoints.json
python3 -m unittest -v test_opentitan_debug_endpoints
```

Tests cover the positive expected wiring, a missing/miswired direct consumer, and
the boundary where a concatenated expression replaces a direct net connection.
The checker recognizes only direct named connections in these three files; it
does not elaborate hierarchy, follow combinational logic, enumerate downstream
debug gates or prove endpoint completeness beyond the pinned reviewed list. It
does not establish lifecycle policy correctness or debug-access safety.
