import unittest

from run_opentitan_debug_endpoints import audit_texts, connections


class EndpointAuditTests(unittest.TestCase):
    def setUp(self):
        self.texts = {
            'main': '''module main;
  lc_ctrl #(
  ) u_lc_ctrl (
    .lc_hw_debug_en_o(lc_ctrl_lc_hw_debug_en),
    .lc_hw_debug_clr_o(lc_ctrl_lc_hw_debug_clr)
  );
  pinmux #(
  ) u_pinmux (
    .lc_hw_debug_en_i(lc_ctrl_lc_hw_debug_en),
    .lc_hw_debug_clr_i(lc_ctrl_lc_hw_debug_clr)
  );
  rv_dm #(
  ) u_rv_dm (
    .lc_hw_debug_en_i(lc_ctrl_lc_hw_debug_en),
    .lc_hw_debug_clr_i(lc_ctrl_lc_hw_debug_clr)
  );
  csrng #(
  ) u_csrng (
    .lc_hw_debug_en_i(lc_ctrl_lc_hw_debug_en)
  );
  sram_ctrl #(
  ) u_sram_ctrl_main (
    .lc_hw_debug_en_i(lc_ctrl_lc_hw_debug_en)
  );
  sram_ctrl #(
  ) u_sram_ctrl_sec (
    .lc_hw_debug_en_i(lc_ctrl_lc_hw_debug_en)
  );
endmodule
''',
            'top': '''module top;
  earlgrey_pd_main #(
  ) earlgrey_pd_main (
    .lc_ctrl_lc_hw_debug_en_o(lc_ctrl_lc_hw_debug_en)
  );
  earlgrey_pd_aon #(
  ) earlgrey_pd_aon (
    .lc_ctrl_lc_hw_debug_en_i(lc_ctrl_lc_hw_debug_en)
  );
endmodule
''',
            'aon': '''module aon;
  pwrmgr #(
  ) u_pwrmgr (
    .lc_hw_debug_en_i(lc_ctrl_lc_hw_debug_en_i)
  );
  clkmgr #(
  ) u_clkmgr (
    .lc_hw_debug_en_i(lc_ctrl_lc_hw_debug_en_i)
  );
endmodule
''',
        }

    def test_resolves_expected_direct_edges(self):
        result = audit_texts(self.texts)
        self.assertEqual(result['status'], 'resolved_bounded')
        self.assertEqual(len(result['edges']), 13)
        self.assertEqual(result['unknown'], [])

    def test_missing_direct_consumer_is_unknown(self):
        self.texts['main'] = self.texts['main'].replace(
            '.lc_hw_debug_clr_i(lc_ctrl_lc_hw_debug_clr)',
            '.lc_hw_debug_clr_i(lc_ctrl_lc_hw_debug_en)')
        result = audit_texts(self.texts)
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertTrue(any('missing direct connection' in item for item in result['unknown']))

    def test_expression_boundary_is_unknown(self):
        self.texts['main'] = self.texts['main'].replace(
            '.lc_hw_debug_en_i(lc_ctrl_lc_hw_debug_en)',
            '.lc_hw_debug_en_i({lc_ctrl_lc_hw_debug_en})', 1)
        result = audit_texts(self.texts)
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertTrue(any("('main', 'u_pinmux', 'lc_hw_debug_en_i'" in item
                            for item in result['unknown']))

    def test_named_pin_scanner_keeps_line_and_net(self):
        self.assertEqual(connections('''  pinmux #(
  ) u_pinmux (
    .lc_hw_debug_en_i(lc_ctrl_lc_hw_debug_en)
  );
'''), [('u_pinmux', 'lc_hw_debug_en_i', 'lc_ctrl_lc_hw_debug_en', 3)])


if __name__ == '__main__':
    unittest.main()
