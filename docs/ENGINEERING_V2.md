# Dual-engine replay certificate

The preserved design and trust-model blueprint is
[ENGINEERING_BLUEPRINT.md](ENGINEERING_BLUEPRINT.md). The v2
implementation uses exact odd-root index intervals and two independent search
engines:

- build/collatz_prover: optimized C++17/GMP prover;
- build/collatz_verify_unit: independently implemented Rust/rug replay
  verifier.

Legacy branch logs remain useful historical execution records. They are not v2
replay certificates and cannot satisfy a theorem profile.

## Current acceptance boundary

The fast verification profile checks inexpensive mathematics, frontier
certificates, legacy records, schemas, mutation tests and release integrity. It
deliberately emits no theorem marker.

The theorem-artifacts profile additionally requires a complete frozen v2
artifact for all 372 roots and both engines. The full-replay profile reruns the
Rust engine over every frozen unit. These profiles emit computational markers.
The blueprint's final theorem marker remains unavailable because manuscript
synchronization is explicitly outside this engineering pass.

## Build and derive inputs

~~~bash
make build-all
python3 tools/build_case_configs.py
python3 verifiers/verify_mathematical_reductions.py
python3 scripts/verify_frontier_certificate.py
~~~

Both binaries compare every case-config field with the authenticated
mathematical input before searching.

Before production, create the authoritative release binaries with two clean,
byte-compared builds in the pinned container:

~~~bash
make freeze-authoritative-build
~~~

Production runners must use `release/bin/collatz_prover` and
`release/bin/collatz_verify_unit`; the final verifier rejects binaries outside
the authenticated provenance allowlist.

The C++ prover is dynamically linked. Authoritative production commands must
therefore run inside the pinned image (repository mounted at `/workspace`) or
an exactly reproduced environment closure, not an arbitrary host userspace:

~~~bash
docker build --file environment/Dockerfile --tag collatz-v2:release .
docker run --rm -it \
  --user "$(id -u):$(id -g)" \
  --volume "$PWD:/workspace" \
  --workdir /workspace \
  collatz-v2:release \
  python3 tools/run_prover_units.py --help
~~~

Replace the final help command with each production command below. Keeping the
repository mount makes plans, results, locks, and provenance persist on the
host while all linked libraries come from the pinned image.

## Plan the production frontier

The historical timings are planning hints only. This command targets roughly
30-minute initial units and then verifies every root and split exactly:

~~~bash
python3 tools/plan_work_units.py \
  --all-cases \
  --target-seconds 1800 \
  --out dist/search-v2/plan

python3 verifiers/verify_partition_manifest.py \
  --all \
  --partitions dist/search-v2/plan
~~~

The planner refuses to overwrite an existing plan. Do not delete
`dist/search-v2/` when resuming, and do not rerun the planner after adaptive
subdivision begins. Remove that directory only when deliberately abandoning an
entire previous v2 computation and starting again from zero.

## Run both engines

Run the prover first. A timed-out prover unit can be replaced by two exact
midpoint children:

~~~bash
python3 tools/run_prover_units.py \
  --exe release/bin/collatz_prover \
  --plan dist/search-v2/plan \
  --out dist/search-v2/results/prover \
  --jobs 8 \
  --resume \
  --timeout 7200 \
  --adaptive-split \
  --heartbeat-seconds 60
~~~

After the prover frontier is stable and verifies again, replay that exact
frontier with Rust:

~~~bash
python3 verifiers/verify_partition_manifest.py \
  --all \
  --partitions dist/search-v2/plan

python3 tools/run_verifier_units.py \
  --exe release/bin/collatz_verify_unit \
  --plan dist/search-v2/plan \
  --out dist/search-v2/results/verifier \
  --jobs 8 \
  --resume \
  --timeout 0 \
  --heartbeat-seconds 60
~~~

Both runners are resumable, use an exclusive output lock, isolate logs and
partials, publish out-of-band `.status/` records, retain accepted execution
provenance, validate results before skipping them, and terminate process groups
on interruption. The memory-mb and cpu-seconds options set optional
per-process limits.

Status is non-mutating:

~~~bash
python3 tools/run_prover_units.py \
  --status \
  --plan dist/search-v2/plan \
  --out dist/search-v2/results/prover
~~~

Use run_verifier_units.py and its result directory for verifier status.
Repeatable `--case` and `--k1` options select validated case/branch pilots
without weakening the underlying partition checks.

## Aggregate and freeze

First assemble the accepted runner records, then check the mutable computation:

~~~bash
python3 tools/freeze_computation_provenance.py --replace

python3 tools/aggregate_search_certificate.py \
  --plan dist/search-v2/plan \
  --prover-results dist/search-v2/results/prover \
  --verifier-results dist/search-v2/results/verifier \
  --out dist/search-v2/certificates \
  --prover-binary release/bin/collatz_prover \
  --verifier-binary release/bin/collatz_verify_unit

python3 verifiers/verify_global_search_certificate.py \
  --plan dist/search-v2/plan \
  --prover-results dist/search-v2/results/prover \
  --verifier-results dist/search-v2/results/verifier \
  --certificates dist/search-v2/certificates \
  --prover-binary release/bin/collatz_prover \
  --verifier-binary release/bin/collatz_verify_unit
~~~

Only a complete five-case result accepts. Freeze it into the managed release
tree and regenerate release hashes:

~~~bash
python3 tools/freeze_search_certificate.py
python3 scripts/generate_release_manifest.py
python3 -B verify_all.py --profile theorem-artifacts
~~~

An independent machine performs the final replay:

~~~bash
python3 -B verify_all.py --profile full-replay --jobs 64
~~~

The production budget from the blueprint is approximately 4,000 CPU-hours.
The compact unit and result files are small; no per-node trace is generated.
