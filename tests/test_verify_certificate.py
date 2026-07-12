import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_certificate.py"
SOURCE = ROOT / "src" / "m96" / "affine_ladder_prefix.cpp"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BranchVerifierTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.manifest = self.base / "tasks.jsonl"
        self.runs = self.base / "runs"
        self.runs.mkdir()
        self.task_id = "m96_k1_01"
        self.log = self.runs / f"{self.task_id}.log"
        self.meta = self.runs / f"{self.task_id}.meta.json"
        self.write_manifest()
        self.write_log()
        self.write_meta()

    def tearDown(self):
        self.tmp.cleanup()

    def header(self):
        return {
            "kind": "header",
            "cover": "m96_k1_1_1",
            "m": 96,
            "k1_min": 1,
            "k1_max": 1,
            "source": "src/m96/affine_ladder_prefix.cpp",
            "source_sha256": sha256(SOURCE),
            "engine_args_schema": ["m", "prefix_csv", "verbose", "enum_threshold"],
        }

    def task(self, task_id=None):
        return {
            "kind": "task",
            "task_id": task_id or self.task_id,
            "m": 96,
            "k1": 1,
            "fixed_prefix": "1",
            "verbose": 0,
            "enum_threshold": 256,
            "expected": {"exit_code": 0, "result": "PASS", "hits": 0},
        }

    def write_manifest(self, tasks=None, header=None):
        values = [header or self.header(), *(tasks or [self.task()])]
        self.manifest.write_text(
            "".join(json.dumps(value, sort_keys=True) + "\n" for value in values),
            encoding="utf-8",
        )

    def write_log(self, hits=0):
        self.log.write_text(
            "CASE=96 K1_RANGE=1..1 NODES=0 DET_VALUES=0 DET_NODES=0 "
            f"HUG_PRUNES=0 FINAL_INTERVALS=0 HITS={hits} SECONDS=0\nRESULT: PASS\n",
            encoding="utf-8",
        )

    def write_meta(self):
        value = {
            "cmd": ["./engine", "96", "1", "0", "256"],
            "exit_code": 0,
            "log_sha256": sha256(self.log),
            "seconds": 0.0,
            "task_id": self.task_id,
            "timed_out": False,
        }
        self.meta.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")

    def verify(self, source=SOURCE):
        return subprocess.run(
            [
                sys.executable,
                str(VERIFIER),
                "--tasks",
                str(self.manifest),
                "--runs",
                str(self.runs),
                "--source",
                str(source),
                "--exe",
                "./engine",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def assert_rejected(self, result, message=None):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("REJECT", result.stderr)
        if message:
            self.assertIn(message, result.stderr)

    def test_valid_artifact_accepts(self):
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"], "ACCEPT")

    def test_missing_branch_is_rejected(self):
        self.log.unlink()
        self.assert_rejected(self.verify(), "missing run files")

    def test_altered_hit_count_is_rejected(self):
        self.write_log(hits=1)
        self.write_meta()
        self.assert_rejected(self.verify(), "HITS markers")

    def test_modified_log_hash_is_rejected(self):
        self.log.write_text(self.log.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
        self.assert_rejected(self.verify(), "bad log hash")

    def test_source_hash_mismatch_is_rejected(self):
        changed = self.base / "changed.cpp"
        changed.write_bytes(SOURCE.read_bytes() + b"\n")
        self.assert_rejected(self.verify(changed), "source hash mismatch")

    def test_unexpected_file_is_rejected(self):
        (self.runs / "extra.txt").write_text("unexpected\n", encoding="utf-8")
        self.assert_rejected(self.verify(), "unexpected run files")

    def test_duplicate_metadata_key_is_rejected(self):
        self.meta.write_text(
            '{"task_id":"m96_k1_01","task_id":"m96_k1_01"}\n',
            encoding="utf-8",
        )
        self.assert_rejected(self.verify(), "duplicate JSON key")

    def test_unsafe_task_id_is_rejected(self):
        self.write_manifest(tasks=[self.task("../escape")])
        self.assert_rejected(self.verify(), "unsafe task_id")

    def test_duplicate_manifest_task_is_rejected(self):
        self.write_manifest(tasks=[self.task(), self.task()])
        self.assert_rejected(self.verify(), "duplicate task_id")

    @unittest.skipIf(not hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlinked_artifact_is_rejected(self):
        target = self.base / "real.log"
        target.write_bytes(self.log.read_bytes())
        self.log.unlink()
        self.log.symlink_to(target)
        self.assert_rejected(self.verify(), "symlinked run artifact")


if __name__ == "__main__":
    unittest.main()
