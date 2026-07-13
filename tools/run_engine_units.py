#!/usr/bin/env python3
"""Resumable process runner for canonical v2 work units."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import resource
import shutil
import signal
import socket
import subprocess
import sys
import time
import platform
from collections import deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canonical_json import atomic_write, load, sha256_file
from verifiers.verify_work_unit_result import verify_result
from tools.split_work_unit import split as split_work_unit
from verifiers.verify_partition_manifest import verify_branch as verify_partition


ENGINE_INFO = {
    "prover": {
        "engine": "cpp-gmp-prover",
        "default_exe": "build/collatz_prover",
        "default_out": "dist/search-v2/results/prover",
    },
    "verifier": {
        "engine": "independent-rust-verifier",
        "default_exe": "build/collatz_verify_unit",
        "default_out": "dist/search-v2/results/verifier",
    },
}
STOP = False


def signal_handler(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def enumerate_units(plan: Path, cases: set[int] | None) -> list[tuple[int, Path]]:
    records = []
    for case_dir in sorted(plan.glob("m*"), key=lambda path: int(path.name[1:])):
        if not case_dir.is_dir() or not case_dir.name[1:].isdigit():
            continue
        m = int(case_dir.name[1:])
        if cases is not None and m not in cases:
            continue
        for branch_dir in sorted(case_dir.glob("k1_*")):
            partition = load(branch_dir / "partition.json")
            for leaf in partition["leaves"]:
                records.append((m, branch_dir / "units" / f"{leaf['unit_id']}.json"))
    return records


def acquire_lock(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    handle = (output / ".runner.lock").open("a+", encoding="ascii")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        handle.close()
        raise RuntimeError(f"another runner owns {output}") from error
    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def acquire_plan_lock(plan: Path, exclusive: bool):
    handle = (plan / ".plan.lock").open("a+", encoding="ascii")
    operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    try:
        fcntl.flock(handle, operation | fcntl.LOCK_NB)
    except BlockingIOError as error:
        handle.close()
        raise RuntimeError(f"another runner owns an incompatible plan lock: {plan}") from error
    return handle


def validate_selected_plan(plan: Path, cases: set[int] | None) -> None:
    selected = sorted(cases if cases is not None else range(92, 97))
    for m in selected:
        config = load(ROOT / f"certificates/config/case_m{m}.json")
        low = int(config["k1_range"]["min"])
        high = int(config["k1_range"]["max"])
        case_dir = plan / f"m{m}"
        expected = {f"k1_{k1:02d}" for k1 in range(low, high + 1)}
        actual = {path.name for path in case_dir.iterdir() if path.is_dir()}
        if actual != expected:
            raise ValueError(f"m={m} branch-directory set mismatch")
        for k1 in range(low, high + 1):
            verify_partition(config, case_dir / f"k1_{k1:02d}", k1)


def quarantine(output: Path, paths: list[Path], reason: str) -> None:
    stamp = f"{int(time.time())}_{reason}"
    target = output / ".quarantine" / stamp
    target.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.exists():
            destination = target / path.name
            counter = 1
            while destination.exists():
                destination = target / f"{path.stem}.{counter}{path.suffix}"
                counter += 1
            os.replace(path, destination)


def command(engine: str, executable: Path, config: Path, unit: Path, partial: Path, threshold: int) -> list[str]:
    common = [
        "--config",
        str(config),
        "--unit",
        str(unit),
        "--output",
        str(partial),
        "--math-certificate",
        str(ROOT / "certificates/analytic/m92_96_reductions.json"),
        "--enum-threshold",
        str(threshold),
    ]
    if engine == "prover":
        return [str(executable), "search-unit", *common]
    return [str(executable), *common]


def valid_existing(
    result: Path,
    config: Path,
    unit: Path,
    engine_name: str,
    executable: Path,
) -> bool:
    if not result.exists():
        return False
    try:
        verify_result(
            config,
            unit,
            result,
            expected_engine=engine_name,
            binary_path=executable,
        )
        return True
    except Exception:
        return False


def terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def active_statuses(output: Path, selected_ids: set[str]) -> tuple[list[dict[str, Any]], int]:
    active = []
    stale = 0
    now = time.time()
    for path in sorted((output / ".status").glob("*.json")):
        try:
            record = load(path)
            pid = int(record["pid"])
            identifier = record["unit_id"]
            if identifier not in selected_ids or not process_exists(pid):
                stale += 1
                continue
            active.append(
                {
                    "unit_id": identifier,
                    "m": int(record["m"]),
                    "pid": pid,
                    "elapsed_seconds": round(now - float(record["started_epoch"]), 3),
                    "log_bytes": int(record["log_bytes"]),
                }
            )
        except Exception:
            stale += 1
    return active, stale


def status_record(item: dict[str, Any]) -> dict[str, str]:
    return {
        "schema": "collatz.runner-status.v1",
        "engine": item["engine"],
        "unit_id": item["unit_id"],
        "m": str(item["m"]),
        "pid": str(item["process"].pid),
        "started_epoch": str(item["started_epoch"]),
        "elapsed_seconds": str(round(time.monotonic() - item["started"], 3)),
        "log_bytes": str(item["log"].stat().st_size if item["log"].exists() else 0),
    }


def write_attempt(
    output: Path,
    item: dict[str, Any],
    *,
    accepted: bool,
    timed_out: bool,
    result: dict[str, Any] | None,
) -> None:
    record = {
        "schema": "collatz.computation-attempt.v1",
        "engine": item["engine"],
        "unit_id": item["unit_id"],
        "m": str(item["m"]),
        "accepted": accepted,
        "timed_out": timed_out,
        "exit_code": item["process"].returncode,
        "started_epoch": str(item["started_epoch"]),
        "elapsed_milliseconds": str(
            max(0, round((time.monotonic() - item["started"]) * 1000))
        ),
        "hostname": socket.gethostname(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "command": item["command"],
        "binary_sha256": sha256_file(item["executable"]),
        "result_id": result["result_id"] if result is not None else None,
    }
    if accepted:
        path = output / ".provenance" / f"{item['unit_id']}.json"
    else:
        path = output / ".attempts" / (
            f"{item['unit_id']}.{item['started_epoch']}.{item['process'].pid}.json"
        )
    atomic_write(path, record)


def run(engine: str, argv: list[str] | None = None) -> int:
    info = ENGINE_INFO[engine]
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="dist/search-v2/plan")
    parser.add_argument("--out", default=info["default_out"])
    parser.add_argument("--exe", default=info["default_exe"])
    parser.add_argument("--case", action="append", type=int, choices=range(92, 97))
    parser.add_argument("--k1", action="append", type=int, choices=range(1, 76))
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=0)
    parser.add_argument("--enum-threshold", type=int, default=256)
    parser.add_argument("--heartbeat-seconds", type=int, default=60)
    parser.add_argument("--memory-mb", type=int, default=0)
    parser.add_argument("--cpu-seconds", type=int, default=0)
    parser.add_argument("--order", choices=("asc", "desc"), default="asc")
    parser.add_argument("--adaptive-split", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume from verified root results (the default behavior)",
    )
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)
    if (
        args.jobs < 1
        or args.timeout < 0
        or args.enum_threshold < 1
        or args.memory_mb < 0
        or args.cpu_seconds < 0
    ):
        parser.error("jobs/threshold must be positive and timeout nonnegative")
    if args.adaptive_split and (engine != "prover" or args.timeout == 0):
        parser.error("--adaptive-split requires the prover and a nonzero timeout")

    plan = (ROOT / args.plan).resolve()
    output = (ROOT / args.out).resolve()
    executable = (ROOT / args.exe).resolve()
    cases = set(args.case) if args.case else None
    plan_lock = None
    if not args.status:
        if not executable.is_file():
            raise RuntimeError(f"engine executable is missing: {executable}")
        plan_lock = acquire_plan_lock(plan, args.adaptive_split)
        validate_selected_plan(plan, cases)
    records = enumerate_units(plan, cases)
    if args.k1:
        selected_k1 = set(args.k1)
        records = [record for record in records if int(load(record[1])["k1"]) in selected_k1]
    if args.order == "desc":
        records.reverse()
    if not records:
        raise RuntimeError("no work units selected")
    selected_ids = {load(unit)["unit_id"] for _, unit in records}
    completed = 0
    invalid = 0
    existing_survivors = 0
    for m, unit in records:
        identifier = load(unit)["unit_id"]
        result = output / f"{identifier}.json"
        config = ROOT / f"certificates/config/case_m{m}.json"
        if valid_existing(result, config, unit, info["engine"], executable):
            completed += 1
            if load(result)["outcome"] == "SURVIVOR":
                existing_survivors += 1
        elif result.exists():
            invalid += 1
    if args.status:
        running, stale_status = active_statuses(output, selected_ids)
        print(
            json.dumps(
                {
                    "engine": info["engine"],
                    "total": len(records),
                    "completed": completed,
                    "running": len(running),
                    "active": running,
                    "pending": len(records) - completed - len(running),
                    "invalid": invalid,
                    "survivors": existing_survivors,
                    "stale_status": stale_status,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    assert plan_lock is not None
    if existing_survivors:
        print(
            json.dumps(
                {
                    "event": "survivor-already-recorded",
                    "engine": info["engine"],
                    "survivors": existing_survivors,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        plan_lock.close()
        return 2

    try:
        lock = acquire_lock(output)
    except Exception:
        plan_lock.close()
        raise
    partial_dir = output / ".partial"
    log_dir = output / ".logs"
    status_dir = output / ".status"
    provenance_dir = output / ".provenance"
    attempts_dir = output / ".attempts"
    partial_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    status_dir.mkdir(parents=True, exist_ok=True)
    provenance_dir.mkdir(parents=True, exist_ok=True)
    attempts_dir.mkdir(parents=True, exist_ok=True)
    for stale in partial_dir.iterdir():
        if stale.is_file():
            quarantine(output, [stale], "stale")
    for stale in status_dir.iterdir():
        if stale.is_file():
            quarantine(output, [stale], "stale-status")

    pending: deque[tuple[int, Path]] = deque()
    for m, unit in records:
        identifier = load(unit)["unit_id"]
        final = output / f"{identifier}.json"
        config = ROOT / f"certificates/config/case_m{m}.json"
        if valid_existing(final, config, unit, info["engine"], executable):
            continue
        if final.exists():
            quarantine(output, [final], "invalid")
        pending.append((m, unit))
    skipped = len(records) - len(pending)
    accepted_count = skipped
    active: dict[int, dict[str, Any]] = {}
    failures = 0
    survivors = 0
    splits = 0
    halt_for_survivor = False
    start = time.monotonic()
    last_heartbeat = 0.0
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    try:
        while pending or active:
            while pending and len(active) < args.jobs and not STOP and not halt_for_survivor:
                m, unit = pending.popleft()
                unit_record = load(unit)
                identifier = unit_record["unit_id"]
                partial = partial_dir / f"{identifier}.json"
                log = log_dir / f"{identifier}.log"
                config = ROOT / f"certificates/config/case_m{m}.json"
                log_handle = log.open("ab")
                child_command = command(
                    engine, executable, config, unit, partial, args.enum_threshold
                )
                process = subprocess.Popen(
                    child_command,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                if args.memory_mb:
                    limit = args.memory_mb * 1024 * 1024
                    resource.prlimit(process.pid, resource.RLIMIT_AS, (limit, limit))
                if args.cpu_seconds:
                    resource.prlimit(
                        process.pid,
                        resource.RLIMIT_CPU,
                        (args.cpu_seconds, args.cpu_seconds),
                    )
                active[process.pid] = {
                    "process": process,
                    "m": m,
                    "k1": int(unit_record["k1"]),
                    "unit": unit,
                    "unit_id": identifier,
                    "partial": partial,
                    "log": log,
                    "log_handle": log_handle,
                    "started": time.monotonic(),
                    "started_epoch": int(time.time()),
                    "config": config,
                    "engine": info["engine"],
                    "status": status_dir / f"{identifier}.json",
                    "command": child_command,
                    "executable": executable,
                }
                atomic_write(active[process.pid]["status"], status_record(active[process.pid]))
            now = time.monotonic()
            for pid, item in list(active.items()):
                process = item["process"]
                timed_out = bool(args.timeout and now - item["started"] > args.timeout)
                if timed_out:
                    terminate(process)
                return_code = process.poll()
                if return_code is None:
                    continue
                item["log_handle"].close()
                item["status"].unlink(missing_ok=True)
                accepted = False
                result = None
                if return_code in (0, 1) and not timed_out and item["partial"].is_file():
                    try:
                        result = verify_result(
                            item["config"],
                            item["unit"],
                            item["partial"],
                            expected_engine=info["engine"],
                            binary_path=executable,
                        )
                        os.replace(item["partial"], output / f"{item['unit_id']}.json")
                        accepted = True
                        accepted_count += 1
                        if result["outcome"] == "SURVIVOR":
                            survivors += 1
                            halt_for_survivor = True
                    except Exception:
                        accepted = False
                if not accepted:
                    if timed_out and args.adaptive_split:
                        branch_dir = item["unit"].parent.parent
                        try:
                            children = split_work_unit(
                                branch_dir, item["unit_id"], item["config"]
                            )
                        except ValueError:
                            failures += 1
                            quarantine(
                                output,
                                [item["partial"], item["log"]],
                                "unsplittable-timeout",
                            )
                        else:
                            verify_partition(
                                load(item["config"]), branch_dir, item["k1"]
                            )
                            pending.extend((item["m"], child) for child in children)
                            splits += 1
                            quarantine(
                                output,
                                [item["partial"], item["log"]],
                                "split-timeout",
                            )
                    else:
                        failures += 1
                        quarantine(
                            output,
                            [item["partial"], item["log"]],
                            "timeout" if timed_out else "failed",
                        )
                write_attempt(
                    output,
                    item,
                    accepted=accepted,
                    timed_out=timed_out,
                    result=result if accepted else None,
                )
                del active[pid]
            if now - last_heartbeat >= args.heartbeat_seconds:
                for item in active.values():
                    atomic_write(item["status"], status_record(item))
                print(
                    json.dumps(
                        {
                            "event": "heartbeat",
                            "engine": info["engine"],
                            "total": len(records) + splits,
                            "completed": accepted_count,
                            "running": len(active),
                            "pending": len(pending),
                            "failed": failures,
                            "survivors": survivors,
                            "splits": splits,
                            "elapsed_seconds": round(now - start, 3),
                            "active": [
                                {
                                    "unit_id": item["unit_id"],
                                    "m": item["m"],
                                    "pid": pid,
                                    "elapsed_seconds": round(now - item["started"], 3),
                                    "log_bytes": (
                                        item["log"].stat().st_size
                                        if item["log"].exists()
                                        else 0
                                    ),
                                }
                                for pid, item in sorted(active.items())
                            ],
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
                last_heartbeat = now
            if STOP or halt_for_survivor:
                for item in active.values():
                    terminate(item["process"])
                    item["log_handle"].close()
                    write_attempt(
                        output,
                        item,
                        accepted=False,
                        timed_out=False,
                        result=None,
                    )
                    quarantine(
                        output,
                        [item["partial"], item["log"], item["status"]],
                        "interrupted" if STOP else "stopped-after-survivor",
                    )
                active.clear()
                break
            time.sleep(0.05)
    finally:
        lock.close()
        plan_lock.close()
    if survivors:
        return 2
    if STOP or failures or pending:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit("invoke run_prover_units.py or run_verifier_units.py")
