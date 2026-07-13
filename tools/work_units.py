#!/usr/bin/env python3
"""Shared data-model helpers for root work units, without search logic."""

from __future__ import annotations

from typing import Any

from tools.canonical_json import config_id, parse_nat, unit_id


def ceil_div(a: int, b: int) -> int:
    if b <= 0:
        raise ValueError("denominator must be positive")
    return -(-a // b)


def root_progression(config: dict[str, Any], k1: int) -> dict[str, str]:
    x = parse_nat(config["X"], "config.X", positive=True)
    numerator = parse_nat(config["window"]["numerator"], "window numerator", positive=True)
    denominator = parse_nat(
        config["window"]["denominator"], "window denominator", positive=True
    )
    upper_n1 = numerator * x // denominator
    lower = ceil_div(x + 1, 1 << k1)
    upper = (upper_n1 + 1) // (1 << k1)
    first = lower if lower & 1 else lower + 1
    last = upper if upper & 1 else upper - 1
    count = 0 if first > last else (last - first) // 2 + 1
    return {
        "first": str(first),
        "last": str(last if count else first - 2),
        "count": str(count),
        "residue": "1",
        "bits": "1",
    }


def make_unit(
    config: dict[str, Any], k1: int, root: dict[str, str], start: int, end: int
) -> dict[str, Any]:
    unit = {
        "schema": "collatz.work-unit.v1",
        "config_id": config_id(config),
        "m": config["m"],
        "k1": str(k1),
        "root": root,
        "index_range": {"start": str(start), "end": str(end)},
    }
    unit["unit_id"] = unit_id(unit)
    return unit


def midpoint_tree(units: list[dict[str, Any]]) -> dict[str, Any]:
    if not units:
        raise ValueError("partition tree needs at least one leaf")
    if len(units) == 1:
        unit = units[0]
        return {
            "kind": "leaf",
            "start": unit["index_range"]["start"],
            "end": unit["index_range"]["end"],
            "unit_id": unit["unit_id"],
        }
    middle = len(units) // 2
    left = midpoint_tree(units[:middle])
    right = midpoint_tree(units[middle:])
    return {
        "kind": "split",
        "start": left["start"],
        "end": right["end"],
        "split_after": left["end"],
        "left": left,
        "right": right,
    }
