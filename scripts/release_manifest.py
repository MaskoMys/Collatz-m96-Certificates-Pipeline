#!/usr/bin/env python3
"""Shared release-file inventory rules."""

from __future__ import annotations

from pathlib import Path

from exact_math import sha256_file


MANAGED_DIRECTORIES = (
    ".github",
    "certificates",
    "docs",
    "examples",
    "manifests",
    "paper",
    "scripts",
    "src",
    "tests",
)
EXCLUDED_FILES = {
    "SHA256SUMS",
    "certificates/release_manifest.json",
}
IGNORED_PARTS = {"__pycache__", ".pytest_cache"}
IGNORED_TOP_LEVEL_DIRECTORIES = {".git", ".venv", "build", "dist"}


def release_files(root: Path) -> list[Path]:
    files = []
    for path in root.iterdir():
        if path.is_symlink():
            raise AssertionError(f"symlinked release path: {path.name}")
        if path.is_dir() and path.name not in MANAGED_DIRECTORIES:
            if path.name not in IGNORED_TOP_LEVEL_DIRECTORIES:
                raise AssertionError(f"unmanaged top-level directory: {path.name}")
            continue
        if path.is_file() and path.name not in EXCLUDED_FILES:
            files.append(path)
    for directory in MANAGED_DIRECTORIES:
        base = root / directory
        if not base.is_dir():
            raise AssertionError(f"managed release directory missing: {directory}")
        for path in base.rglob("*"):
            relative = path.relative_to(root)
            if any(part in IGNORED_PARTS for part in relative.parts):
                continue
            name = relative.as_posix()
            if name in EXCLUDED_FILES:
                continue
            if path.is_symlink():
                raise AssertionError(f"symlinked release path: {name}")
            if path.is_file():
                files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def file_records(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        }
        for path in release_files(root)
    ]
