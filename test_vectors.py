import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_qd_dfd import TOOL


POLICY = {
    "signals": {"reset": "tb.rst_n", "lock": "tb.lc", "request": "tb.req", "grant": "tb.grant"},
    "widths": {"lock": 4},
    "forbidden": [{"when": {"reset": "1", "lock": "1010", "grant": "1"}}],
    "required": [{"when": {"reset": "1", "lock": "1010", "request": "1", "grant": "0"}},
                 {"when": {"reset": "1", "lock": "0101", "grant": "1"}}],
}
DECLS = '''$scope module tb $end
$var wire 1 ! rst_n $end
$var wire 4 @ lc [3:0] $end
$var wire 1 # req $end
$var wire 1 $ grant $end
$upscope $end
$enddefinitions $end
'''
GOOD = '#0\n1! 1# 0$ b1010 @\n#5\nb101 @ 1$\n'


class VectorTests(unittest.TestCase):
    def run_case(self, trace=GOOD, policy=POLICY, decls=DECLS):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'policy.json').write_text(json.dumps(policy))
            (root / 'trace.vcd').write_text(decls + trace)
            run = subprocess.run([sys.executable, str(TOOL), 'check', str(root / 'trace.vcd'),
                                  '--policy', str(root / 'policy.json'), '--json'],
                                 capture_output=True, text=True)
            return run.returncode, json.loads(run.stdout)

    def test_encoded_controls_and_zero_extension(self):
        code, report = self.run_case()
        self.assertEqual((code, report['diagnostics']), (0, []))
        code, report = self.run_case(GOOD + '#8\nb1010 @\n')
        self.assertEqual(code, 1)
        self.assertIn('forbidden', {d['kind'] for d in report['diagnostics']})

    def test_partial_unknown_is_decisive_only_without_known_mismatch(self):
        for bits in ('x', 'z', '10x0', '10z0'):
            code, report = self.run_case(GOOD + f'#8\nb{bits} @\n')
            self.assertEqual(code, 1)
            self.assertIn('unknown', {d['kind'] for d in report['diagnostics']})
        # Both expected encodings disagree with the known leading bits.
        self.assertEqual(self.run_case(GOOD + '#8\nb11x0 @\n')[0], 0)

    def test_width_mismatch_and_bad_value_rejected(self):
        for value in ('10000', '2', ''):
            self.assertEqual(self.run_case(GOOD + f'#8\nb{value} @\n')[0], 1)
        self.assertEqual(self.run_case(GOOD + '#8\n1@\n')[0], 1)
        self.assertEqual(self.run_case(decls=DECLS.replace('wire 4 @', 'wire 3 @'))[0], 1)
        policy = copy.deepcopy(POLICY)
        del policy['widths']
        self.assertEqual(self.run_case(policy=policy)[0], 1)

    def test_policy_width_and_expected_value_validation(self):
        for width in (0, -1, True, '4', 4097):
            policy = copy.deepcopy(POLICY); policy['widths']['lock'] = width
            self.assertEqual(self.run_case(policy=policy)[0], 1)
        for value in ('101', '10x0', 10, ''):
            policy = copy.deepcopy(POLICY); policy['required'][0]['when']['lock'] = value
            self.assertEqual(self.run_case(policy=policy)[0], 1)

    def test_aliases_and_same_timestamp_final_value(self):
        decls = DECLS.replace('$upscope', '$var wire 4 % unused [3:0] $end\n$var wire 4 @ alias [3:0] $end\n$upscope')
        policy = copy.deepcopy(POLICY)
        policy['signals']['alias'] = 'tb.alias'; policy['widths']['alias'] = 4
        policy['required'][1]['when']['alias'] = '0101'
        self.assertEqual(self.run_case(GOOD + '#8\nb1010 @\n#8\nb101 @\n', policy, decls)[0], 0)
        self.assertEqual(self.run_case(decls=DECLS.replace('wire 1 # req', 'wire 1 @ req'))[0], 1)

    def test_no_vector_initialization_is_unknown_not_zero(self):
        code, report = self.run_case('#0\n1! 1# 1$\n')
        self.assertEqual(code, 1)
        self.assertTrue(any(d['kind'] == 'unknown' and d['signals']['tb.lc'] == 'xxxx'
                            for d in report['diagnostics']))

    def test_maximum_supported_width(self):
        policy = copy.deepcopy(POLICY); policy['widths']['lock'] = 4096
        policy['required'][0]['when']['lock'] = '0' * 4096
        policy['required'][1]['when']['lock'] = '0' * 4095 + '1'
        policy['forbidden'][0]['when']['lock'] = '0' * 4096
        self.assertEqual(self.run_case('#0\n1! 1# 0$ b0 @\n#5\nb1 @ 1$\n', policy,
                                      DECLS.replace('wire 4 @', 'wire 4096 @').replace('[3:0]', '[4095:0]'))[0], 0)
