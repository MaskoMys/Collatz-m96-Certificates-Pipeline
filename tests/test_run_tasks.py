import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_tasks.py"


def write_manifest(path, count=1):
    lines = [
        {
            "kind": "header",
            "cover": "test_cover",
            "m": 96,
            "k1_min": 1,
            "k1_max": count,
            "source_sha256": "0" * 64,
        }
    ]
    for k1 in range(1, count + 1):
        lines.append(
            {
                "kind": "task",
                "task_id": f"m96_k1_{k1:02d}",
                "m": 96,
                "k1": k1,
                "fixed_prefix": str(k1),
                "verbose": 0,
                "enum_threshold": 256,
                "expected": {"exit_code": 0, "hits": 0, "result": "PASS"},
            }
        )
    path.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")


def write_fake_engine(path):
    path.write_text(
        textwrap.dedent("""\
        #!/usr/bin/env python3
        import os
        import sys
        import time

        m, fixed_prefix = sys.argv[1], sys.argv[2]
        counter = os.environ.get('FAKE_COUNTER')
        if counter:
            with open(counter, 'a', encoding='utf-8') as f:
                f.write(fixed_prefix + '\\n')
        sleep = float(os.environ.get('FAKE_SLEEP', '0'))
        if sleep:
            time.sleep(sleep)
        print(f'CASE={m} K1_RANGE={fixed_prefix}..{fixed_prefix} NODES=0 DET_VALUES=0 DET_NODES=0 HUG_PRUNES=0 FINAL_INTERVALS=0 HITS=0 SECONDS=0')
        print('RESULT: PASS')
    """),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class RunTasksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.manifest = self.base / "tasks.jsonl"
        self.fake = self.base / "fake_engine.py"
        self.out = self.base / "runs"
        self.counter = self.base / "counter.txt"
        write_fake_engine(self.fake)

    def tearDown(self):
        self.tmp.cleanup()

    def run_runner(self, *extra, sleep=None):
        env = os.environ.copy()
        env["FAKE_COUNTER"] = str(self.counter)
        if sleep is not None:
            env["FAKE_SLEEP"] = str(sleep)
        cmd = [
            sys.executable,
            str(RUNNER),
            "--exe",
            str(self.fake),
            "--tasks",
            str(self.manifest),
            "--out",
            str(self.out),
            "--jobs",
            "1",
            *extra,
        ]
        return subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True)

    def counter_lines(self):
        if not self.counter.exists():
            return []
        return self.counter.read_text(encoding="utf-8").splitlines()

    def test_resume_skips_valid_artifacts(self):
        write_manifest(self.manifest)
        first = self.run_runner("--timeout", "10")
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        self.assertEqual(self.counter_lines(), ["1"])

        second = self.run_runner("--resume", "--timeout", "10")
        self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
        self.assertEqual(self.counter_lines(), ["1"])

        status = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--status",
                "--exe",
                str(self.fake),
                "--tasks",
                str(self.manifest),
                "--out",
                str(self.out),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(status.returncode, 0, status.stderr)
        payload = json.loads(status.stdout)
        self.assertEqual(payload["completed"], 1)
        self.assertEqual(payload["pending"], 0)

    def test_invalid_root_requires_retry_invalid(self):
        write_manifest(self.manifest)
        first = self.run_runner("--timeout", "10")
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        (self.out / "m96_k1_01.log").write_text("corrupt\n", encoding="utf-8")

        bad = self.run_runner("--resume", "--timeout", "10")
        self.assertNotEqual(bad.returncode, 0)

        retry = self.run_runner("--resume", "--retry-invalid", "--timeout", "10")
        self.assertEqual(retry.returncode, 0, retry.stderr + retry.stdout)
        self.assertEqual(self.counter_lines(), ["1", "1"])
        self.assertTrue(any((self.out / ".quarantine").iterdir()))

    def test_timeout_does_not_promote_root_artifacts(self):
        write_manifest(self.manifest)
        timed = self.run_runner("--timeout", "1", sleep=3)
        self.assertNotEqual(timed.returncode, 0)
        self.assertFalse((self.out / "m96_k1_01.meta.json").exists())
        self.assertTrue(any((self.out / ".quarantine").iterdir()))

    def test_heartbeat_is_emitted(self):
        write_manifest(self.manifest)
        run = self.run_runner(
            "--timeout", "0", "--heartbeat-seconds", "0.5", "--progress", sleep=1.5
        )
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.assertIn('"event": "heartbeat"', run.stdout)
        self.assertIn("complete", run.stderr)
        self.assertIn("active:", run.stderr)
        self.assertTrue((self.out / "m96_k1_01.meta.json").exists())

    def test_human_status_progress_bar(self):
        write_manifest(self.manifest)
        first = self.run_runner("--timeout", "10")
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)

        status = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--status",
                "--human",
                "--exe",
                str(self.fake),
                "--tasks",
                str(self.manifest),
                "--out",
                str(self.out),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertIn("[", status.stdout)
        self.assertIn("1/1 complete", status.stdout)

    def test_status_reports_rough_eta_from_completed_timings(self):
        write_manifest(self.manifest, count=1)
        first = self.run_runner("--timeout", "10")
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)

        write_manifest(self.manifest, count=2)
        status = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--status",
                "--exe",
                str(self.fake),
                "--tasks",
                str(self.manifest),
                "--out",
                str(self.out),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(status.returncode, 0, status.stderr)
        payload = json.loads(status.stdout)
        self.assertEqual(payload["completed"], 1)
        self.assertEqual(payload["pending"], 1)
        self.assertTrue(payload["estimate"]["available"])
        self.assertEqual(payload["estimate"]["sample_count"], 1)
        self.assertGreaterEqual(payload["estimate"]["remaining_wall_seconds"], 0)

    def test_desc_order_runs_high_k1_first(self):
        write_manifest(self.manifest, count=3)
        run = self.run_runner("--timeout", "10", "--order", "desc")
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.assertEqual(self.counter_lines(), ["3", "2", "1"])

    def test_lock_blocks_second_runner_and_sigint_quarantines(self):
        write_manifest(self.manifest)
        env = os.environ.copy()
        env["FAKE_SLEEP"] = "5"
        first = subprocess.Popen(
            [
                sys.executable,
                str(RUNNER),
                "--exe",
                str(self.fake),
                "--tasks",
                str(self.manifest),
                "--out",
                str(self.out),
                "--jobs",
                "1",
                "--timeout",
                "0",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            deadline = time.time() + 5
            while not (self.out / ".runner.lock").exists() and time.time() < deadline:
                time.sleep(0.1)
            self.assertTrue((self.out / ".runner.lock").exists())

            second = self.run_runner("--timeout", "0")
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("another runner", second.stderr)

            first.send_signal(signal.SIGINT)
            stdout, stderr = first.communicate(timeout=10)
            self.assertEqual(first.returncode, 130, stderr + stdout)
            self.assertFalse((self.out / "m96_k1_01.meta.json").exists())
            self.assertTrue(any((self.out / ".quarantine").iterdir()))
        finally:
            if first.poll() is None:
                first.kill()
                first.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main()
