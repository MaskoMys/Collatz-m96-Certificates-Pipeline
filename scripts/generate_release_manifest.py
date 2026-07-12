#!/usr/bin/env python3
"""Generate the deterministic release inventory and SHA256SUMS."""

from __future__ import annotations

import argparse
from pathlib import Path

from exact_math import canonical_json_bytes, sha256_file
from release_manifest import MANAGED_DIRECTORIES, file_records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    records = file_records(root)
    manifest = {
        "schema": "collatz-certificate-release-v1",
        "managed_directories": list(MANAGED_DIRECTORIES),
        "files": records,
    }
    manifest_path = root / "certificates" / "release_manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(manifest))

    checksum_records = [
        *records,
        {
            "path": "certificates/release_manifest.json",
            "sha256": sha256_file(manifest_path),
            "size": manifest_path.stat().st_size,
        },
    ]
    checksum_records.sort(key=lambda record: record["path"])
    checksum_text = "".join(
        f"{record['sha256']}  {record['path']}\n" for record in checksum_records
    )
    (root / "SHA256SUMS").write_text(checksum_text, encoding="ascii")
    print(f"wrote {manifest_path} with {len(records)} files")
    print(f"wrote {root / 'SHA256SUMS'} with {len(checksum_records)} hashes")


if __name__ == "__main__":
    main()
