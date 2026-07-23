#!/usr/bin/env python3
"""Operational timing hints from the committed legacy branch runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.canonical_json import load


ROOT = Path(__file__).resolve().parents[1]


def historical_seconds(m: int, k1: int) -> float | None:
    if m == 96:
        path = (
            ROOT
            / "examples/m96_full_run_2026-07-06/runs"
            / f"m96_k1_{k1:02d}.meta.json"
        )
    else:
        path = (
            ROOT
            / "examples/m92_m95_full_runs_2026-07-09"
            / f"m{m}/runs"
            / f"m{m}_k1_{k1:02d}.meta.json"
        )
    if not path.is_file():
        return None
    value = load(path, require_canonical=False).get("seconds")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


def estimated_unit_seconds(m: int, unit: dict[str, Any]) -> float | None:
    seconds = historical_seconds(m, int(unit["k1"]))
    root_count = int(unit["root"]["count"])
    if seconds is None or root_count <= 0:
        return None
    start = int(unit["index_range"]["start"])
    end = int(unit["index_range"]["end"])
    return seconds * (end - start + 1) / root_count
