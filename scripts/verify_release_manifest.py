#!/usr/bin/env python3
"""Verify the release inventory, hashes, and absence of unmanaged payload files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from exact_math import canonical_json_bytes, sha256_file
from release_manifest import MANAGED_DIRECTORIES, file_records


SHA_LINE = re.compile(r"^([0-9a-f]{64})  ([A-Za-z0-9_./-]+)$")


def duplicate_rejector(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    manifest_path = root / "certificates" / "release_manifest.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw, object_pairs_hook=duplicate_rejector)
    if raw != canonical_json_bytes(manifest):
        raise AssertionError("release manifest is not canonical JSON")
    if set(manifest) != {"schema", "managed_directories", "files"}:
        raise AssertionError("release manifest keys mismatch")
    if manifest["schema"] != "collatz-certificate-release-v1":
        raise AssertionError("release manifest schema mismatch")
    if manifest["managed_directories"] != list(MANAGED_DIRECTORIES):
        raise AssertionError("managed directory policy mismatch")
    expected_records = file_records(root)
    if manifest["files"] != expected_records:
        raise AssertionError("release file inventory or hash mismatch")

    expected_hashes = {
        record["path"]: record["sha256"] for record in expected_records
    }
    expected_hashes["certificates/release_manifest.json"] = sha256_file(manifest_path)
    checksum_path = root / "SHA256SUMS"
    lines = checksum_path.read_text(encoding="ascii").splitlines()
    parsed = {}
    for line in lines:
        match = SHA_LINE.fullmatch(line)
        if not match:
            raise AssertionError(f"malformed SHA256SUMS line: {line!r}")
        digest, name = match.groups()
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or name.startswith("./"):
            raise AssertionError(f"unsafe SHA256SUMS path: {name!r}")
        if name in parsed:
            raise AssertionError(f"duplicate SHA256SUMS path: {name}")
        parsed[name] = digest
    if list(parsed) != sorted(parsed):
        raise AssertionError("SHA256SUMS is not sorted")
    if parsed != expected_hashes:
        raise AssertionError("SHA256SUMS inventory or digest mismatch")

    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "verified_files": len(expected_records),
                "manifest_sha256": sha256_file(manifest_path),
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
