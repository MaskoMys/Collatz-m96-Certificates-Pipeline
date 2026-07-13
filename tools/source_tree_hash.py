#!/usr/bin/env python3
"""Hash a source set with paths and contents in deterministic order."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def hash_paths(names: list[str], *, base: Path = Path(".")) -> str:
    digest = hashlib.sha256(b"collatz.source-tree.v1\0")
    for name in sorted(names):
        path = base / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"not a regular source file: {name}")
        encoded = Path(name).as_posix().encode("utf-8")
        payload = path.read_bytes()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    try:
        print(hash_paths(args.paths))
    except ValueError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
