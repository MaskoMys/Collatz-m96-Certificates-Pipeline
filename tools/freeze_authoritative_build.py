#!/usr/bin/env python3
"""Build twice in the pinned image and freeze matching authoritative binaries."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canonical_json import sha256_file


BINARIES = ("collatz_prover", "collatz_verify_unit")


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )


def extract(image: str, destination: Path) -> None:
    container = run(["docker", "create", image], capture=True).stdout.strip()
    try:
        destination.mkdir(parents=True, exist_ok=True)
        for name in BINARIES:
            run(
                [
                    "docker",
                    "cp",
                    f"{container}:/workspace/build/{name}",
                    str(destination / name),
                ]
            )
    finally:
        subprocess.run(
            ["docker", "rm", "--force", container],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-prefix", default="collatz-v2-authoritative")
    parser.add_argument("--keep-images", action="store_true")
    args = parser.parse_args()
    tag_a = f"{args.image_prefix}:a-{os.getpid()}"
    tag_b = f"{args.image_prefix}:b-{os.getpid()}"
    try:
        for tag in (tag_a, tag_b):
            run(
                [
                    "docker",
                    "build",
                    "--no-cache",
                    "--file",
                    "environment/Dockerfile",
                    "--tag",
                    tag,
                    ".",
                ]
            )
        run(["docker", "run", "--rm", tag_a, "make", "test"])
        run(["docker", "run", "--rm", tag_a, "make", "engineering-smoke"])
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            first = temporary_path / "first"
            second = temporary_path / "second"
            extract(tag_a, first)
            extract(tag_b, second)
            for name in BINARIES:
                first_hash = sha256_file(first / name)
                second_hash = sha256_file(second / name)
                if first_hash != second_hash:
                    raise ValueError(
                        f"reproducible build mismatch for {name}: "
                        f"{first_hash} != {second_hash}"
                    )
            destination = ROOT / "release/bin"
            destination.mkdir(parents=True, exist_ok=True)
            for name in BINARIES:
                target = destination / name
                temporary_target = destination / f".{name}.tmp"
                shutil.copyfile(first / name, temporary_target)
                temporary_target.chmod(0o755)
                os.replace(temporary_target, target)
        repository_mount = f"{ROOT}:/workspace"
        run(
            [
                "docker",
                "run",
                "--rm",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--volume",
                repository_mount,
                "--workdir",
                "/workspace",
                tag_a,
                "python3",
                "tools/generate_build_provenance.py",
                "--reproducible-build",
                "MATCH",
            ]
        )
        run([sys.executable, "verifiers/verify_build_provenance.py"])
    finally:
        if not args.keep_images:
            subprocess.run(
                ["docker", "image", "rm", "--force", tag_a, tag_b],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    for name in BINARIES:
        print(f"{name} {sha256_file(ROOT / 'release/bin' / name)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
