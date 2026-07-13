#!/usr/bin/env python3
"""Strict canonical JSON and domain-separated certificate identities."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


SHA256_RE = re.compile(r"[0-9a-f]{64}")
NAT_RE = re.compile(r"0|[1-9][0-9]*")
POS_RE = re.compile(r"[1-9][0-9]*")


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def canonical_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_bytes(value: Any, *, newline: bool = False) -> bytes:
    suffix = "\n" if newline else ""
    return (canonical_text(value) + suffix).encode("utf-8")


def strict_loads(raw: bytes | str, *, require_canonical: bool = False) -> Any:
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="strict")
    else:
        text = raw
    value = json.loads(
        text,
        object_pairs_hook=_reject_duplicates,
        parse_constant=_reject_constant,
    )
    if require_canonical and text.encode("utf-8") != canonical_bytes(value, newline=True):
        raise ValueError("JSON file is not in canonical form")
    return value


def load(path: Path, *, require_canonical: bool = True) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"certificate path is not a regular file: {path}")
    return strict_loads(path.read_bytes(), require_canonical=require_canonical)


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_bytes(value, newline=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def object_id(domain: str, value: Any) -> str:
    return sha256_bytes(domain.encode("ascii") + b"\0" + canonical_bytes(value))


def config_id(config: Any) -> str:
    return object_id("collatz.case-config.v1", config)


def unit_id(unit: dict[str, Any]) -> str:
    payload = dict(unit)
    payload.pop("unit_id", None)
    return object_id("collatz.work-unit.v1", payload)


def partition_id(partition: dict[str, Any]) -> str:
    payload = dict(partition)
    payload.pop("partition_id", None)
    return object_id("collatz.root-partition.v1", payload)


def result_id(result: dict[str, Any]) -> str:
    payload = dict(result)
    payload.pop("result_id", None)
    return object_id("collatz.engine-result.v1", payload)


def require_exact_keys(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    actual = set(value)
    if actual != keys:
        raise ValueError(
            f"{label} keys mismatch: missing={sorted(keys - actual)} "
            f"extra={sorted(actual - keys)}"
        )
    return value


def parse_nat(value: Any, label: str, *, positive: bool = False) -> int:
    pattern = POS_RE if positive else NAT_RE
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        kind = "positive" if positive else "nonnegative"
        raise ValueError(f"{label} must be a canonical {kind} decimal string")
    return int(value)


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def require_relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise ValueError(f"{label} is not a valid repository-relative POSIX path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ValueError(f"{label} is not a valid repository-relative POSIX path")
    return value
