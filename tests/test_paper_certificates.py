import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from verify_frontier_certificate import read_csv  # noqa: E402
from verify_descent_certificates import verify_cell  # noqa: E402


class PaperCertificateTest(unittest.TestCase):
    def run_script(self, name, *arguments):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / name), *map(str, arguments)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def test_frontier_certificate_accepts(self):
        result = self.run_script("verify_frontier_certificate.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["count"], 280139)

    def test_frontier_oracle_accepts(self):
        result = self.run_script("verify_frontier_oracle.py")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_first_spike_accepts(self):
        result = self.run_script("verify_first_spike_certificate.py")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_duplicate_frontier_row_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frontier.csv"
            path.write_text("t\n10\n10\n", encoding="ascii")
            with self.assertRaisesRegex(AssertionError, "strictly sorted and unique"):
                read_csv(path)

    def test_mutated_first_spike_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = ROOT / "certificates" / "first_spike.json"
            path = Path(tmp) / "first_spike.json"
            value = json.loads(source.read_text(encoding="utf-8"))
            value["survivors"] = 1
            path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = self.run_script(
                "verify_first_spike_certificate.py", "--certificate", path
            )
            self.assertNotEqual(result.returncode, 0)

    def test_mutated_oracle_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = ROOT / "certificates" / "frontier" / "oracle_summary.json"
            path = Path(tmp) / "oracle.json"
            value = json.loads(source.read_text(encoding="utf-8"))
            value["counts"][0]["count"] += 1
            path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = self.run_script("verify_frontier_oracle.py", "--certificate", path)
            self.assertNotEqual(result.returncode, 0)

    def test_descent_cell_arithmetic_accepts(self):
        verify_cell((3, 6, 2, 5, 1), 3, 4, 24)

    def test_mutated_descent_cell_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, "affine descent data mismatch"):
            verify_cell((3, 6, 2, 5, 3), 3, 4, 24)


if __name__ == "__main__":
    unittest.main()
