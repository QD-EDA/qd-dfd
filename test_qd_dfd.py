import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("qd-dfd")
SIGNALS = {"reset": "tb.rst_n", "lock": "tb.locked", "request": "tb.dbg_req", "grant": "tb.dbg_grant"}
POLICY = {
    "signals": SIGNALS,
    "forbidden": [{"when": {"reset": "1", "lock": "1", "grant": "1"}}],
    "required": [
        {"when": {"reset": "1", "lock": "1", "request": "1", "grant": "0"}},
        {"when": {"reset": "1", "lock": "0", "grant": "1"}},
    ],
}
DECLS = '''$scope module tb $end
$var wire 1 ! rst_n $end
$var wire 1 \" locked $end
$var wire 1 # dbg_req $end
$var wire 1 $ dbg_grant $end
$var wire 8 % unrelated_bus [7:0] $end
$upscope $end
$enddefinitions $end
'''


class CheckerTests(unittest.TestCase):
    def run_check(self, trace, policy=POLICY):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vcd, config = root / "trace.vcd", root / "policy.json"
            vcd.write_text(DECLS + trace)
            config.write_text(json.dumps(policy))
            return subprocess.run(
                [sys.executable, str(TOOL), "check", str(vcd), "--policy", str(config), "--json"],
                text=True, capture_output=True, check=False,
            )

    def result(self, trace, policy=POLICY):
        run = self.run_check(trace, policy)
        return run.returncode, json.loads(run.stdout)

    def test_allowed_unlocked_access_and_denied_locked_request(self):
        code, result = self.result('''#0
1! 0\" 0# 0$
b10101111 %
#5
1# 1$
#8
1\" 0$
''')
        self.assertEqual(code, 0)
        self.assertEqual(result["diagnostics"], [])

    def test_forbidden_locked_grant(self):
        code, result = self.result('''#0
1! 0\" 0# 0$
#5
1# 1$
#8
1\" 1$
''')
        self.assertEqual(code, 1)
        self.assertIn("forbidden", {d["kind"] for d in result["diagnostics"]})

    def test_missing_hierarchy(self):
        policy = json.loads(json.dumps(POLICY))
        policy["signals"]["lock"] = "tb.not_present"
        code, result = self.result("#0\n", policy)
        self.assertEqual(code, 1)
        self.assertIn("missing VCD signal", result["diagnostics"][0]["message"])

    def test_x_and_z_at_decisive_check_fail(self):
        for bit in ("x", "z"):
            with self.subTest(bit=bit):
                code, result = self.result(f'''#0
1! 0\" 1# {bit}$
#5
0\" 0$
''')
                self.assertEqual(code, 1)
                self.assertIn("unknown", {d["kind"] for d in result["diagnostics"]})

    def test_same_timestamp_uses_final_values(self):
        code, result = self.result('''#0
1! 0\" 0# 0$
#5
1# 1$
#8
1\"
#8
0$
''')
        self.assertEqual(code, 0)
        self.assertEqual(result["diagnostics"], [])

    def test_vacuous_trace_fails(self):
        code, result = self.result('''#0
1! 0\" 0# 0$
#5
1# 1$
''')
        self.assertEqual(code, 1)
        self.assertIn("vacuous", {d["kind"] for d in result["diagnostics"]})

    def test_unknown_cannot_be_declared_expected(self):
        policy = json.loads(json.dumps(POLICY))
        policy["required"][0]["when"]["grant"] = "x"
        code, result = self.result("#0\n", policy)
        self.assertEqual(code, 1)
        self.assertIn("expected values must be 0 or 1", result["diagnostics"][0]["message"])


if __name__ == "__main__":
    unittest.main()
