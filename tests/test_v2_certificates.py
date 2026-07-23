from __future__ import annotations

import json
import signal
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.canonical_json import (
    atomic_write,
    config_id,
    load,
    partition_id,
    result_id,
    sha256_file,
    strict_loads,
    unit_id,
)
from tools.split_work_unit import split
from tools.aggregate_search_certificate import branch_certificate
from verifiers.verify_partition_manifest import verify_branch
from verifiers.verify_build_provenance import verify_provenance
from verifiers.verify_schemas import schema_validator
from verifiers.verify_work_unit_result import verify_result


ROOT = Path(__file__).resolve().parents[1]


class V2CertificateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.run(
            ["make", "build-prover", "build-fault-prover", "build-rust-verifier"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        subprocess.run(
            [
                "python3",
                "tools/plan_work_units.py",
                "--case",
                "92",
                "--out",
                str(self.temp / "plan"),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def branch(self, k1: int) -> Path:
        return self.temp / "plan" / "m92" / f"k1_{k1:02d}"

    def unit(self, k1: int) -> Path:
        branch = self.branch(k1)
        identifier = load(branch / "partition.json")["leaves"][0]["unit_id"]
        return branch / "units" / f"{identifier}.json"

    def run_pair(self, k1: int) -> tuple[Path, Path]:
        unit = self.unit(k1)
        prover = self.temp / f"prover_{k1}.json"
        verifier = self.temp / f"verifier_{k1}.json"
        common = [
            "--config",
            "certificates/config/case_m92.json",
            "--unit",
            str(unit),
            "--enum-threshold",
            "256",
        ]
        subprocess.run(
            [
                str(ROOT / "build/collatz_prover"),
                "search-unit",
                *common,
                "--output",
                str(prover),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                str(ROOT / "build/collatz_verify_unit"),
                *common,
                "--output",
                str(verifier),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        return prover, verifier

    def test_complete_case_partition_accepts(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "verifiers/verify_partition_manifest.py",
                "--case",
                "92",
                "--partitions",
                str(self.temp / "plan"),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(result.stdout)["verified_branches"], 73)

    def test_authoritative_build_allowlist_accepts(self) -> None:
        engines = verify_provenance(
            ROOT / "release/build_provenance/authoritative_binaries.json"
        )
        self.assertEqual(
            list(engines), ["cpp-gmp-prover", "independent-rust-verifier"]
        )

    def test_midpoint_split_remains_exact(self) -> None:
        branch = self.branch(29)
        identifier = load(branch / "partition.json")["leaves"][0]["unit_id"]
        split(branch, identifier, ROOT / "certificates/config/case_m92.json")
        config = load(ROOT / "certificates/config/case_m92.json")
        self.assertEqual(verify_branch(config, branch, 29), 2)

    def test_partition_gap_is_rejected(self) -> None:
        branch = self.branch(29)
        identifier = load(branch / "partition.json")["leaves"][0]["unit_id"]
        split(branch, identifier, ROOT / "certificates/config/case_m92.json")
        partition_path = branch / "partition.json"
        partition = load(partition_path)
        bad_start = str(int(partition["tree"]["right"]["start"]) + 1)
        partition["tree"]["right"]["start"] = bad_start
        partition["leaves"][1]["start"] = bad_start
        partition["partition_id"] = partition_id(partition)
        atomic_write(partition_path, partition)
        config = load(ROOT / "certificates/config/case_m92.json")
        with self.assertRaisesRegex(ValueError, "interval mismatch"):
            verify_branch(config, branch, 29)

    def test_partition_overlap_is_rejected(self) -> None:
        branch = self.branch(29)
        identifier = load(branch / "partition.json")["leaves"][0]["unit_id"]
        split(branch, identifier, ROOT / "certificates/config/case_m92.json")
        partition_path = branch / "partition.json"
        partition = load(partition_path)
        bad_start = partition["tree"]["left"]["end"]
        partition["tree"]["right"]["start"] = bad_start
        partition["leaves"][1]["start"] = bad_start
        partition["partition_id"] = partition_id(partition)
        atomic_write(partition_path, partition)
        config = load(ROOT / "certificates/config/case_m92.json")
        with self.assertRaisesRegex(ValueError, "interval mismatch"):
            verify_branch(config, branch, 29)

    def test_extra_unmanifested_unit_is_rejected(self) -> None:
        branch = self.branch(29)
        shutil.copyfile(self.unit(29), branch / "units" / ("0" * 64 + ".json"))
        config = load(ROOT / "certificates/config/case_m92.json")
        with self.assertRaisesRegex(ValueError, "unexpected or missing work-unit file"):
            verify_branch(config, branch, 29)

    def test_recursive_cross_engine_result_matches(self) -> None:
        prover_path, verifier_path = self.run_pair(29)
        unit = self.unit(29)
        config = ROOT / "certificates/config/case_m92.json"
        prover = verify_result(
            config,
            unit,
            prover_path,
            expected_engine="cpp-gmp-prover",
            binary_path=ROOT / "build/collatz_prover",
        )
        verifier = verify_result(
            config,
            unit,
            verifier_path,
            expected_engine="independent-rust-verifier",
            binary_path=ROOT / "build/collatz_verify_unit",
        )
        self.assertEqual(prover["counters"], verifier["counters"])
        self.assertEqual(prover["counters"]["recursive_nodes"], "574")
        self.assertEqual(prover["hits"], "0")

    def test_changed_config_is_rejected_by_both_engines(self) -> None:
        config = load(ROOT / "certificates/config/case_m92.json")
        config["k_caps"][0] = str(int(config["k_caps"][0]) + 1)
        changed = self.temp / "changed_config.json"
        atomic_write(changed, config)
        unit = self.unit(73)
        commands = [
            [
                str(ROOT / "build/collatz_prover"),
                "search-unit",
                "--config",
                str(changed),
                "--unit",
                str(unit),
                "--output",
                str(self.temp / "bad_cpp.json"),
            ],
            [
                str(ROOT / "build/collatz_verify_unit"),
                "--config",
                str(changed),
                "--unit",
                str(unit),
                "--output",
                str(self.temp / "bad_rust.json"),
            ],
        ]
        for command in commands:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("config semantics", result.stderr)

    def test_debug_terminal_dumps_match_byte_for_byte(self) -> None:
        unit = self.unit(73)
        cpp_dump = self.temp / "cpp_dump.json"
        rust_dump = self.temp / "rust_dump.json"
        commands = [
            [
                str(ROOT / "build/collatz_prover"),
                "search-unit",
                "--config",
                "certificates/config/case_m92.json",
                "--unit",
                str(unit),
                "--output",
                str(self.temp / "cpp_dump_result.json"),
                "--debug-terminal-dump",
                str(cpp_dump),
            ],
            [
                str(ROOT / "build/collatz_verify_unit"),
                "--config",
                "certificates/config/case_m92.json",
                "--unit",
                str(unit),
                "--output",
                str(self.temp / "rust_dump_result.json"),
                "--debug-terminal-dump",
                str(rust_dump),
            ],
        ]
        for command in commands:
            subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
        self.assertEqual(cpp_dump.read_bytes(), rust_dump.read_bytes())
        self.assertEqual(load(cpp_dump)["decisions"], [{"a1": "1", "outcome": "STAGE_MINIMUM"}])

    def test_mutated_result_is_rejected_even_with_recomputed_id(self) -> None:
        prover_path, _ = self.run_pair(73)
        result = load(prover_path)
        result["hits"] = "1"
        result["result_id"] = result_id(result)
        atomic_write(prover_path, result)
        with self.assertRaisesRegex(ValueError, "outcome/hit-count"):
            verify_result(
                ROOT / "certificates/config/case_m92.json",
                self.unit(73),
                prover_path,
                expected_engine="cpp-gmp-prover",
                binary_path=ROOT / "build/collatz_prover",
            )

    def test_result_identity_and_completeness_mutations_are_rejected(self) -> None:
        prover_path, _ = self.run_pair(73)
        base = load(prover_path)
        mutations = {
            "source": ({"source_sha256": "0" * 64}, "source hash"),
            "binary": ({"binary_sha256": "0" * 64}, "binary hash"),
            "timeout": ({"outcome": "ERROR"}, "outcome/hit-count"),
        }
        for name, (changes, message) in mutations.items():
            with self.subTest(name=name):
                changed = dict(base)
                changed.update(changes)
                changed["result_id"] = result_id(changed)
                path = self.temp / f"mutated_{name}.json"
                atomic_write(path, changed)
                with self.assertRaisesRegex(ValueError, message):
                    verify_result(
                        ROOT / "certificates/config/case_m92.json",
                        self.unit(73),
                        path,
                        expected_engine="cpp-gmp-prover",
                        binary_path=ROOT / "build/collatz_prover",
                    )
        truncated = self.temp / "truncated.json"
        truncated.write_text('{"schema":"collatz.engine-result.v1"', encoding="ascii")
        with self.assertRaises(ValueError):
            verify_result(
                ROOT / "certificates/config/case_m92.json",
                self.unit(73),
                truncated,
                expected_engine="cpp-gmp-prover",
                binary_path=ROOT / "build/collatz_prover",
            )

    def test_out_of_root_unit_range_is_rejected(self) -> None:
        branch = self.branch(29)
        partition_path = branch / "partition.json"
        partition = load(partition_path)
        old_id = partition["leaves"][0]["unit_id"]
        unit_path = branch / "units" / f"{old_id}.json"
        unit = load(unit_path)
        unit["index_range"]["end"] = unit["root"]["count"]
        unit["unit_id"] = unit_id(unit)
        new_path = branch / "units" / f"{unit['unit_id']}.json"
        atomic_write(new_path, unit)
        unit_path.unlink()
        partition["leaves"][0]["unit_id"] = unit["unit_id"]
        partition["leaves"][0]["end"] = unit["index_range"]["end"]
        partition["tree"]["unit_id"] = unit["unit_id"]
        partition["tree"]["end"] = unit["index_range"]["end"]
        partition["partition_id"] = partition_id(partition)
        atomic_write(partition_path, partition)
        config = load(ROOT / "certificates/config/case_m92.json")
        with self.assertRaisesRegex(ValueError, "partition tree node interval"):
            verify_branch(config, branch, 29)

    def test_missing_or_disagreeing_independent_result_is_rejected(self) -> None:
        prover_path, verifier_path = self.run_pair(73)
        identifier = load(prover_path)["unit_id"]
        prover_dir = self.temp / "aggregate-prover"
        verifier_dir = self.temp / "aggregate-verifier"
        prover_dir.mkdir()
        verifier_dir.mkdir()
        shutil.copyfile(prover_path, prover_dir / f"{identifier}.json")
        with self.assertRaises(ValueError):
            branch_certificate(
                92,
                self.branch(73),
                ROOT / "certificates/config/case_m92.json",
                prover_dir,
                verifier_dir,
                ROOT / "build/collatz_prover",
                ROOT / "build/collatz_verify_unit",
            )
        verifier = load(verifier_path)
        verifier["counters"]["recursive_nodes"] = str(
            int(verifier["counters"]["recursive_nodes"]) + 1
        )
        verifier["result_id"] = result_id(verifier)
        atomic_write(verifier_dir / f"{identifier}.json", verifier)
        with self.assertRaisesRegex(ValueError, "counter disagreement"):
            branch_certificate(
                92,
                self.branch(73),
                ROOT / "certificates/config/case_m92.json",
                prover_dir,
                verifier_dir,
                ROOT / "build/collatz_prover",
                ROOT / "build/collatz_verify_unit",
            )

    def test_runner_preserves_survivor_and_stops(self) -> None:
        prover_path, _ = self.run_pair(73)
        fake = self.temp / "fake_survivor_engine.py"
        template = self.temp / "survivor_template.json"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, shutil, sys\n"
            f"template = pathlib.Path({str(template)!r})\n"
            "output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
            "shutil.copyfile(template, output)\n"
            "raise SystemExit(1)\n",
            encoding="ascii",
        )
        fake.chmod(0o755)
        result = load(prover_path)
        result["binary_sha256"] = sha256_file(fake)
        result["hits"] = "1"
        result["outcome"] = "SURVIVOR"
        result["result_id"] = result_id(result)
        atomic_write(template, result)
        output = self.temp / "runner-results"
        command = [
            "python3",
            "tools/run_prover_units.py",
            "--case",
            "92",
            "--plan",
            str(self.temp / "plan"),
            "--out",
            str(output),
            "--exe",
            str(fake),
            "--order",
            "desc",
            "--heartbeat-seconds",
            "1",
        ]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertTrue((output / f"{result['unit_id']}.json").is_file())
        self.assertEqual(len(list(output.glob("*.json"))), 1)
        provenance = load(output / ".provenance" / f"{result['unit_id']}.json")
        self.assertTrue(provenance["accepted"])
        self.assertEqual(provenance["result_id"], result["result_id"])
        status = subprocess.run(
            [*command, "--status"], cwd=ROOT, check=True, capture_output=True, text=True
        )
        summary = json.loads(status.stdout)
        self.assertEqual(summary["survivors"], 1)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["pending"], 72)

    def test_runner_timeout_is_replaced_by_exact_children(self) -> None:
        target_branch = self.branch(29)
        parent_id = load(target_branch / "partition.json")["leaves"][0]["unit_id"]
        fake = self.temp / "adaptive_engine.py"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import hashlib, pathlib, subprocess, sys, time\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            "from tools.canonical_json import atomic_write, load, result_id\n"
            "unit_path = pathlib.Path(sys.argv[sys.argv.index('--unit') + 1])\n"
            f"if load(unit_path)['unit_id'] == {parent_id!r}:\n"
            "    time.sleep(10)\n"
            "    raise SystemExit(2)\n"
            f"command = [{str(ROOT / 'build/collatz_prover')!r}, *sys.argv[1:]]\n"
            "completed = subprocess.run(command)\n"
            "output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
            "result = load(output)\n"
            "result['binary_sha256'] = hashlib.sha256(pathlib.Path(sys.argv[0]).read_bytes()).hexdigest()\n"
            "result['result_id'] = result_id(result)\n"
            "atomic_write(output, result)\n"
            "raise SystemExit(completed.returncode)\n",
            encoding="ascii",
        )
        fake.chmod(0o755)
        output = self.temp / "adaptive-results"
        command = [
            "python3",
            "tools/run_prover_units.py",
            "--case",
            "92",
            "--plan",
            str(self.temp / "plan"),
            "--k1",
            "29",
            "--out",
            str(output),
            "--exe",
            str(fake),
            "--jobs",
            "2",
            "--timeout",
            "1",
            "--adaptive-split",
            "--heartbeat-seconds",
            "1",
        ]
        run = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(run.returncode, 0, run.stderr or run.stdout)
        config = load(ROOT / "certificates/config/case_m92.json")
        self.assertEqual(verify_branch(config, target_branch, 29), 2)
        self.assertEqual(len(list(output.glob("*.json"))), 2)
        self.assertEqual(len(list((output / ".provenance").glob("*.json"))), 2)
        self.assertEqual(len(list((output / ".attempts").glob("*.json"))), 1)
        status = subprocess.run(
            [*command, "--status"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        summary = json.loads(status.stdout)
        self.assertEqual(summary["branches"]["completed"], 1)
        self.assertEqual(summary["history"]["timed_out_attempts"], 1)
        self.assertGreater(summary["history"]["discarded_timeout_cpu_hours"], 0)

    def test_adaptive_children_run_before_untouched_peers(self) -> None:
        plan = self.temp / "priority-plan"
        subprocess.run(
            [
                "python3",
                "tools/plan_work_units.py",
                "--case",
                "92",
                "--segments-per-branch",
                "2",
                "--out",
                str(plan),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        branch = plan / "m92/k1_29"
        parent_id = load(branch / "partition.json")["leaves"][0]["unit_id"]
        starts = self.temp / "starts.txt"
        fake = self.temp / "priority_engine.py"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import hashlib, pathlib, subprocess, sys, time\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            "from tools.canonical_json import atomic_write, load, result_id\n"
            "unit_path = pathlib.Path(sys.argv[sys.argv.index('--unit') + 1])\n"
            "identifier = load(unit_path)['unit_id']\n"
            f"with pathlib.Path({str(starts)!r}).open('a', encoding='ascii') as handle:\n"
            "    handle.write(identifier + '\\n')\n"
            f"if identifier == {parent_id!r}:\n"
            "    time.sleep(10)\n"
            "    raise SystemExit(2)\n"
            f"command = [{str(ROOT / 'build/collatz_prover')!r}, *sys.argv[1:]]\n"
            "completed = subprocess.run(command)\n"
            "output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
            "result = load(output)\n"
            "result['binary_sha256'] = hashlib.sha256(pathlib.Path(sys.argv[0]).read_bytes()).hexdigest()\n"
            "result['result_id'] = result_id(result)\n"
            "atomic_write(output, result)\n"
            "raise SystemExit(completed.returncode)\n",
            encoding="ascii",
        )
        fake.chmod(0o755)
        run = subprocess.run(
            [
                "python3",
                "tools/run_prover_units.py",
                "--case",
                "92",
                "--k1",
                "29",
                "--plan",
                str(plan),
                "--out",
                str(self.temp / "priority-results"),
                "--exe",
                str(fake),
                "--jobs",
                "1",
                "--timeout",
                "1",
                "--adaptive-split",
                "--heartbeat-seconds",
                "1",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(run.returncode, 0, run.stderr or run.stdout)
        final_leaves = load(branch / "partition.json")["leaves"]
        order = starts.read_text(encoding="ascii").splitlines()
        self.assertEqual(order[0], parent_id)
        self.assertEqual(order[1:3], [leaf["unit_id"] for leaf in final_leaves[:2]])

    def test_selected_replan_quarantines_orphan_result(self) -> None:
        output = self.temp / "replan-results"
        command = [
            "python3",
            "tools/run_prover_units.py",
            "--case",
            "92",
            "--k1",
            "29",
            "--plan",
            str(self.temp / "plan"),
            "--out",
            str(output),
            "--exe",
            str(ROOT / "build/collatz_prover"),
            "--heartbeat-seconds",
            "1",
        ]
        first = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
        old_result = next(output.glob("*.json"))
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
                str(self.temp / "plan"),
                "--replace-selected",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        status = subprocess.run(
            [*command, "--status"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(status.stdout)["orphan_results"], 1)
        second = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(second.returncode, 0, second.stderr or second.stdout)
        self.assertFalse(old_result.exists())
        self.assertEqual(len(list(output.glob("*.json"))), 2)
        self.assertTrue(list((output / ".quarantine").rglob(old_result.name)))

    def test_adaptive_split_limit_stops_pilot(self) -> None:
        sleeper = self.temp / "split_limit_engine.py"
        sleeper.write_text(
            "#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n",
            encoding="ascii",
        )
        sleeper.chmod(0o755)
        output = self.temp / "split-limit-results"
        run = subprocess.run(
            [
                "python3",
                "tools/run_prover_units.py",
                "--case",
                "92",
                "--k1",
                "29",
                "--plan",
                str(self.temp / "plan"),
                "--out",
                str(output),
                "--exe",
                str(sleeper),
                "--jobs",
                "1",
                "--timeout",
                "1",
                "--adaptive-split",
                "--stop-after-splits",
                "1",
                "--heartbeat-seconds",
                "1",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(run.returncode, 1, run.stderr or run.stdout)
        config = load(ROOT / "certificates/config/case_m92.json")
        self.assertEqual(verify_branch(config, self.branch(29), 29), 2)
        self.assertFalse(list(output.glob("*.json")))
        self.assertEqual(len(list((output / ".attempts").glob("*.json"))), 1)

    def test_status_reports_active_unit_and_interrupt_cleans_it(self) -> None:
        sleeper = self.temp / "sleep_engine.py"
        sleeper.write_text(
            "#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n",
            encoding="ascii",
        )
        sleeper.chmod(0o755)
        output = self.temp / "status-results"
        command = [
            "python3",
            "tools/run_prover_units.py",
            "--case",
            "92",
            "--plan",
            str(self.temp / "plan"),
            "--k1",
            "73",
            "--out",
            str(output),
            "--exe",
            str(sleeper),
            "--jobs",
            "1",
            "--heartbeat-seconds",
            "1",
        ]
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 5
            while not list((output / ".status").glob("*.json")):
                if process.poll() is not None or time.monotonic() >= deadline:
                    break
                time.sleep(0.02)
            status = subprocess.run(
                [*command, "--status"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(status.stdout)["running"], 1, status.stdout)
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 1, stderr or stdout)
            self.assertFalse(list((output / ".status").glob("*.json")))
            self.assertEqual(len(list((output / ".attempts").glob("*.json"))), 1)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_fault_injected_prover_disagrees_and_is_not_certifiable(self) -> None:
        _, verifier_path = self.run_pair(29)
        unit = self.unit(29)
        faults = [
            "skip-first-ell",
            "reverse-hensel-child",
            "omit-first-a1",
            "weaken-minimum",
            "change-floor-alpha",
            "report-false-hit",
        ]
        for fault in faults:
            with self.subTest(fault=fault):
                fault_result = self.temp / f"fault_{fault}.json"
                completed = subprocess.run(
                    [
                        str(ROOT / "build/collatz_prover_fault"),
                        "search-unit",
                        "--config",
                        "certificates/config/case_m92.json",
                        "--unit",
                        str(unit),
                        "--output",
                        str(fault_result),
                        "--enum-threshold",
                        "256",
                        "--fault",
                        fault,
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                if fault_result.exists():
                    with self.assertRaisesRegex(ValueError, "semantic parameters"):
                        verify_result(
                            ROOT / "certificates/config/case_m92.json",
                            unit,
                            fault_result,
                            expected_engine="cpp-gmp-prover",
                            binary_path=ROOT / "build/collatz_prover_fault",
                        )
                    self.assertNotEqual(
                        load(fault_result), load(verifier_path), fault
                    )
                else:
                    self.assertEqual(completed.returncode, 2, completed.stderr)

        production = subprocess.run(
            [
                str(ROOT / "build/collatz_prover"),
                "search-unit",
                "--config",
                "certificates/config/case_m92.json",
                "--unit",
                str(unit),
                "--output",
                str(self.temp / "forbidden_fault.json"),
                "--fault",
                "skip-first-ell",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(production.returncode, 2)
        self.assertIn("unknown option", production.stderr)

    def test_duplicate_json_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            strict_loads('{"schema":"x","schema":"x"}')

    def test_symlinked_unit_is_rejected(self) -> None:
        unit = self.unit(73)
        link = self.temp / "unit-link.json"
        link.symlink_to(unit)
        with self.assertRaisesRegex(ValueError, "regular file"):
            load(link)

    def test_schemas_accept_generated_objects(self) -> None:
        schema_dir = ROOT / "schemas"
        schemas = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in schema_dir.glob("*.schema.json")
        }
        for schema in schemas.values():
            Draft202012Validator.check_schema(schema)
        prover, _ = self.run_pair(29)
        objects = {
            "case_config.schema.json": load(
                ROOT / "certificates/config/case_m92.json"
            ),
            "work_unit.schema.json": load(self.unit(29)),
            "root_partition.schema.json": load(
                self.branch(29) / "partition.json"
            ),
            "engine_result.schema.json": load(prover),
        }
        for name, value in objects.items():
            schema_validator(schemas[name], schemas).validate(value)


if __name__ == "__main__":
    unittest.main()
