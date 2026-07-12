import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_release_manifest.py"
VERIFIER = ROOT / "scripts" / "verify_release_manifest.py"
MANAGED = (
    ".github",
    "certificates",
    "docs",
    "examples",
    "manifests",
    "paper",
    "scripts",
    "src",
    "tests",
)


class ReleaseManifestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for directory in MANAGED:
            (self.root / directory).mkdir(parents=True)
        (self.root / "README.md").write_text("release test\n", encoding="utf-8")
        (self.root / "docs" / "proof.md").write_text("proof payload\n", encoding="utf-8")
        generated = subprocess.run(
            [sys.executable, str(GENERATOR), "--root", str(self.root)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(generated.returncode, 0, generated.stderr)

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self):
        return subprocess.run(
            [sys.executable, str(VERIFIER), "--root", str(self.root)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def test_generated_manifest_accepts(self):
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_modified_payload_is_rejected(self):
        (self.root / "docs" / "proof.md").write_text("modified\n", encoding="utf-8")
        result = self.verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inventory or hash mismatch", result.stderr)

    def test_unlisted_managed_file_is_rejected(self):
        (self.root / "certificates" / "extra.json").write_text("{}\n", encoding="utf-8")
        result = self.verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inventory or hash mismatch", result.stderr)

    def test_malformed_checksum_path_is_rejected(self):
        sums = self.root / "SHA256SUMS"
        sums.write_text(sums.read_text(encoding="ascii") + "0" * 64 + "  ../escape\n", encoding="ascii")
        result = self.verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe SHA256SUMS path", result.stderr)

    def test_unmanaged_top_level_directory_is_rejected(self):
        (self.root / "unlisted").mkdir()
        result = self.verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unmanaged top-level directory", result.stderr)


if __name__ == "__main__":
    unittest.main()
