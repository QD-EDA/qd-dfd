import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import run_opentitan_debug_endpoints as tool
from run_opentitan_debug_endpoints import rv_dm_path_contracts


RV_DM = '''module rv_dm;
  if (UseDmiInterface) begin : gen_dmi_gating
    assign jtag_o = '0;
  end else begin : gen_jtag_gating
    prim_lc_sync #(
      .NumCopies(int'(PmEnLastPos))
    ) u_pm_en_sync (
      .clk_i,
      .rst_ni,
      .lc_en_i(pinmux_hw_debug_en_i),
      .lc_en_o(pinmux_hw_debug_en)
    );
    assign jtag_in_int = (lc_tx_test_true_strict(pinmux_hw_debug_en[PmEnJtagIn])) ? jtag_i : '0;
    assign jtag_o = (lc_tx_test_true_strict(pinmux_hw_debug_en[PmEnJtagOut])) ? jtag_out_int : '0;
    assign dmi_en = lc_tx_test_true_strict(pinmux_hw_debug_en[PmEnDmiReq]);
`ifndef DMIDirectTAP
    prim_clock_mux2 #(.NoFpgaBufG(1'b1)) u_prim_clock_mux2 (
      .clk0_i(jtag_in_int.tck), .clk1_i(clk_i),
      .sel_i(testmode), .clk_o(tck_muxed)
    );
    prim_clock_mux2 #(.NoFpgaBufG(1'b1)) u_prim_rst_n_mux2 (
      .clk0_i(jtag_in_int.trst_n), .clk1_i(scan_rst_ni),
      .sel_i(testmode), .clk_o(trst_n_muxed)
    );
    dmi_jtag #(.IdcodeValue(IdcodeValue)) dap (
      .dmi_req_o(dmi_req),
      .dmi_req_valid_o(dmi_req_valid_raw),
      .dmi_req_ready_i(dmi_req_ready & dmi_en),
      .tck_i(tck_muxed), .tms_i(jtag_in_int.tms),
      .trst_ni(trst_n_muxed), .td_i(jtag_in_int.tdi),
      .td_o(jtag_out_int.tdo)
    );
    assign dmi_req_valid = dmi_req_valid_raw & dmi_en;
    assign dmi_rsp_ready = dmi_rsp_ready_raw & dmi_en;
`endif
  end
  dm_top #(.NrHarts(NrHarts)) u_dm_top (
    .dmi_req_valid_i(dmi_req_valid),
    .dmi_req_ready_o(dmi_req_ready),
    .dmi_req_i(dmi_req),
    .dmi_resp_valid_o(dmi_rsp_valid)
  );
endmodule
'''


class RvDmPathTests(unittest.TestCase):
    def test_source_linked_path(self):
        contracts, unknown = rv_dm_path_contracts(RV_DM)
        self.assertEqual(unknown, [])
        self.assertEqual(len(contracts), 11)
        self.assertEqual([item['line'] for item in contracts],
                         [5, 13, 14, 15, 17, 21, 25, 25, 33, 34, 37])

    def test_changed_gate_and_endpoint_fail_closed(self):
        for old, new in [('lc_tx_test_true_strict(pinmux_hw_debug_en[PmEnJtagIn])',
                          'lc_tx_test_true_loose(pinmux_hw_debug_en[PmEnJtagIn])'),
                         ('dmi_req_valid_raw & dmi_en;', 'dmi_req_valid_raw;'),
                         ('.dmi_req_valid_i(dmi_req_valid)', '.dmi_req_valid_i(1\'b1)')]:
            with self.subTest(old=old):
                contracts, unknown = rv_dm_path_contracts(RV_DM.replace(old, new))
                self.assertTrue(unknown)
                self.assertLess(len(contracts), 11)

    def test_duplicate_and_branch_drift_are_unknown(self):
        for changed in (RV_DM.replace('if (UseDmiInterface)', 'if (1)'),
                        RV_DM.replace('`ifndef DMIDirectTAP', '`ifdef DMIDirectTAP'),
                        RV_DM.replace('    dmi_jtag #', '    `ifdef OTHER_MODE\n    dmi_jtag #'),
                        RV_DM.replace('  dm_top #', '  dm_top #(.Extra(0)) other_dm ();\n  dm_top #'),
                        RV_DM.replace('    assign dmi_en = lc_tx_test_true_strict(pinmux_hw_debug_en[PmEnDmiReq]);',
                                      '    assign dmi_en = lc_tx_test_true_strict(pinmux_hw_debug_en[PmEnDmiReq]);\n'
                                      '    assign dmi_en = lc_tx_test_true_strict(pinmux_hw_debug_en[PmEnDmiReq]);'),
                        RV_DM.replace('    assign dmi_req_valid =',
                                      '    assign dmi_req_valid =\n    assign dmi_req_valid =')):
            with self.subTest(changed=changed):
                self.assertTrue(rv_dm_path_contracts(changed)[1])

    def test_comment_does_not_supply_missing_gate(self):
        changed = RV_DM.replace('assign dmi_en = lc_tx_test_true_strict',
                                '// assign dmi_en = lc_tx_test_true_strict')
        self.assertTrue(rv_dm_path_contracts(changed)[1])

    def test_mid_scan_source_mutation_returns_unknown_report(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / 'checkout'
            for relative in tool.FILES.values():
                path = checkout / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('original\n')
            report = Path(directory) / 'report.json'

            def mutate_after_read(_texts):
                (checkout / tool.FILES['rv_dm']).write_text('changed\n')
                return {'status': 'resolved_bounded', 'edges': [], 'contracts': [],
                        'rv_dm_path': [], 'unknown': []}

            def fake_git(argv, **_kwargs):
                return tool.PIN + '\n' if argv[1] == 'rev-parse' else ''

            with mock.patch.object(sys, 'argv', ['tool', str(checkout), str(report)]), \
                    mock.patch.object(tool.subprocess, 'check_output', side_effect=fake_git), \
                    mock.patch.object(tool, 'audit_texts', side_effect=mutate_after_read), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main(), 2)
            data = json.loads(report.read_text())
            self.assertEqual(data['status'], 'UNKNOWN')
            self.assertTrue(any('post-scan source changed' in item for item in data['unknown']))
            self.assertNotEqual(data['sources']['rv_dm']['sha256'],
                                data['postcheck']['sha256']['rv_dm'])


if __name__ == '__main__':
    unittest.main()
