#!/usr/bin/env python3
"""Replace one leaf work unit by two exact midpoint children."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canonical_json import atomic_write, load, partition_id
from tools.work_units import make_unit


def replace_leaf(node: dict[str, Any], identifier: str, replacement: dict[str, Any]) -> bool:
    if node["kind"] == "leaf":
        if node["unit_id"] != identifier:
            return False
        node.clear()
        node.update(replacement)
        return True
    return replace_leaf(node["left"], identifier, replacement) or replace_leaf(
        node["right"], identifier, replacement
    )


def flatten(node: dict[str, Any]) -> list[dict[str, str]]:
    if node["kind"] == "leaf":
        return [
            {
                "unit_id": node["unit_id"],
                "start": node["start"],
                "end": node["end"],
            }
        ]
    return flatten(node["left"]) + flatten(node["right"])


def split(branch_dir: Path, identifier: str, config_path: Path) -> list[Path]:
    partition_path = branch_dir / "partition.json"
    partition = load(partition_path)
    config = load(config_path)
    unit_path = branch_dir / "units" / f"{identifier}.json"
    unit = load(unit_path)
    start = int(unit["index_range"]["start"])
    end = int(unit["index_range"]["end"])
    if start >= end:
        raise ValueError("singleton work unit cannot be split")
    middle = (start + end) // 2
    left = make_unit(config, int(unit["k1"]), unit["root"], start, middle)
    right = make_unit(config, int(unit["k1"]), unit["root"], middle + 1, end)
    replacement = {
        "kind": "split",
        "start": str(start),
        "end": str(end),
        "split_after": str(middle),
        "left": {
            "kind": "leaf",
            "start": str(start),
            "end": str(middle),
            "unit_id": left["unit_id"],
        },
        "right": {
            "kind": "leaf",
            "start": str(middle + 1),
            "end": str(end),
            "unit_id": right["unit_id"],
        },
    }
    if not replace_leaf(partition["tree"], identifier, replacement):
        raise ValueError("unit is not a partition leaf")
    partition["leaves"] = flatten(partition["tree"])
    partition["partition_id"] = partition_id(partition)
    left_path = unit_path.parent / f"{left['unit_id']}.json"
    right_path = unit_path.parent / f"{right['unit_id']}.json"
    atomic_write(left_path, left)
    atomic_write(right_path, right)
    atomic_write(partition_path, partition)
    unit_path.unlink()
    return [left_path, right_path]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", required=True)
    parser.add_argument("--unit-id", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    children = split(ROOT / args.branch, args.unit_id, ROOT / args.config)
    for child in children:
        print(child.relative_to(ROOT))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
