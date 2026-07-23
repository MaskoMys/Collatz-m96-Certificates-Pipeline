#!/usr/bin/env python3
"""Plan exact midpoint work-unit partitions for all mathematical roots."""

from __future__ import annotations

import argparse
import fcntl
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canonical_json import atomic_write, load, parse_nat, partition_id
from tools.historical_timings import historical_seconds
from tools.work_units import make_unit, midpoint_tree, root_progression


CASES = range(92, 97)


def planned_segments(requested: int, count: int, maximum: int | None = None) -> int:
    if requested < 1 or count < 1:
        raise ValueError("segment and root counts must be positive")
    requested = min(requested, count)
    segments = min(1 << (requested - 1).bit_length(), count)
    if maximum is not None:
        segments = min(segments, maximum)
    return segments


def ranges_for(count: int, segments: int) -> list[tuple[int, int]]:
    if count <= 0:
        return [(0, 0)]
    segments = min(segments, count)
    ranges = []
    for index in range(segments):
        start = index * count // segments
        end = (index + 1) * count // segments - 1
        if start <= end:
            ranges.append((start, end))
    return ranges


def plan_branch(
    config: dict[str, Any], k1: int, segments: int, branch_dir: Path
) -> dict[str, Any]:
    root = root_progression(config, k1)
    count = int(root["count"])
    units = [make_unit(config, k1, root, start, end) for start, end in ranges_for(count, segments)]
    units_dir = branch_dir / "units"
    units_dir.mkdir(parents=True, exist_ok=True)
    for unit in units:
        atomic_write(units_dir / f"{unit['unit_id']}.json", unit)
    leaves = [
        {
            "unit_id": unit["unit_id"],
            "start": unit["index_range"]["start"],
            "end": unit["index_range"]["end"],
        }
        for unit in units
    ]
    partition = {
        "schema": "collatz.root-partition.v1",
        "config_id": unit_config_id(config),
        "m": config["m"],
        "k1": str(k1),
        "root": root,
        "tree": midpoint_tree(units),
        "leaves": leaves,
    }
    partition["partition_id"] = partition_id(partition)
    atomic_write(branch_dir / "partition.json", partition)
    return partition


def unit_config_id(config: dict[str, Any]) -> str:
    from tools.canonical_json import config_id

    return config_id(config)


def main() -> None:
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all-cases", action="store_true")
    selection.add_argument("--case", type=int, choices=CASES, action="append")
    parser.add_argument("--configs", default="certificates/config")
    parser.add_argument("--out", default="dist/search-v2/plan")
    parser.add_argument("--segments-per-branch", type=int, default=1)
    parser.add_argument("--target-seconds", type=float)
    parser.add_argument(
        "--max-segments-per-branch",
        type=int,
        help="cap timing-derived subdivision; production currently recommends 2",
    )
    replacement = parser.add_mutually_exclusive_group()
    replacement.add_argument("--replace", action="store_true")
    replacement.add_argument(
        "--replace-selected",
        action="store_true",
        help="archive and replace only the selected case directories",
    )
    args = parser.parse_args()
    if args.segments_per_branch < 1:
        raise ValueError("--segments-per-branch must be positive")
    if args.target_seconds is not None and args.target_seconds <= 0:
        raise ValueError("--target-seconds must be positive")
    if (
        args.max_segments_per_branch is not None
        and args.max_segments_per_branch < 1
    ):
        raise ValueError("--max-segments-per-branch must be positive")

    out = ROOT / args.out
    cases = CASES if args.all_cases else sorted(set(args.case))
    plan_lock = None
    archive = None
    destination = out
    temporary = None
    if args.replace_selected:
        if not out.is_dir():
            raise ValueError(f"cannot replace selected cases in missing plan: {out}")
        plan_lock = (out / ".plan.lock").open("a+", encoding="ascii")
        try:
            fcntl.flock(plan_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            plan_lock.close()
            raise RuntimeError(f"another runner owns the plan: {out}") from error
        temporary = tempfile.TemporaryDirectory(
            prefix=f".{out.name}.replacement-",
            dir=out.parent,
        )
        destination = Path(temporary.name)
    elif out.exists():
        if not args.replace:
            raise ValueError(
                f"output already exists (use --replace or --replace-selected): {out}"
            )
        shutil.rmtree(out)

    total_branches = 0
    total_units = 0
    try:
        for m in cases:
            config = load(ROOT / args.configs / f"case_m{m}.json")
            k1_min = parse_nat(config["k1_range"]["min"], "k1 min", positive=True)
            k1_max = parse_nat(config["k1_range"]["max"], "k1 max", positive=True)
            for k1 in range(k1_min, k1_max + 1):
                requested = args.segments_per_branch
                if args.target_seconds is not None:
                    seconds = historical_seconds(m, k1)
                    if seconds is not None:
                        requested = max(
                            requested,
                            math.ceil(seconds / args.target_seconds),
                        )
                root = root_progression(config, k1)
                segments = planned_segments(
                    requested,
                    int(root["count"]),
                    args.max_segments_per_branch,
                )
                branch = plan_branch(
                    config,
                    k1,
                    segments,
                    destination / f"m{m}" / f"k1_{k1:02d}",
                )
                total_branches += 1
                total_units += len(branch["leaves"])
        if args.replace_selected:
            stamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
            archive = out.parent / f"{out.name}.retired-{stamp}"
            archive.mkdir(parents=True)
            for m in cases:
                current = out / f"m{m}"
                replacement_case = destination / f"m{m}"
                if not current.is_dir() or not replacement_case.is_dir():
                    raise ValueError(f"cannot replace incomplete m={m} plan")
                os.replace(current, archive / current.name)
                os.replace(replacement_case, current)
    finally:
        if temporary is not None:
            temporary.cleanup()
        if plan_lock is not None:
            plan_lock.close()
    print(
        f"planned {total_units} units across {total_branches} branches under {out}"
    )
    if archive is not None:
        print(f"archived replaced case plans under {archive}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
