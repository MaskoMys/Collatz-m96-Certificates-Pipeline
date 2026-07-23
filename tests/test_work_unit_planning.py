from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.canonical_json import load
from tools.plan_work_units import planned_segments
from verifiers.verify_partition_manifest import verify_branch


ROOT = Path(__file__).resolve().parents[1]


class WorkUnitPlanningTest(unittest.TestCase):
    def test_timing_partition_can_be_capped(self) -> None:
        self.assertEqual(planned_segments(68, 10_000), 128)
        self.assertEqual(planned_segments(68, 10_000, 2), 2)
        self.assertEqual(planned_segments(68, 10_000, 30), 30)

    def test_replace_selected_preserves_other_cases_and_archives_old_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = root / "plan"
            subprocess.run(
                [
                    "python3",
                    "tools/plan_work_units.py",
                    "--case",
                    "92",
                    "--case",
                    "93",
                    "--out",
                    str(plan),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            preserved = load(plan / "m93/k1_01/partition.json")["partition_id"]
            subprocess.run(
                [
                    "python3",
                    "tools/plan_work_units.py",
                    "--case",
                    "92",
                    "--segments-per-branch",
                    "2",
                    "--max-segments-per-branch",
                    "2",
                    "--out",
                    str(plan),
                    "--replace-selected",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                load(plan / "m93/k1_01/partition.json")["partition_id"],
                preserved,
            )
            self.assertEqual(
                len(load(plan / "m92/k1_29/partition.json")["leaves"]),
                2,
            )
            archives = list(root.glob("plan.retired-*"))
            self.assertEqual(len(archives), 1)
            self.assertTrue((archives[0] / "m92/k1_29/partition.json").is_file())
            config = load(ROOT / "certificates/config/case_m92.json")
            self.assertEqual(verify_branch(config, plan / "m92/k1_29", 29), 2)


if __name__ == "__main__":
    unittest.main()
