import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_reduction_certificates.py"
VERIFIER = ROOT / "scripts" / "verify_reduction_certificates.py"
CERTIFICATES = ROOT / "certificates" / "reductions"
SOURCE = ROOT / "src" / "m96" / "affine_ladder_prefix.cpp"


class ReductionCertificateTest(unittest.TestCase):
    def run_verifier(self, certificates, source=SOURCE):
        return subprocess.run(
            [
                sys.executable,
                str(VERIFIER),
                "--certificates",
                str(certificates),
                "--source",
                str(source),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def copied_certificates(self, base):
        target = base / "reductions"
        shutil.copytree(CERTIFICATES, target)
        return target

    def test_committed_certificates_accept(self):
        result = self.run_verifier(CERTIFICATES)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"], "ACCEPT")

    def test_generator_reproduces_certificates_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "reductions"
            result = subprocess.run(
                [sys.executable, str(GENERATOR), "--out", str(output)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for expected in sorted(CERTIFICATES.iterdir()):
                self.assertEqual(expected.read_bytes(), (output / expected.name).read_bytes())

    def test_mutated_farey_error_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            certificates = self.copied_certificates(Path(tmp))
            path = certificates / "m96_reduction.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["final_lift"]["farey"]["error_upper"]["numerator"] = "1"
            path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = self.run_verifier(certificates)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("REJECT", result.stderr)

    def test_unexpected_certificate_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            certificates = self.copied_certificates(Path(tmp))
            (certificates / "extra.json").write_text("{}\n", encoding="utf-8")
            result = self.run_verifier(certificates)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("certificate set mismatch", result.stderr)

    def test_source_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            certificates = self.copied_certificates(base)
            changed_source = base / "affine_ladder_prefix.cpp"
            changed_source.write_bytes(SOURCE.read_bytes() + b"\n")
            result = self.run_verifier(certificates, changed_source)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source hash mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
