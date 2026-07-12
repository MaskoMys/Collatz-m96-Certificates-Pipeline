#!/usr/bin/env python3
import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

RESULT_RE = re.compile(r"^RESULT:\s*(PASS|FAIL)\s*$", re.M)
HITS_RE = re.compile(r"\bHITS=(\d+)\b")
CASE_RE = re.compile(r"\bCASE=(\d+)\b")
RANGE_RE = re.compile(r"\bK1_RANGE=(\d+)\.\.(\d+)\b")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HEADER_KEYS = {
    "kind",
    "cover",
    "m",
    "k1_min",
    "k1_max",
    "source",
    "source_sha256",
    "engine_args_schema",
}
TASK_KEYS = {
    "kind",
    "task_id",
    "m",
    "k1",
    "fixed_prefix",
    "verbose",
    "enum_threshold",
    "expected",
}
EXPECTED_KEYS = {"exit_code", "result", "hits"}
META_KEYS = {"cmd", "exit_code", "log_sha256", "seconds", "task_id", "timed_out"}


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def reject_json_constant(value):
    raise ValueError(f"non-finite JSON value {value}")


def strict_json_loads(data):
    return json.loads(
        data,
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_json_constant,
    )


def require_exact_keys(obj, expected, label):
    if not isinstance(obj, dict):
        raise AssertionError(f"{label} must be an object")
    actual = set(obj)
    if actual != expected:
        raise AssertionError(
            f"{label} keys mismatch missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}"
        )


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    header = None
    tasks = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            obj = strict_json_loads(line)
            kind = obj.get("kind")
            if kind == "header":
                if header is not None:
                    raise ValueError(f"{path}:{lineno}: duplicate header")
                require_exact_keys(obj, HEADER_KEYS, f"{path}:{lineno}: header")
                header = obj
            elif kind == "task":
                require_exact_keys(obj, TASK_KEYS, f"{path}:{lineno}: task")
                tasks.append(obj)
            else:
                raise ValueError(f"{path}:{lineno}: bad kind")
    if header is None:
        raise ValueError("missing header")
    if not tasks:
        raise ValueError("missing tasks")
    return header, tasks


def require_int(obj, key):
    value = obj.get(key)
    if type(value) is not int:
        raise AssertionError(f"{key} must be an integer")
    return value


def require_task_id(task):
    tid = task.get("task_id")
    if not isinstance(tid, str) or not TASK_ID_RE.fullmatch(tid):
        raise AssertionError(f"unsafe task_id {tid!r}")
    return tid


def expected_cmd_tail(task):
    return [
        str(task["m"]),
        task["fixed_prefix"],
        str(task["verbose"]),
        str(task["enum_threshold"]),
    ]


def audit_cover(header, tasks):
    kmin = require_int(header, "k1_min")
    kmax = require_int(header, "k1_max")
    m = require_int(header, "m")
    if kmin < 1 or kmax < kmin:
        raise AssertionError(f"invalid k1 range {kmin}..{kmax}")
    if not isinstance(header.get("cover"), str):
        raise AssertionError("missing cover name")
    if not isinstance(header.get("source_sha256"), str) or not SHA256_RE.fullmatch(
        header["source_sha256"]
    ):
        raise AssertionError("missing or invalid source_sha256")

    seen = []
    ids = set()
    for t in tasks:
        tid = require_task_id(t)
        if tid in ids:
            raise AssertionError(f"duplicate task_id {tid}")
        ids.add(t["task_id"])
        if require_int(t, "m") != m:
            raise AssertionError(f"{tid}: m mismatch")
        k1 = require_int(t, "k1")
        if t.get("fixed_prefix") != str(k1):
            raise AssertionError(f"{tid}: fixed_prefix mismatch")
        expected = t.get("expected")
        require_exact_keys(expected, EXPECTED_KEYS, f"{tid}: expected")
        require_int(expected, "exit_code")
        require_int(expected, "hits")
        if expected.get("result") not in {"PASS", "FAIL"}:
            raise AssertionError(f"{tid}: invalid expected result")
        seen.append(t["k1"])
    expect = list(range(kmin, kmax + 1))
    if sorted(seen) != expect:
        missing = sorted(set(expect) - set(seen))
        extra = sorted(set(seen) - set(expect))
        raise AssertionError(f"cover mismatch missing={missing} extra={extra}")


def audit_run_files(runs, tasks):
    expected = set()
    for task in tasks:
        tid = require_task_id(task)
        expected.add(f"{tid}.log")
        expected.add(f"{tid}.meta.json")

    actual = set()
    for path in runs.iterdir():
        if path.name.startswith("."):
            continue
        if path.is_symlink():
            raise AssertionError(f"symlinked run artifact {path.name}")
        if path.is_file():
            actual.add(path.name)
    extra = sorted(actual - expected)
    missing = sorted(expected - actual)
    if missing:
        raise AssertionError(f"missing run files {missing[:5]}")
    if extra:
        raise AssertionError(f"unexpected run files {extra[:5]}")


def verify_artifact_pair(task, log, meta, exe=None):
    tid = require_task_id(task)
    if log.is_symlink() or meta.is_symlink():
        raise AssertionError(f"{tid}: symlinked artifact")
    if not log.is_file():
        raise AssertionError(f"missing log {log}")
    if not meta.is_file():
        raise AssertionError(f"missing meta {meta}")

    m = strict_json_loads(meta.read_text(encoding="utf-8"))
    require_exact_keys(m, META_KEYS, f"{tid}: metadata")
    if m.get("task_id") != tid:
        raise AssertionError(f"{tid}: metadata task_id mismatch")
    if not isinstance(m.get("cmd"), list) or len(m["cmd"]) != 5:
        raise AssertionError(f"{tid}: malformed command metadata")
    if exe is not None and m["cmd"][0] != exe:
        raise AssertionError(f"{tid}: command executable {m['cmd'][0]!r} != {exe!r}")
    if m["cmd"][1:] != expected_cmd_tail(task):
        raise AssertionError(f"{tid}: command args mismatch {m['cmd'][1:]}")
    if m.get("exit_code") != task["expected"]["exit_code"]:
        raise AssertionError(f"{tid}: bad exit {m.get('exit_code')}")
    if m.get("timed_out") is not False:
        raise AssertionError(f"{tid}: timed out")
    seconds = m.get("seconds")
    if (
        type(seconds) not in {int, float}
        or not math.isfinite(seconds)
        or seconds < 0
    ):
        raise AssertionError(f"{tid}: invalid seconds")
    if not isinstance(m.get("log_sha256"), str) or not SHA256_RE.fullmatch(
        m["log_sha256"]
    ):
        raise AssertionError(f"{tid}: invalid log hash metadata")

    data = log.read_text(encoding="utf-8")
    if sha256_file(log) != m["log_sha256"]:
        raise AssertionError(f"{tid}: bad log hash")
    res = RESULT_RE.findall(data)
    if res != [task["expected"]["result"]]:
        raise AssertionError(f"{tid}: bad RESULT markers {res}")
    hits = [int(x) for x in HITS_RE.findall(data)]
    if len(hits) != 1:
        raise AssertionError(f"{tid}: expected one HITS marker, found {hits}")
    expected_hits = task["expected"]["hits"]
    if any(x != expected_hits for x in hits):
        raise AssertionError(f"{tid}: HITS markers {hits} != {expected_hits}")
    case = CASE_RE.findall(data)
    if case != [str(task["m"])]:
        raise AssertionError(f"{tid}: CASE markers {case}")
    rng = RANGE_RE.findall(data)
    if len(rng) != 1:
        raise AssertionError(f"{tid}: K1_RANGE markers {rng}")
    lo, hi = map(int, rng[0])
    if lo != task["k1"] or hi != task["k1"]:
        raise AssertionError(f"{tid}: K1_RANGE {lo}..{hi} expected {task['k1']}")
    return {"task_id": tid, "log_sha256": m["log_sha256"]}


def verify_one(task, runs, exe=None):
    tid = require_task_id(task)
    log = runs / f"{tid}.log"
    meta = runs / f"{tid}.meta.json"
    return verify_artifact_pair(task, log, meta, exe)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="manifests/tasks.jsonl")
    ap.add_argument("--runs", default="dist/runs")
    ap.add_argument("--source", default="src/m96/affine_ladder_prefix.cpp")
    ap.add_argument("--exe", help="optional executable path to require in run metadata")
    args = ap.parse_args()
    header, tasks = load(args.tasks)
    audit_cover(header, tasks)

    source = Path(args.source)
    if source.is_symlink() or not source.is_file():
        raise AssertionError(f"source file missing: {source}")
    actual = sha256_file(source)
    if actual != header["source_sha256"]:
        raise AssertionError(
            f"source hash mismatch {actual} != {header['source_sha256']}"
        )

    runs = Path(args.runs)
    if not runs.is_dir():
        raise AssertionError(f"runs directory missing: {runs}")
    audit_run_files(runs, tasks)

    cert = []
    for t in tasks:
        cert.append(verify_one(t, runs, args.exe))
    payload = "".join(
        f"{x['task_id']} {x['log_sha256']}\n"
        for x in sorted(cert, key=lambda x: x["task_id"])
    ).encode()
    combined = hashlib.sha256(payload).hexdigest()
    summary = {
        "verified_tasks": len(tasks),
        "cover": header["cover"],
        "combined_log_hash": combined,
        "result": "ACCEPT",
    }
    print(json.dumps(summary, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"REJECT: {e}", file=sys.stderr)
        sys.exit(1)
