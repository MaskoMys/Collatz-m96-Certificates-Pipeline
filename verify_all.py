#!/usr/bin/env python3
"""Verify the complete committed certificate artifact without rerunning searches."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
EXPECTED_BRANCHES = {
    92: (73, "ffb745aa8226dcb48a3389bf2581157f0c4def031db606c06614d3e3c1754a51"),
    93: (74, "99b4ba724a45fa0c7b865156e62beb472a46480c4eaaef9a6ee16efb4b546f72"),
    94: (75, "24719b6162ac277a6814862839105c64e6398571fafbd6bacc7f1d183cdd0970"),
    95: (75, "9c0b50f74d3a0fdcd57b3cc7abefb4efd7ed5bf1eb6f1a20697e5045ddb60fe3"),
    96: (75, "d8f99127dceeccd3a9fbcee254a0334fa9940a9cc8d231801e7d46adcd0b2f65"),
}


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise AssertionError(f"command failed: {' '.join(command)}\n{details}")
    return result


def run_json(command: list[str]) -> dict[str, object]:
    return json.loads(run(command).stdout)


def compare_directories(committed: Path, generated: Path, label: str) -> None:
    expected = sorted(
        path.relative_to(committed).as_posix()
        for path in committed.rglob("*")
        if path.is_file()
    )
    actual = sorted(
        path.relative_to(generated).as_posix()
        for path in generated.rglob("*")
        if path.is_file()
    )
    if actual != expected:
        raise AssertionError(f"regenerated {label} certificate set mismatch")
    for name in expected:
        if (committed / name).read_bytes() != (generated / name).read_bytes():
            raise AssertionError(f"{label} certificate does not regenerate: {name}")


def verify_regeneration() -> None:
    committed = ROOT / "certificates" / "reductions"
    with tempfile.TemporaryDirectory() as tmp:
        temporary = Path(tmp)
        output = temporary / "reductions"
        run(
            [
                PYTHON,
                "scripts/generate_reduction_certificates.py",
                "--out",
                str(output),
            ]
        )
        compare_directories(committed, output, "reduction")

        frontier_output = temporary / "frontier"
        run([PYTHON, "scripts/generate_frontier_certificate.py", "--out", str(frontier_output)])
        run(
            [
                PYTHON,
                "scripts/generate_frontier_oracle.py",
                "--out",
                str(frontier_output / "oracle_summary.json"),
            ]
        )
        a29_executable = temporary / "independent_a29_scan"
        run(
            [
                "g++",
                "-O3",
                "-std=c++17",
                "src/frontier/independent_a29_scan.cpp",
                "-o",
                str(a29_executable),
            ]
        )
        a29_result = run([str(a29_executable)])
        (frontier_output / "a29_scan_summary.json").write_text(
            a29_result.stdout, encoding="utf-8"
        )
        compare_directories(ROOT / "certificates" / "frontier", frontier_output, "frontier")

        spike_output = temporary / "first_spike.json"
        run([PYTHON, "scripts/generate_first_spike_certificate.py", "--out", str(spike_output)])
        if spike_output.read_bytes() != (ROOT / "certificates" / "first_spike.json").read_bytes():
            raise AssertionError("first-spike certificate does not regenerate")

        descent_output = temporary / "descent"
        run([PYTHON, "scripts/generate_descent_certificates.py", "--out", str(descent_output)])
        compare_directories(ROOT / "certificates" / "descent", descent_output, "descent")


def branch_command(m: int) -> list[str]:
    if m == 96:
        tasks = "manifests/tasks.jsonl"
        runs = "examples/m96_full_run_2026-07-06/runs"
    else:
        base = "examples/m92_m95_full_runs_2026-07-09"
        tasks = f"{base}/manifests/tasks_m{m}.jsonl"
        runs = f"{base}/m{m}/runs"
    return [
        PYTHON,
        "scripts/verify_certificate.py",
        "--tasks",
        tasks,
        "--runs",
        runs,
        "--source",
        "src/m96/affine_ladder_prefix.cpp",
        "--exe",
        "./build/affine_ladder_prefix",
    ]


def verify_independent_a29_scan() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        executable = Path(tmp) / "independent_a29_scan"
        run(
            [
                "g++",
                "-O3",
                "-std=c++17",
                "-Wall",
                "-Wextra",
                "-Werror",
                "src/frontier/independent_a29_scan.cpp",
                "-o",
                str(executable),
            ]
        )
        return run_json(
            [PYTHON, "scripts/verify_a29_scan.py", "--exe", str(executable)]
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    release = run_json([PYTHON, "scripts/verify_release_manifest.py"])
    reductions = run_json([PYTHON, "scripts/verify_reduction_certificates.py"])
    frontier = run_json([PYTHON, "scripts/verify_frontier_certificate.py"])
    frontier_oracle = run_json([PYTHON, "scripts/verify_frontier_oracle.py"])
    a29_scan_record = run_json([PYTHON, "scripts/verify_a29_scan.py"])
    a29_scan_reproduction = verify_independent_a29_scan()
    first_spike = run_json([PYTHON, "scripts/verify_first_spike_certificate.py"])
    descent = run_json([PYTHON, "scripts/verify_descent_certificates.py"])
    verify_regeneration()

    branches = {}
    for m, (count, digest) in EXPECTED_BRANCHES.items():
        result = run_json(branch_command(m))
        if result.get("result") != "ACCEPT":
            raise AssertionError(f"m={m} branch verifier did not accept")
        if result.get("verified_tasks") != count or result.get("combined_log_hash") != digest:
            raise AssertionError(f"m={m} branch summary mismatch")
        branches[str(m)] = result

    tests = "SKIPPED"
    if not args.skip_tests:
        run([PYTHON, "-m", "unittest", "discover", "-s", "tests"])
        tests = "ACCEPT"

    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "release_integrity": release,
                "analytic_reductions": reductions,
                "frontier_certificate": frontier,
                "frontier_oracle": frontier_oracle,
                "a29_scan_record": a29_scan_record,
                "a29_scan_reproduction": a29_scan_reproduction,
                "first_spike_certificate": first_spike,
                "descent_certificates": descent,
                "branch_certificates": branches,
                "reduction_regeneration": "ACCEPT",
                "adversarial_tests": tests,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"REJECT: {error}", file=sys.stderr)
        raise SystemExit(1)
