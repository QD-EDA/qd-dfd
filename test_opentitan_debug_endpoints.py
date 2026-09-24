import unittest

from run_opentitan_debug_endpoints import audit_texts, connections


class EndpointAuditTests(unittest.TestCase):
    def setUp(self):
        self.texts = {
            'main': '''module earlgrey_pd_main #(
  parameter bit RvDmUseDmiInterface = 0,
) ();
  lc_ctrl #(
  ) u_lc_ctrl (
    .lc_hw_debug_en_o(lc_ctrl_lc_hw_debug_en),
    .lc_hw_debug_clr_o(lc_ctrl_lc_hw_debug_clr)
  );
  pinmux #(
  ) u_pinmux (
    .lc_hw_debug_en_i(lc_ctrl_lc_hw_debug_en),
    .lc_hw_debug_clr_i(lc_ctrl_lc_hw_debug_clr),
    .pinmux_hw_debug_en_o(pinmux_pinmux_hw_debug_en),
    .rv_jtag_o(pinmux_rv_jtag_req),
    .rv_jtag_i(pinmux_rv_jtag_rsp)
  );
  rv_dm #(
    .UseDmiInterface(RvDmUseDmiInterface)
  ) u_rv_dm (
    .lc_hw_debug_en_i(lc_ctrl_lc_hw_debug_en),
    .lc_hw_debug_clr_i(lc_ctrl_lc_hw_debug_clr),
    .pinmux_hw_debug_en_i(pinmux_pinmux_hw_debug_en),
    .jtag_i(pinmux_rv_jtag_req),
    .jtag_o(pinmux_rv_jtag_rsp)
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
            'top': '''module top_earlgrey #(
  parameter bit RvDmUseDmiInterface = 0,
) ();
  earlgrey_pd_main #(
    .RvDmUseDmiInterface(RvDmUseDmiInterface)
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
        self.assertEqual(len(result['edges']), 19)
        self.assertEqual(len(result['contracts']), 4)
        self.assertEqual(result['unknown'], [])

    def test_changed_rv_debug_connection_is_unknown(self):
        for port, net in [('pinmux_hw_debug_en_i', 'pinmux_pinmux_hw_debug_en'),
                          ('rv_jtag_o', 'pinmux_rv_jtag_req'),
                          ('jtag_o', 'pinmux_rv_jtag_rsp')]:
            with self.subTest(port=port):
                changed = dict(self.texts)
                changed['main'] = changed['main'].replace(f'.{port}({net})',
                                                            f'.{port}(wrong_net)')
                result = audit_texts(changed)
                self.assertEqual(result['status'], 'UNKNOWN')
                self.assertTrue(any(port in item for item in result['unknown']))

    def test_nondefault_dmi_and_missing_forwarding_are_unknown(self):
        self.texts['top'] = self.texts['top'].replace('RvDmUseDmiInterface = 0',
                                                      'RvDmUseDmiInterface = 1')
        self.texts['main'] = self.texts['main'].replace(
            '.UseDmiInterface(RvDmUseDmiInterface)', '.UseDmiInterface(1)')
        result = audit_texts(self.texts)
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertTrue(any('default RvDmUseDmiInterface' in item for item in result['unknown']))
        self.assertTrue(any('u_rv_dm.UseDmiInterface' in item for item in result['unknown']))

    def test_comment_and_duplicate_contract_are_unknown(self):
        self.texts['top'] = self.texts['top'].replace(
            'parameter bit RvDmUseDmiInterface = 0,',
            '// parameter bit RvDmUseDmiInterface = 0,')
        self.texts['main'] = self.texts['main'].replace(
            'parameter bit RvDmUseDmiInterface = 0,',
            'parameter bit RvDmUseDmiInterface = 0,\n  parameter bit RvDmUseDmiInterface = 0,')
        result = audit_texts(self.texts)
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertTrue(any('default RvDmUseDmiInterface' in item for item in result['unknown']))

    def test_duplicate_reviewed_pin_is_unknown(self):
        for duplicate in ('.jtag_i(pinmux_rv_jtag_req)', '.jtag_i(wrong_net)',
                          '.jtag_i(wrapper(wrong_net))'):
            with self.subTest(duplicate=duplicate):
                changed = dict(self.texts)
                changed['main'] = changed['main'].replace(
                    '.jtag_i(pinmux_rv_jtag_req),',
                    '.jtag_i(pinmux_rv_jtag_req),\n    ' + duplicate + ',')
                result = audit_texts(changed)
                self.assertEqual(result['status'], 'UNKNOWN')
                self.assertTrue(any('u_rv_dm.jtag_i' in item for item in result['unknown']))

    def test_duplicate_instance_or_wrong_module_is_unknown(self):
        for changed_main in (
            self.texts['main'].replace('  pinmux #(\n', '  bogus #(\n'),
            self.texts['main'].replace('  rv_dm #(\n',
                '  pinmux #(\n  ) u_pinmux (\n    .rv_jtag_o(pinmux_rv_jtag_req)\n  );\n  rv_dm #(\n'),
        ):
            with self.subTest(changed_main=changed_main):
                result = audit_texts({**self.texts, 'main': changed_main})
                self.assertEqual(result['status'], 'UNKNOWN')
                self.assertTrue(any('u_pinmux' in item for item in result['unknown']))

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
