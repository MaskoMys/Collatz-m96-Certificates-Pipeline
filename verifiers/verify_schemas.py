#!/usr/bin/env python3
"""Validate all shipped v1 schemas and canonical case configurations."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

try:
    from referencing import Registry, Resource
except ImportError:  # jsonschema 4.10 in the pinned Debian environment
    Registry = None
    Resource = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canonical_json import load


EXPECTED = {
    "authoritative_builds.schema.json",
    "branch_certificate.schema.json",
    "case_config.schema.json",
    "case_search_certificate.schema.json",
    "computation_attempt.schema.json",
    "computation_provenance.schema.json",
    "engine_result.schema.json",
    "global_search_certificate.schema.json",
    "root_partition.schema.json",
    "work_unit.schema.json",
}


def schema_validator(
    schema: dict[str, object], schemas: dict[str, dict[str, object]]
) -> Draft202012Validator:
    if Registry is not None and Resource is not None:
        registry = Registry()
        for candidate in schemas.values():
            registry = registry.with_resource(
                candidate["$id"], Resource.from_contents(candidate)
            )
        return Draft202012Validator(schema, registry=registry)
    from jsonschema import RefResolver

    store = {candidate["$id"]: candidate for candidate in schemas.values()}
    return Draft202012Validator(
        schema, resolver=RefResolver.from_schema(schema, store=store)
    )


def main() -> None:
    directory = ROOT / "schemas"
    actual = {path.name for path in directory.glob("*.json")}
    if actual != EXPECTED:
        raise ValueError(
            f"schema set mismatch missing={sorted(EXPECTED - actual)} "
            f"extra={sorted(actual - EXPECTED)}"
        )
    schemas = {name: load(directory / name) for name in sorted(EXPECTED)}
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    config_validator = schema_validator(schemas["case_config.schema.json"], schemas)
    for m in range(92, 97):
        config_validator.validate(load(ROOT / f"certificates/config/case_m{m}.json"))
    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "verified_schemas": len(schemas),
                "verified_configs": 5,
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
