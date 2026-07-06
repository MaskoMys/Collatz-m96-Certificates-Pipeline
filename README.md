# Collatz m=96 certificate pipeline

This repository contains a partial, exact-arithmetic certificate pipeline for the
Hercher/Simons--de Weger style `m=96` Collatz cycle route.

It is **not yet a complete public proof artifact**. The current repository can
build the search engine, generate the 75-branch task manifest, run branches, and
verify branch logs. It now includes one completed 75-branch run example, but a
completed public certificate release still requires final analytic certificates,
whole-release manifests, and release packaging.

The manuscript PDF in `paper/` describes the intended complete release. Its
claims about shipped raw logs, `verify_all.py`, immutable manifests, and
supplementary certificates should be read as target release language, not as a
description of this repository snapshot.

## TL;DR Full Run

From the repository root, start a clean detached full run with:

```bash
rm -rf build dist
make build

python3 scripts/generate_manifest.py \
  --out manifests/tasks.jsonl \
  --mode k1 \
  --source src/m96/affine_ladder_prefix.cpp

rm -rf dist/runs
mkdir -p dist/run_logs
setsid -f python3 scripts/run_tasks.py \
  --exe ./build/affine_ladder_prefix \
  --tasks manifests/tasks.jsonl \
  --out dist/runs \
  --jobs 8 \
  --timeout 0 \
  --resume \
  --retry-invalid \
  --heartbeat-seconds 60 \
  --progress \
  --order desc \
  > dist/run_logs/full_run.log 2>&1
```

Check status at any time with:

```bash
watch -t -n 5 'python3 scripts/run_tasks.py \
  --status \
  --human \
  --order desc \
  --tasks manifests/tasks.jsonl \
  --out dist/runs \
  --exe ./build/affine_ladder_prefix'
```

Watch the detached log with:

```bash
tail -f dist/run_logs/full_run.log
```

Interrupt a detached run gracefully with:

```bash
python3 scripts/run_tasks.py --stop --out dist/runs --human
```

Completed root artifacts remain in `dist/runs/`; active partial attempts are
quarantined under `dist/runs/.quarantine/`. Re-run the same start command later
to resume.

When status reaches `75/75 complete`, run the final verifier:

```bash
python3 scripts/verify_certificate.py \
  --tasks manifests/tasks.jsonl \
  --runs dist/runs \
  --source src/m96/affine_ladder_prefix.cpp \
  --exe ./build/affine_ladder_prefix
```

Success means the verifier prints `"verified_tasks": 75` and
`"result": "ACCEPT"`.

## Repository Layout

```text
src/m96/                 C++ affine-ladder search engine
scripts/                 manifest, runner, verifier, and audit scripts
manifests/               branch-cover manifests and cover specification
docs/m96/                m=96 proof notes, audits, and partial run status
docs/                    broader notes and publication-readiness guide
examples/                verified run examples and compact reports
paper/                   manuscript draft PDF
.github/workflows/       CI smoke checks
```

Generated artifacts such as binaries, logs, and certificate run directories are
ignored by Git.

## Generated Artifacts

Use one standard layout for local/generated files:

- `dist/runs/` is the canonical full-run certificate output directory. Final accepted
  `{task_id}.log` and `{task_id}.meta.json` files live at its root; runner
  bookkeeping lives under hidden subdirectories such as `.partial/`, `.status/`,
  and `.quarantine/`.
- `dist/run_logs/` is only for terminal/nohup output from long runner processes.
- `build/` contains the compiled engine and disposable smoke-test outputs such
  as `build/runs_sample/`.

These paths are ignored by Git. Root-level `runs/`, `run_logs/`, and
`runs_sample/` are legacy scratch names and are also ignored, but new commands
should use `dist/` and `build/`. The public proof artifact is not complete until
the root of `dist/runs/` contains all 75 accepted branch log/meta pairs and the
verifier accepts them.

Committed examples live under `examples/`; these are intentionally small,
reviewable snapshots of accepted outputs rather than scratch run directories.

## Current Status

- Constants and local arithmetic checks pass with exact integer/rational
  arithmetic.
- The `k1=1` sample branch rebuilds and verifies successfully.
- The full `k1=1..75` manifest exists in `manifests/tasks.jsonl`.
- A full `k1=1..75` branch run example is committed at
  `examples/m96_full_run_2026-07-06/`; `scripts/verify_certificate.py` accepts
  all 75 tasks with combined log hash
  `d8f99127dceeccd3a9fbcee254a0334fa9940a9cc8d231801e7d46adcd0b2f65`.
- The final public-release pieces described in the manuscript are not present:
  no whole-repository SHA-256 manifest, no `verify_all.py`, no adversarial
  verifier suite, and no final release package.

## Prerequisites

- Python 3.10 or newer.
- A C++17 compiler.
- GMP development headers and libraries.

On Debian/Ubuntu:

```bash
sudo apt-get install g++ libgmp-dev
```

## Quick Smoke Test

Shortcut:

```bash
make smoke
```

Equivalent commands:

Build the engine:

```bash
mkdir -p build
g++ -O3 -std=c++17 src/m96/affine_ladder_prefix.cpp -lgmpxx -lgmp \
  -o build/affine_ladder_prefix
```

Run the exact audit scripts:

```bash
python3 scripts/certify_constants.py
python3 scripts/audit_lower_bound.py
```

Run and verify the one-branch sample:

```bash
rm -rf build/runs_sample
python3 scripts/run_tasks.py \
  --exe ./build/affine_ladder_prefix \
  --tasks manifests/tasks_sample_k1_1.jsonl \
  --out build/runs_sample \
  --jobs 1 \
  --timeout 60

python3 scripts/verify_certificate.py \
  --tasks manifests/tasks_sample_k1_1.jsonl \
  --runs build/runs_sample \
  --source src/m96/affine_ladder_prefix.cpp \
  --exe ./build/affine_ladder_prefix
```

The verifier should print JSON with `"result": "ACCEPT"`.

## Full Branch Run

Build the engine first:

```bash
make build
```

Regenerate the manifest if the source changes:

```bash
python3 scripts/generate_manifest.py \
  --out manifests/tasks.jsonl \
  --mode k1 \
  --source src/m96/affine_ladder_prefix.cpp
```

Run all 75 branches. Descending order certifies the easy high-`k1` branches
first, then continues into the harder low-`k1` region:

```bash
mkdir -p dist/run_logs
python3 scripts/run_tasks.py \
  --exe ./build/affine_ladder_prefix \
  --tasks manifests/tasks.jsonl \
  --out dist/runs \
  --jobs 8 \
  --timeout 0 \
  --resume \
  --retry-invalid \
  --heartbeat-seconds 60 \
  --progress \
  --order desc
```

Detached long run:

```bash
mkdir -p dist/run_logs
setsid -f python3 scripts/run_tasks.py \
  --exe ./build/affine_ladder_prefix \
  --tasks manifests/tasks.jsonl \
  --out dist/runs \
  --jobs 8 \
  --timeout 0 \
  --resume \
  --retry-invalid \
  --heartbeat-seconds 60 \
  --progress \
  --order desc \
  > dist/run_logs/full_run.log 2>&1
```

Human-readable status at any time:

```bash
python3 scripts/run_tasks.py \
  --status \
  --human \
  --order desc \
  --tasks manifests/tasks.jsonl \
  --out dist/runs \
  --exe ./build/affine_ladder_prefix
```

Watch the detached log:

```bash
tail -f dist/run_logs/full_run.log
```

Interrupt a detached run gracefully:

```bash
python3 scripts/run_tasks.py --stop --out dist/runs --human
```

This sends `SIGINT` to the active runner recorded in
`dist/runs/.runner.lock`. The runner terminates active child processes,
quarantines their partial files, and keeps completed root artifacts untouched.
Run the same detached command again later to resume from accepted artifacts.

Success criteria for the run:

- the status command eventually reports `75/75 complete`, `running 0`, and
  `pending 0`;
- if starting from a clean `dist/runs/`, it should also report `quarantined 0`
  and `invalid 0`;
- the root of `dist/runs/` contains 75 `.log` files and 75 `.meta.json` files;
- hidden runner state under `dist/runs/.partial/`, `.status/`, and
  `.quarantine/` is not part of the certificate surface.

Verify the resulting branch logs:

```bash
python3 scripts/verify_certificate.py \
  --tasks manifests/tasks.jsonl \
  --runs dist/runs \
  --source src/m96/affine_ladder_prefix.cpp \
  --exe ./build/affine_ladder_prefix
```

This branch verifier checks the task cover, source hash, metadata, exact engine
arguments, exit status, timeouts, raw-log hashes, unique summary markers, branch
range, and all parsed `HITS=` counters. The full branch run is accepted only
when this verifier prints JSON with `"verified_tasks": 75` and
`"result": "ACCEPT"`.

## Trust Boundary

Trusted kernel:

- `scripts/verify_certificate.py` parsing and cover audit;
- exact SHA-256 hashes;
- exact GMP/integer/rational arithmetic in the shipped source and scripts;
- independently audited mathematical reductions in `docs/m96/`.

Untrusted payload:

- generated task logs until accepted by the verifier;
- wall-clock timing;
- partial runs;
- any output not checked by the verifier.

## Before Public Release

At minimum, complete these before presenting the repository as a finished proof
artifact:

- Run `k1=1..75` to completion and archive every `.log` and `.meta.json`.
- Add a whole-repository manifest and one-command `verify_all.py`.
- Add adversarial tests for verifier failure modes.
- Reconcile the manuscript data-availability statement with the actual archive.
- Choose and add an explicit license.
- Mint an immutable GitHub release and, if desired, a Zenodo DOI.
