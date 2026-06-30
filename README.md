# Collatz m=96 certificate pipeline

This repository contains a partial, exact-arithmetic certificate pipeline for the
Hercher/Simons--de Weger style `m=96` Collatz cycle route.

It is **not yet a complete public proof artifact**. The current repository can
build the search engine, generate the 75-branch task manifest, run branches, and
verify branch logs. A completed certificate release still requires all 75 raw
branch logs, final analytic certificates, and an accepted full verifier run.

The manuscript PDF in `paper/` describes the intended complete release. Its
claims about shipped raw logs, `verify_all.py`, immutable manifests, and
supplementary certificates should be read as target release language, not as a
description of this repository snapshot.

## Repository Layout

```text
src/m96/                 C++ affine-ladder search engine
scripts/                 manifest, runner, verifier, and audit scripts
manifests/               branch-cover manifests and cover specification
docs/m96/                m=96 proof notes, audits, and partial run status
docs/                    broader notes and publication-readiness guide
paper/                   manuscript draft PDF
.github/workflows/       CI smoke checks
```

Generated artifacts such as binaries, logs, and build directories are ignored by
Git.

## Current Status

- Constants and local arithmetic checks pass with exact integer/rational
  arithmetic.
- The `k1=1` sample branch rebuilds and verifies successfully.
- The full `k1=1..75` manifest exists in `manifests/tasks.jsonl`.
- The run record is incomplete: `docs/m96/audit_summary.md` reports 32/75
  branches confirmed, with `k1=2..44` not fully completed in this snapshot.
- The final public-release pieces described in the manuscript are not present:
  no `runs/` directory, no complete raw branch archive, no whole-repository
  SHA-256 manifest, no `verify_all.py`, and no adversarial verifier suite.

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
rm -rf runs_sample
python3 scripts/run_tasks.py \
  --exe ./build/affine_ladder_prefix \
  --tasks manifests/tasks_sample_k1_1.jsonl \
  --out runs_sample \
  --jobs 1 \
  --timeout 60

python3 scripts/verify_certificate.py \
  --tasks manifests/tasks_sample_k1_1.jsonl \
  --runs runs_sample \
  --source src/m96/affine_ladder_prefix.cpp \
  --exe ./build/affine_ladder_prefix
```

The verifier should print JSON with `"result": "ACCEPT"`.

## Full Branch Run

Regenerate the manifest if the source changes:

```bash
python3 scripts/generate_manifest.py \
  --out manifests/tasks.jsonl \
  --mode k1 \
  --source src/m96/affine_ladder_prefix.cpp
```

Run all 75 branches:

```bash
rm -rf runs
python3 scripts/run_tasks.py \
  --exe ./build/affine_ladder_prefix \
  --tasks manifests/tasks.jsonl \
  --out runs \
  --jobs 16 \
  --timeout 14400
```

Verify the resulting branch logs:

```bash
python3 scripts/verify_certificate.py \
  --tasks manifests/tasks.jsonl \
  --runs runs \
  --source src/m96/affine_ladder_prefix.cpp \
  --exe ./build/affine_ladder_prefix
```

This branch verifier checks the task cover, source hash, metadata, exact engine
arguments, exit status, timeouts, raw-log hashes, unique summary markers, branch
range, and all parsed `HITS=` counters.

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
