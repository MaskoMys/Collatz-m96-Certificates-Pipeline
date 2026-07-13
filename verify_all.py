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


def verify_fast(skip_tests: bool) -> dict[str, object]:
    release = run_json([PYTHON, "scripts/verify_release_manifest.py"])
    authoritative_builds = run_json(
        [PYTHON, "verifiers/verify_build_provenance.py"]
    )
    reductions = run_json([PYTHON, "scripts/verify_reduction_certificates.py"])
    engineering_reductions = run_json(
        [PYTHON, "verifiers/verify_mathematical_reductions.py"]
    )
    schemas = run_json([PYTHON, "verifiers/verify_schemas.py"])
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
    if not skip_tests:
        run(["make", "test"])
        tests = "ACCEPT"
    return {
        "result": "ACCEPT",
        "profile": "fast",
        "theorem_marker": None,
        "release_integrity": release,
        "authoritative_builds": authoritative_builds,
        "analytic_reductions": reductions,
        "engineering_analytic_inputs": engineering_reductions,
        "engineering_schemas": schemas,
        "frontier_certificate": frontier,
        "frontier_oracle": frontier_oracle,
        "a29_scan_record": a29_scan_record,
        "a29_scan_reproduction": a29_scan_reproduction,
        "first_spike_certificate": first_spike,
        "descent_certificates": descent,
        "legacy_branch_records": branches,
        "reduction_regeneration": "ACCEPT",
        "adversarial_tests": tests,
    }


def verify_theorem_artifacts(args: argparse.Namespace) -> dict[str, object]:
    result = run_json(
        [
            PYTHON,
            "verifiers/verify_global_search_certificate.py",
            "--plan",
            args.search_plan,
            "--prover-results",
            args.prover_results,
            "--verifier-results",
            args.verifier_results,
            "--certificates",
            args.search_certificates,
            "--prover-binary",
            args.prover_binary,
            "--verifier-binary",
            args.verifier_binary,
            "--build-provenance",
            args.build_provenance,
            "--computation-provenance",
            args.computation_provenance,
        ]
    )
    if result.get("computational_marker") != "ACCEPT_COMPUTATIONAL_ARTIFACT_SET_M_LE_96":
        raise AssertionError("global artifact verifier did not emit its computational marker")
    return result


def verify_full_replay(args: argparse.Namespace) -> dict[str, object]:
    artifact_result = verify_theorem_artifacts(args)
    stored = ROOT / args.verifier_results
    with tempfile.TemporaryDirectory() as temporary:
        fresh = Path(temporary) / "verifier-results"
        run(
            [
                PYTHON,
                "tools/run_verifier_units.py",
                "--plan",
                args.search_plan,
                "--out",
                str(fresh),
                "--exe",
                args.verifier_binary,
                "--jobs",
                str(args.jobs),
                "--heartbeat-seconds",
                "300",
            ]
        )
        expected = sorted(path.name for path in stored.glob("*.json"))
        actual = sorted(path.name for path in fresh.glob("*.json"))
        if actual != expected:
            raise AssertionError("fresh replay result-file set mismatch")
        for name in expected:
            if (stored / name).read_bytes() != (fresh / name).read_bytes():
                raise AssertionError(f"fresh replay differs from frozen result: {name}")
    return {
        "result": "ACCEPT",
        "profile": "full-replay",
        "artifact_verification": artifact_result,
        "computational_marker": "ACCEPT_COMPUTATIONAL_REPLAY_M_LE_96",
        "theorem_marker": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        choices=("fast", "theorem-artifacts", "full-replay"),
        default="fast",
    )
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--search-plan", default="certificates/search-v2/plan")
    parser.add_argument(
        "--prover-results", default="certificates/search-v2/results/prover"
    )
    parser.add_argument(
        "--verifier-results", default="certificates/search-v2/results/verifier"
    )
    parser.add_argument(
        "--search-certificates", default="certificates/search-v2/certificates"
    )
    parser.add_argument("--prover-binary", default="release/bin/collatz_prover")
    parser.add_argument(
        "--verifier-binary", default="release/bin/collatz_verify_unit"
    )
    parser.add_argument(
        "--build-provenance",
        default="release/build_provenance/authoritative_binaries.json",
    )
    parser.add_argument(
        "--computation-provenance", default="release/computation_provenance"
    )
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")

    fast = verify_fast(args.skip_tests)
    if args.profile == "fast":
        result = fast
    elif args.profile == "theorem-artifacts":
        result = {
            "result": "ACCEPT",
            "profile": "theorem-artifacts",
            "fast_verification": fast,
            "search_verification": verify_theorem_artifacts(args),
            "computational_marker": "ACCEPT_COMPUTATIONAL_ARTIFACT_SET_M_LE_96",
            "theorem_marker": None,
        }
    else:
        result = {
            "result": "ACCEPT",
            "profile": "full-replay",
            "fast_verification": fast,
            **verify_full_replay(args),
        }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"REJECT: {error}", file=sys.stderr)
        raise SystemExit(1)
