# Collatz m=92-96 certificate pipeline

This repository contains an exact-arithmetic certificate pipeline for the
Hercher/Simons--de Weger style Collatz cycle route for the configured
`m=92,93,94,95,96` cases. It includes deterministic analytic reduction
certificates and accepted branch archives for all five cases.

It is **not yet the complete supplementary release promised by the manuscript**.
The arithmetic reductions, 372 branch records, `A28` and `A29` frontier checks,
first-spike check, structural oracle, descent covers, release inventory,
one-command verifier, and mutation tests are present. Manuscript source,
author-selected licenses, independent review and reproduction, and the final
archival release remain outstanding.

The manuscript PDF in `paper/` describes the intended complete release. Its
claims about LaTeX source and the final immutable archive remain target release
language. The current proof surface is described by `docs/THEOREM_MAP.md`.

## TL;DR Verify the Committed Artifact

From a clean checkout:

```bash
python3 -B verify_all.py
```

Success is a final JSON object with top-level `"result": "ACCEPT"`. This verifies
the managed release hashes, regenerates all five analytic reductions, checks all
372 committed branch records, and runs the adversarial tests. It does not rerun
the expensive searches.

## TL;DR m=96 Full Run

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

## TL;DR m=92..95 Runs

Build once, then generate the four manifests:

```bash
make build

for m in 92 93 94 95; do
  python3 scripts/generate_manifest.py \
    --m "$m" \
    --out "manifests/tasks_m${m}.jsonl" \
    --mode k1 \
    --source src/m96/affine_ladder_prefix.cpp
done
```

Run the cases sequentially. This keeps each case in its own output directory, so
one long case cannot obscure completed ones:

```bash
mkdir -p dist/run_logs
for m in 92 93 94 95; do
  python3 scripts/run_tasks.py \
    --exe ./build/affine_ladder_prefix \
    --tasks "manifests/tasks_m${m}.jsonl" \
    --out "dist/runs_m${m}" \
    --jobs 8 \
    --timeout 0 \
    --resume \
    --retry-invalid \
    --heartbeat-seconds 60 \
    --progress \
    --order desc \
    > "dist/run_logs/m${m}_run.log" 2>&1
done
```

To detach one case at a time:

```bash
m=95
mkdir -p dist/run_logs
setsid -f python3 scripts/run_tasks.py \
  --exe ./build/affine_ladder_prefix \
  --tasks "manifests/tasks_m${m}.jsonl" \
  --out "dist/runs_m${m}" \
  --jobs 8 \
  --timeout 0 \
  --resume \
  --retry-invalid \
  --heartbeat-seconds 60 \
  --progress \
  --order desc \
  > "dist/run_logs/m${m}_run.log" 2>&1
```

Check one case at a time:

```bash
m=95
python3 scripts/run_tasks.py \
  --status \
  --human \
  --order desc \
  --tasks "manifests/tasks_m${m}.jsonl" \
  --out "dist/runs_m${m}" \
  --exe ./build/affine_ladder_prefix
```

Stop one detached case gracefully:

```bash
m=95
python3 scripts/run_tasks.py --stop --out "dist/runs_m${m}" --human
```

Verify all four cases after their statuses are complete:

```bash
for m in 92 93 94 95; do
  python3 scripts/verify_certificate.py \
    --tasks "manifests/tasks_m${m}.jsonl" \
    --runs "dist/runs_m${m}" \
    --source src/m96/affine_ladder_prefix.cpp \
    --exe ./build/affine_ladder_prefix
done
```

Expected accepted task counts are `m=92: 73`, `m=93: 74`, `m=94: 75`, and
`m=95: 75`.

## Repository Layout

```text
src/m96/                 C++ affine-ladder search engine
certificates/            exact reductions and release inventory
scripts/                 manifest, runner, verifier, and audit scripts
manifests/               branch-cover manifests and cover specification
docs/m96/                m=96 proof notes, audits, and theorem contract
docs/                    broader notes and publication-readiness guide
examples/                verified run examples and compact reports
paper/                   manuscript draft PDF
.github/workflows/       CI smoke checks
verify_all.py             one-command committed-artifact verifier
SHA256SUMS                release payload hashes
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
  arithmetic for the configured `m=92..96` source constants.
- The `k1=1` sample branch rebuilds and verifies successfully.
- The `m=96` full `k1=1..75` manifest exists in `manifests/tasks.jsonl`;
  additional manifests for `m=92..95` live in `manifests/tasks_m*.jsonl`.
- Full branch run examples for `m=92..95` are committed at
  `examples/m92_m95_full_runs_2026-07-09/`; all four cases verify with
  `"result": "ACCEPT"` across 297 total tasks.
- A full `k1=1..75` branch run example is committed at
  `examples/m96_full_run_2026-07-06/`; `scripts/verify_certificate.py` accepts
  all 75 tasks with combined log hash
  `d8f99127dceeccd3a9fbcee254a0334fa9940a9cc8d231801e7d46adcd0b2f65`.
- Exact analytic reduction certificates for `m=92..96` are committed under
  `certificates/reductions/`; their verifier checks the common `K0` lift, all
  windows, caps and stage bounds, the local prefix gate, each final `Q` lift,
  and the Simons--de Weger contradictions.
- `verify_all.py`, `certificates/release_manifest.json`, `SHA256SUMS`, and the
  unit/mutation suite provide the one-command affine-ladder artifact check.
- The remaining publication work is manuscript source and licensing,
  independent reproduction and mathematical review, and the immutable tagged
  archive.

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
python3 scripts/verify_reduction_certificates.py
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

## m=92..95 Branch Runs

The same engine contains `make_case(92)`, `make_case(93)`, `make_case(94)`,
and `make_case(95)`. Their natural branch ranges are encoded in
`scripts/generate_manifest.py`. See `docs/m92_m95_companion_runs.md` for the
companion-run note:

```text
m=92: k1=1..73
m=93: k1=1..74
m=94: k1=1..75
m=95: k1=1..75
```

To produce clean publication-grade local runs, remove each target output
directory before starting. To resume an interrupted local run, keep the existing
directory and run the same command with `--resume --retry-invalid`.

```bash
make build

for m in 92 93 94 95; do
  python3 scripts/generate_manifest.py \
    --m "$m" \
    --out "manifests/tasks_m${m}.jsonl" \
    --mode k1 \
    --source src/m96/affine_ladder_prefix.cpp
done

for m in 92 93 94 95; do
  mkdir -p dist/run_logs
  python3 scripts/run_tasks.py \
    --exe ./build/affine_ladder_prefix \
    --tasks "manifests/tasks_m${m}.jsonl" \
    --out "dist/runs_m${m}" \
    --jobs 8 \
    --timeout 0 \
    --resume \
    --retry-invalid \
    --heartbeat-seconds 60 \
    --progress \
    --order desc \
    > "dist/run_logs/m${m}_run.log" 2>&1

  python3 scripts/verify_certificate.py \
    --tasks "manifests/tasks_m${m}.jsonl" \
    --runs "dist/runs_m${m}" \
    --source src/m96/affine_ladder_prefix.cpp \
    --exe ./build/affine_ladder_prefix \
    > "dist/run_logs/m${m}_verify.json"
done
```

Each verifier output must contain `"result": "ACCEPT"` with the expected task
count for that case.

The tighter `m=94` and `m=95` caps are now derived from exact dynamic growth
bounds and checked by `scripts/verify_reduction_certificates.py`.

## Trust Boundary

Trusted kernel:

- `scripts/verify_certificate.py` parsing and cover audit;
- `scripts/verify_reduction_certificates.py` exact analytic arithmetic;
- `scripts/verify_release_manifest.py` file inventory and hashes;
- exact SHA-256 hashes;
- exact GMP/integer/rational arithmetic in the shipped source and scripts;
- independently audited mathematical reductions in `docs/m96/`.

Untrusted payload:

- generated task logs until accepted by the verifier;
- wall-clock timing;
- partial runs;
- any output not checked by the verifier.

The raw logs are integrity-checked execution records, not compact proof traces.
Independent confirmation of the expensive computation requires rerunning the
frozen source. The mathematical lemmas listed in `docs/THEOREM_MAP.md` remain
human review obligations.

## Before Public Release

Before presenting the complete manuscript supplement as finished:

- Add the LaTeX source and make the data-availability statement match the archive.
- Obtain independent mathematical review and a second frozen-source run.
- Choose and add explicit code, paper, and data licenses.
- Regenerate the release manifest, merge to the release branch, and mint an
  immutable GitHub release and archival DOI.
