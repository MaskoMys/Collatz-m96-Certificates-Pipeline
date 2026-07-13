# Collatz m=92-96 certificate pipeline

This repository implements an exact-arithmetic certificate pipeline for the
Hercher/Simons--de Weger Collatz cycle route for `m=92,93,94,95,96`.

The mathematical reductions and the definitive engineering layer are present.
The remaining computational step is to execute and independently replay the
complete v2 search frontier, then freeze those results into the release. Until
that production run exists, the repository intentionally emits no theorem
marker.

The older 372 branch logs are preserved as historical execution records. They
are useful corroboration and planning data, but they are not substitutes for
the v2 dual-engine replay certificate.

## TL;DR: Audit the Current Repository

From a clean checkout with the prerequisites installed:

```bash
python3 -B verify_all.py --profile fast
```

Success is a final JSON object with:

```json
{
  "profile": "fast",
  "result": "ACCEPT",
  "theorem_marker": null
}
```

This verifies the release inventory, rebuilds the analytic reductions, checks
all 372 legacy branch records, verifies the frontier and descent certificates,
and runs the adversarial test suite. It does not rerun the expensive searches.

The null marker is expected. The stronger profiles reject until the complete
v2 production artifacts have been frozen.

## TL;DR: Produce the Definitive Certificate

Authoritative production uses the pinned container and the authenticated
binaries under `release/bin/`. Run the following from the repository root on
an AMD64 Linux machine with Docker.

Build the environment and define a helper that executes commands inside it:

```bash
docker build \
  --file environment/Dockerfile \
  --tag collatz-v2:release \
  .

v2() {
  docker run --rm \
    --user "$(id -u):$(id -g)" \
    --volume "$PWD:/workspace" \
    --workdir /workspace \
    collatz-v2:release "$@"
}

JOBS=8
```

Set `JOBS` to the number of concurrent CPU-heavy processes the machine can
sustain. Eight is a conservative starting point; do not blindly use the full
logical-CPU count on a shared or thermally constrained machine.

Confirm the committed inputs and authoritative binaries before computing:

```bash
v2 python3 -B verify_all.py --profile fast
```

### 1. Plan and verify all 372 roots

The planner refuses to overwrite an existing output directory. Do not delete
`dist/search-v2/` when resuming, and do not rerun the planner after adaptive
subdivision has begun.

```bash
v2 python3 tools/plan_work_units.py \
  --all-cases \
  --target-seconds 1800 \
  --out dist/search-v2/plan

v2 python3 verifiers/verify_partition_manifest.py \
  --all \
  --partitions dist/search-v2/plan
```

The initial production plan contains 372 root branches. Historical timings
currently divide them into approximately 3,098 work units; adaptive timeout
splits may increase that number while preserving the exact root cover.

### 2. Run the C++/GMP prover

```bash
v2 python3 tools/run_prover_units.py \
  --exe release/bin/collatz_prover \
  --plan dist/search-v2/plan \
  --out dist/search-v2/results/prover \
  --jobs "$JOBS" \
  --resume \
  --timeout 7200 \
  --adaptive-split \
  --heartbeat-seconds 60
```

Check progress from another terminal after defining the same `v2` helper:

```bash
v2 python3 tools/run_prover_units.py \
  --status \
  --plan dist/search-v2/plan \
  --out dist/search-v2/results/prover
```

Press `Ctrl+C` for a graceful interruption. Accepted units remain reusable;
rerun the identical prover command to resume. Never remove `dist/search-v2/`
when resuming.

### 3. Replay the final frontier independently in Rust

The prover may have subdivided timed-out units, so verify the final frontier
again before starting Rust:

```bash
v2 python3 verifiers/verify_partition_manifest.py \
  --all \
  --partitions dist/search-v2/plan

v2 python3 tools/run_verifier_units.py \
  --exe release/bin/collatz_verify_unit \
  --plan dist/search-v2/plan \
  --out dist/search-v2/results/verifier \
  --jobs "$JOBS" \
  --resume \
  --timeout 0 \
  --heartbeat-seconds 60
```

Rust replay status is also non-mutating:

```bash
v2 python3 tools/run_verifier_units.py \
  --status \
  --plan dist/search-v2/plan \
  --out dist/search-v2/results/verifier
```

The replay command is resumable in the same way as the prover.

### 4. Aggregate and verify the mutable computation

These commands require every final work unit to have one accepted result from
each engine, matching counters, and zero survivors:

```bash
v2 python3 tools/freeze_computation_provenance.py

v2 python3 tools/aggregate_search_certificate.py \
  --plan dist/search-v2/plan \
  --prover-results dist/search-v2/results/prover \
  --verifier-results dist/search-v2/results/verifier \
  --out dist/search-v2/certificates \
  --prover-binary release/bin/collatz_prover \
  --verifier-binary release/bin/collatz_verify_unit

v2 python3 verifiers/verify_global_search_certificate.py \
  --plan dist/search-v2/plan \
  --prover-results dist/search-v2/results/prover \
  --verifier-results dist/search-v2/results/verifier \
  --certificates dist/search-v2/certificates \
  --prover-binary release/bin/collatz_prover \
  --verifier-binary release/bin/collatz_verify_unit
```

### 5. Freeze and accept the computational artifact

Run this only after the mutable global verifier accepts. The freeze command
refuses to overwrite an existing release certificate unless explicitly told to
do so.

```bash
v2 python3 tools/freeze_search_certificate.py
v2 python3 scripts/generate_release_manifest.py
v2 python3 -B verify_all.py --profile theorem-artifacts
```

Success must include:

```text
ACCEPT_COMPUTATIONAL_ARTIFACT_SET_M_LE_96
```

An independent machine can then perform the complete Rust replay:

```bash
v2 python3 -B verify_all.py --profile full-replay --jobs "$JOBS"
```

Its success marker is:

```text
ACCEPT_COMPUTATIONAL_REPLAY_M_LE_96
```

These are computational acceptance markers. The final paper theorem marker
remains unavailable because manuscript synchronization is deliberately outside
this engineering pass.

The estimated production budget is approximately 4,000 CPU-hours. Wall-clock
time is roughly total CPU time divided by effective sustained parallelism, not
simply the advertised logical-CPU count.

## How the Certificate Works

1. Authenticated analytic inputs define the exact finite searches for
   `m=92,...,96`.
2. The planner partitions all 372 mathematical root branches into disjoint
   odd-root index intervals.
3. The optimized C++17/GMP prover exhausts every work unit and emits a canonical
   authenticated result.
4. A separately implemented Rust/rug engine replays every same unit.
5. Independent verifiers check partition coverage, schemas, hashes, build and
   execution provenance, matching counters, and zero survivors.
6. Aggregation accepts only a complete five-case result with no gaps, overlaps,
   duplicate units, unresolved work, or reported hits.

This is a chunked authenticated replay certificate, not a multi-trillion-record
per-node trace. The complete design and trust model are in
`docs/ENGINEERING_BLUEPRINT.md`; operational details are in
`docs/ENGINEERING_V2.md`.

## Existing Examples

Do not delete `examples/`. It contains committed, hashed historical runs:

- `examples/m96_full_run_2026-07-06/`: all 75 legacy m=96 branches;
- `examples/m92_m95_full_runs_2026-07-09/`: all 297 legacy m=92..95 branches;
- machine information, per-branch timings, summaries, and accepted verifier
  outputs.

These examples remain useful for corroboration, regression checks, and runtime
planning. They are not v2 work-unit results and therefore cannot satisfy a
theorem profile. The v2 runners write only below `dist/search-v2/` and never
modify `examples/`.

Instructions for reproducing the historical branch-log pipeline are isolated
in `docs/LEGACY_BRANCH_RUNS.md`. They are not part of the definitive production
workflow.

## Repository Layout

```text
certificates/analytic/       authenticated m=92..96 analytic inputs
certificates/config/         generated and authenticated case configurations
certificates/search-v2/      frozen production certificate, once completed
environment/                 pinned production build environment
examples/                    committed historical runs and timing reports
release/bin/                 authoritative C++ and Rust binaries
release/build_provenance/    reproducible-build allowlist
schemas/                     strict certificate and provenance schemas
src/prover/                  optimized C++17/GMP work-unit prover
src/verifier-rust/           independent Rust/rug replay engine
tools/                       planners, runners, aggregation, and freezing tools
verifiers/                   independent artifact verifiers
scripts/                     analytic, legacy, and release utilities
docs/                        design, operations, proof notes, and release notes
paper/                       manuscript draft PDF
verify_all.py                top-level acceptance profiles
SHA256SUMS                   release payload hashes
```

Generated files have two standard homes:

- `build/` contains disposable local binaries and smoke-test output;
- `dist/search-v2/` contains resumable mutable production plans and results.

Both are ignored by Git. The committed `examples/`, `certificates/`, and
`release/` directories are release data, not scratch space.

## Prerequisites

Authoritative production requires:

- an AMD64 Linux host;
- Docker;
- sufficient storage for compact unit/result records;
- enough uninterrupted CPU capacity for the production budget.

The pinned image supplies C++17, GMP, OpenSSL, nlohmann-json, Python, and Rust
1.92.0. Direct host development additionally requires Python 3.10 or newer, a
C++17 compiler, GMP/OpenSSL development headers, `python3-jsonschema`, and the
pinned Rust toolchain.

On Debian/Ubuntu, the native development packages are:

```bash
sudo apt-get install \
  g++ \
  libgmp-dev \
  libssl-dev \
  m4 \
  nlohmann-json3-dev \
  python3-jsonschema
```

## Development Checks

Build both v2 engines and the legacy engine:

```bash
make build-all
```

Run all unit, property, mutation, signal, survivor, schema, and release tests:

```bash
make test
```

Run a complete dual-engine smoke replay for m=92 and m=93:

```bash
make engineering-smoke
```

Reproduce the authoritative binaries with two clean pinned builds and require
byte-identical outputs:

```bash
make freeze-authoritative-build
```

That last command is a reproducible-build audit. It is not necessary merely to
use the already authenticated binaries committed under `release/bin/`.

## Current Acceptance Boundary

Available now:

- exact analytic reductions and case configurations for m=92..96;
- independent A28, A29, frontier, first-spike, structural, and descent checks;
- 372 accepted historical branch records;
- canonical work-unit and result formats with strict schemas;
- exact partition planning and adaptive subdivision;
- optimized C++ prover and separately implemented Rust replay engine;
- resumable runners, locks, status records, provenance, and quarantine;
- reproducible authoritative binaries, mutation tests, fault injection, and CI.

Still required for computational acceptance:

- execute every final work unit with both engines;
- freeze complete computation provenance and the v2 certificate;
- obtain an independent full replay.

Still required before presenting a final archival paper release:

- synchronize the manuscript and data-availability statement;
- obtain independent mathematical review;
- select explicit code, paper, and data licenses;
- publish an immutable tagged release and archival DOI.

## Trust Boundary

The release verifier trusts exact arithmetic and the reviewed semantics of the
analytic, partition, result, provenance, and aggregation verifiers. It also
authenticates the canonical inputs, source trees, pinned build environment, and
authoritative binaries.

The expensive search result is not accepted on the C++ prover's assertion
alone. Every exact work unit must be recomputed by the separately implemented
Rust engine, and both result sets must pass independent coverage and aggregate
checks. Timing data, partial attempts, quarantined files, legacy logs, and any
unverified output are not v2 proof evidence.

The mathematical lemmas and the correspondence between the finite search and
the stated Collatz theorem remain human review obligations. See
`docs/THEOREM_MAP.md` for the current proof surface.
