# Engineering Blueprint for the Definitive Exclusion of Collatz `m`-Cycles with `m <= 96`

> **Implementation status:** This is the preserved design and trust-model
> blueprint. The implemented operational workflow is documented in
> [`ENGINEERING_V2.md`](ENGINEERING_V2.md), and the authoritative schemas live
> in [`../schemas/`](../schemas/). Draft paths and the final theorem marker
> below describe the original target; manuscript synchronization remains
> outside the current engineering release.

**Target repository:** `Collatz-m96-math-completed`
**Audience:** software engineer implementing the remaining computational-certification layer
**Status of mathematics:** the exact analytic reductions, search windows, branch ranges, stage bounds, caps, post-window contradictions, and independent `A28` cutoff are treated as completed inputs.
**Target theorem:** using Hercher for `m <= 91`, and independently certified exhaustive finite searches for `m = 92,93,94,95,96`, conclude that no nontrivial positive Collatz `m`-cycle exists for `m <= 96`.

---

## 1. Executive decision

The remaining work is an engineering and computational-certification project. It must establish, for every finite-search region produced by the completed mathematics, that two separately implemented exact-arithmetic engines exhaust the region and find zero survivors.

A literal JSON record for every current search node is not viable. The archived runs report approximately:

| Case | Recursive nodes | Deterministic values | Historical CPU time |
|---:|---:|---:|---:|
| 92 | 21,592 | 286,914 | 0.010 CPU-hours |
| 93 | 3,545,908 | 67,592,483 | 0.014 CPU-hours |
| 94 | 286,052,392 | 5,291,642,034 | 0.667 CPU-hours |
| 95 | 12,415,597,241 | 247,582,308,247 | 30.41 CPU-hours |
| 96 | 351,848,297,864 | 8,348,144,009,683 | 990.49 CPU-hours |

The implementation shall therefore use a **chunked authenticated replay certificate**:

1. Partition every mathematical root branch into exact, disjoint arithmetic-progression work units.
2. Run the optimized C++/GMP prover on every unit.
3. Run a separately written verifier engine on every same unit.
4. Require both engines to return zero hits.
5. Verify the unit partition itself independently and exactly.
6. Commit all inputs, outputs, source, binaries, configurations, and manifests by cryptographic hashes.

This is stronger than the current summary-log scheme because the second engine recomputes every search and pruning decision. It is practical because it avoids storing trillions of individual trace events. A compact per-node proof object may be added later, but it is not required to close the theorem if the full independent replay is completed.

The paper must describe this accurately as an **independently replayed exhaustive exact computation**, unless a compact trace checker that avoids replay is subsequently implemented.

---

## 2. Non-negotiable theorem acceptance condition

The repository may emit the final marker

```text
ACCEPT_THEOREM_M_LE_96
```

only when all of the following hold:

1. The immutable release manifest is valid and contains no missing, altered, or additional files.
2. The completed mathematical verifier regenerates all analytic reductions for `m=92,...,96` from primitive exact inputs.
3. The independent `A28` verifier derives the cutoff `d <= 560277`, scans the full range, and verifies the prefix gate with no undecided boundary.
4. The root-cover verifier proves the exact branch sets:
   - `m=92`: `k1=1,...,73`;
   - `m=93`: `k1=1,...,74`;
   - `m=94`: `k1=1,...,75`;
   - `m=95`: `k1=1,...,75`;
   - `m=96`: `k1=1,...,75`.
5. For each of the 372 root branches, the final work-unit frontier is pairwise disjoint and its union equals the complete odd `a1` root progression.
6. Every work unit has:
   - one accepted prover result;
   - one accepted independent-verifier result;
   - matching input/configuration hashes;
   - zero hits in both results;
   - no timeout, crash, arithmetic exception, undecided floor, or unresolved state.
7. The aggregate has zero survivors, zero unresolved units, zero duplicate units, zero partition gaps, and zero partition overlaps.
8. All release mutation tests pass.
9. The manuscript theorem, certificate map, trust model, and data-availability statement exactly match the implemented system.

No spot check, legacy transcript, result counter, or hash-only log may satisfy items 5–7.

---

## 3. Inputs already available and how to integrate them

### 3.1 Completed mathematical certificate

Promote the current files:

```text
mathematical_completion/verify_completed_mathematics.py
mathematical_completion/completed_mathematics_certificate.json
```

to authoritative release paths:

```text
verifiers/verify_mathematical_reductions.py
certificates/analytic/m92_96_reductions.json
```

Required changes:

- The verifier must not import any search implementation.
- The generated certificate must include a canonical `case_config` object for every `m`.
- The verifier must derive and compare every case configuration field from exact mathematics.
- Retire `verify_m96_analytic_certificate.py` as an authority. It may remain only as a regression test.
- `verify_all.py` must call the unified verifier.

### 3.2 Required case configuration

The exact case values are:

| `m` | Window `n1 <= (A_num/A_den) X` | Depth | `k1` max | Caps |
|---:|---:|---:|---:|---|
| 92 | `73/10` | 2 | 73 | `73,118` |
| 93 | `15/1` | 3 | 74 | `74,118,188` |
| 94 | `24/1` | 5 | 75 | `75,119,189,299,474` |
| 95 | `24/1` | 6 | 75 | `75,119,189,299,474,751` |
| 96 | `29/1` | 7 | 75 | `75,120,191,303,481,763,1210` |

The stage-minimum arrays shall be generated from the mathematical certificate, not hand-maintained independently in C++, Rust, and Python.

Generate `certificates/config/case_m92.json` through `case_m96.json`. Every engine reads these files. Each engine independently validates their hash against the analytic certificate before searching.

---

## 4. Target repository layout

```text
src/
  prover/
    search_core.hpp
    search_core.cpp
    main.cpp
  verifier-rust/
    Cargo.toml
    Cargo.lock
    src/
      main.rs
      bigint.rs
      progression.rs
      search.rs
      config.rs
      canonical.rs
verifiers/
  verify_mathematical_reductions.py
  verify_a28_independent.py
  verify_work_unit_result.py
  verify_partition_manifest.py
  verify_global_search_certificate.py
  verify_release_manifest.py
tools/
  build_case_configs.py
  plan_work_units.py
  split_work_unit.py
  run_prover_units.py
  run_verifier_units.py
  aggregate_search_certificate.py
  canonical_json.py
schemas/
  case_config.schema.json
  root_partition.schema.json
  work_unit.schema.json
  engine_result.schema.json
  branch_certificate.schema.json
  global_search_certificate.schema.json
certificates/
  analytic/
    m92_96_reductions.json
  frontier/
    A28_certificate.csv
    A28_summary.json
  config/
    case_m92.json ... case_m96.json
  search-v2/
    global_search_certificate.json
    m92/... m96/...
release/
  build_provenance/
  computation_provenance/
  verification_status.json
  RELEASE_NOTES.md
tests/
  unit/
  property/
  differential/
  mutation/
  fixtures/
environment/
  Dockerfile
  Dockerfile.lock
  nix/ or apt-snapshot configuration
verify_all.py
MANIFEST.sha256
```

Legacy runs must be moved under `archive/legacy-runs/` and clearly marked non-authoritative.

---

## 5. Canonical data rules

All proof-critical files shall use these rules:

1. UTF-8 only.
2. LF line endings.
3. JSON object keys sorted lexicographically.
4. No insignificant whitespace in hashed canonical form.
5. Duplicate keys rejected before schema validation.
6. Every arbitrary-precision integer encoded as a canonical decimal string:
   - zero is `"0"`;
   - no leading zeros;
   - no plus sign;
   - negative values use one leading minus sign where permitted.
7. Timestamps, hostnames, elapsed times, and human notes are excluded from proof-object hashes. They belong in separate provenance files.
8. SHA-256 is mandatory for identity. BLAKE3 may be added for fast local integrity but cannot replace SHA-256 in the release manifest.
9. Every schema has a fixed version string. Unknown versions are rejected.
10. All path fields are repository-relative POSIX paths and reject `..`, absolute paths, NULs, backslashes, or symlink escape.

Identity rules:

```text
config_id = SHA256("collatz.case-config.v1\0" || canonical(config))
unit_id   = SHA256("collatz.work-unit.v1\0"  || canonical(unit-input))
result_id = SHA256("collatz.engine-result.v1\0" || canonical(result-without-result_id))
```

---

## 6. Exact root and work-unit model

### 6.1 Mathematical root

For fixed `m,k1`, let

```text
U1 = floor(A_num * X / A_den)
L  = ceil((X + 1) / 2^k1)
U  = floor((U1 + 1) / 2^k1)
```

The root consists of odd integers `a1` in `[L,U]`. Normalize it as:

```text
first = least odd integer >= L
last  = greatest odd integer <= U
count = 0, if first > last;
        (last-first)/2 + 1, otherwise.
```

A root branch with count zero is represented by one certified empty unit.

### 6.2 Work unit

A work unit is a contiguous index range of the root odd progression, not an arbitrary unverified subset:

```text
a1(j) = first + 2*j
j_start <= j <= j_end
```

Its concrete progression is:

```text
L_unit = first + 2*j_start
U_unit = first + 2*j_end
residue = 1
bits = 1
```

This design makes coverage checking simple and independent of search internals. The final units for one branch must partition `[0,count-1]` into consecutive, nonoverlapping ranges.

### 6.3 Why root-only partitioning is preferred

- It is mathematically transparent.
- It does not require trusting intermediate affine states produced by the prover.
- Every work unit can be started independently by both engines.
- It supports adaptive bisection of slow tasks.
- It makes the global cover proof a simple exact integer interval proof.
- Splitting the root interval may change search performance but cannot change mathematical coverage or correctness.

Internal-state checkpointing may be added later, but it is not needed for the first definitive release.

---

## 7. Work-unit planning and adaptive splitting

### 7.1 Initial plan

Create one unit per root branch. For `m=92`–`94`, this may already be sufficient. For `m=95` and `m=96`, use the historical branch timing as a planning hint only.

Recommended target: **15–30 minutes per final work unit on one reference core**. This limits stragglers and allows independent replay across a cluster.

For branch historical time `T`, begin with

```text
segments = max(1, ceil(T / target_seconds))
```

and divide the root index range into equal-count segments.

Historical timing is not proof input. The resulting partition is proof input and is checked exactly.

### 7.2 Adaptive bisection

The runner shall support a non-proof operational timeout, for example two hours. If a unit exceeds the limit:

1. terminate it;
2. discard/quarantine all partial output;
3. split its index interval at the exact midpoint;
4. create two child units;
5. repeat until both complete.

Only completed leaf units appear in the final branch certificate. The partition tree records the bisections. Timeout history is retained in operational logs but excluded from the mathematical result.

Never resume from a prover-generated internal state in the first release. Restart from exact root subintervals so the independent verifier can reproduce each task without trusting checkpoints.

### 7.3 Partition manifest

For each branch, store:

- the root count;
- a binary partition tree;
- the final ordered leaf units;
- the SHA-256 of every unit input.

The independent partition verifier must prove:

- root values are correct from the case configuration;
- every split uses `mid = floor((start+end)/2)` or records an explicit valid split;
- children are adjacent and exactly cover the parent;
- leaves are ordered;
- no duplicate `unit_id` exists;
- the leaf union is exactly `[0,count-1]`.

---

## 8. Optimized prover implementation

### 8.1 Refactoring requirement

Refactor `src/m96/affine_ladder_prefix.cpp` into a case-general, unit-addressable engine. Preserve exact arithmetic and search semantics, but remove hard-coded case construction from the search core.

Required CLI:

```bash
collatz_prover search-unit \
  --config certificates/config/case_m96.json \
  --unit certificates/search-v2/m96/.../unit.json \
  --output results/prover/<unit_id>.json \
  --enum-threshold 256
```

Required behavior:

- read and validate canonical JSON;
- verify the case/config hash;
- derive `a1` values only from the unit index interval;
- search the full unit;
- use only GMP integers and exact rational/floor decisions;
- abort on every undecided floor or internal invariant violation;
- write output atomically using temporary file plus rename;
- never write `PASS` if interrupted;
- return nonzero on any exception.

### 8.2 Search invariants to assert at runtime

At every recursive state:

1. `L <= U` after normalization.
2. `r` is canonical modulo `2^bits`.
3. Both endpoints satisfy the progression congruence.
4. `p` is odd.
5. `(p*a1+q)` is divisible by `2^s` for every represented `a1`; check at the residue class level.
6. The represented `a_i` is odd.
7. `Ksum` and `Lsum` cannot overflow native types; preferably store them as checked 64-bit integers and assert upper bounds from configuration.
8. `Ksum < FIRST_POSITIVE_SURPLUS` whenever the `A28` floor gate is used.
9. Every Hensel exact/continuation pair is disjoint and covers the parent continuation class.
10. Every deterministic leaf iterates exactly the represented progression.

### 8.3 Result file

The prover result shall contain:

- unit/config IDs;
- source and binary hashes;
- command-line semantic parameters;
- outcome: `NO_SURVIVOR`, `SURVIVOR`, or `ERROR`;
- exact hit count;
- recursive node count;
- deterministic value/node counts;
- prefix-prune count;
- final-congruence count;
- terminal-reason counts;
- maximum integer bit length observed;
- a canonical summary checksum.

Elapsed time and machine details go in a separate provenance record.

### 8.4 No reliance on prover counters

Counters are diagnostic. The theorem depends only on a separately replayed zero-hit result and complete unit coverage. A changed counter must be detected when comparing two runs, but a matching counter is not itself proof.

---

## 9. Independent verifier engine

### 9.1 Language and independence

Implement the authoritative independent engine in **Rust**, preferably using `rug::Integer` for performance. It may use GMP as an arithmetic library, but it must share no search source, generated code, progression code, or control-flow implementation with C++.

Retain the existing Python implementation for small differential fixtures, not for the full theorem run.

The Rust project must have:

- committed `Cargo.lock`;
- denied unsafe code unless explicitly justified;
- checked conversions between machine integers and big integers;
- deterministic iteration order;
- no floating-point arithmetic;
- no FFI calls into the C++ prover.

### 9.2 Independent algorithm requirements

Implement independently:

- floor and ceiling division, including negative operands;
- `v2`;
- progression normalization;
- interval intersection;
- linear inequality intersection;
- linear congruence intersection modulo powers of two;
- exact `ell` range derivation;
- Hensel valuation splitting;
- deterministic exact simulation;
- prefix-surplus floor gate;
- final congruence test;
- all runtime invariants.

Read the same case configuration, but verify its hash against the independently checked mathematical certificate. Do not copy constants into source code except schema/version constants.

### 9.3 Required CLI

```bash
collatz_verify_unit \
  --math-certificate certificates/analytic/m92_96_reductions.json \
  --config certificates/config/case_m96.json \
  --unit path/to/unit.json \
  --output results/verifier/<unit_id>.json
```

The verifier output uses the same result schema but records a distinct `engine="independent-rust-verifier"` and its own source/binary hashes.

### 9.4 Cross-engine comparison

The aggregator must require:

- same unit ID;
- same config ID;
- both outcomes `NO_SURVIVOR`;
- both hit counts zero;
- no errors;
- semantic parameters equal;
- counters equal where the two algorithms define identical counters.

If optimizations make counters algorithm-dependent, record separate counters and compare only invariant quantities, such as represented input count and hit count. Do not force the verifier to mimic the prover solely to match counters.

### 9.5 Differential test mode

Both engines shall support a `--debug-terminal-dump` mode only for small fixtures. It emits terminal decisions for each `a1`, allowing byte-for-byte comparison in CI. This mode must be disabled for production scale.

---

## 10. Optional authenticated macro-trace

A literal per-node trace is infeasible at current scale. If the manuscript wishes to retain “proof-carrying trace” terminology, implement the following optional layer:

1. Each work unit emits a canonical stream of **macro events**, not individual recursive nodes.
2. A macro event represents one exact root subinterval result and includes:
   - unit ID;
   - terminal outcome;
   - counts by sound pruning category;
   - a digest of deterministic subinterval summaries.
3. The independent verifier recomputes the macro stream during full replay and requires the same digest.

This supplies authenticated execution evidence but does not remove the need for full replay. The paper must not claim low-cost certificate checking unless a genuinely compact symbolic trace is later produced and independently checked without replaying the exhaustive search.

Do not attempt to serialize all historical nodes or deterministic values.

---

## 11. Independent `A28` integration

Replace the current generator-sharing checker with the completed independent derivation.

The authoritative verifier must:

1. independently enclose `log 2` and `log 3` with rational intervals;
2. reconstruct the continued fraction through `P28/Q28`;
3. prove `epsilon = Q28*alpha-P28 > 0` and `Q28*epsilon < 1`;
4. derive, rather than assume,

```text
d < Q28*epsilon + Q28^2/(3*X*log 2) < 560278;
```

5. scan every `d=1,...,560277`;
6. decide both strict inequalities exactly;
7. compare the complete accepted set with the shipped CSV;
8. verify count, extrema, gap, band counts, and zero boundary cases.

The A28 verifier must not import the CSV generator or any generator helper implementing the same scan.

---

## 12. Orchestration and computation workflow

### 12.1 Commands

The engineer shall provide these stable commands:

```bash
# Build and validate mathematical inputs
make build-all
python3 tools/build_case_configs.py
python3 verifiers/verify_mathematical_reductions.py
python3 verifiers/verify_a28_independent.py

# Plan exact work-unit frontiers
python3 tools/plan_work_units.py --all-cases --target-seconds 1800
python3 verifiers/verify_partition_manifest.py --all

# Run optimized prover
python3 tools/run_prover_units.py --jobs 64 --resume

# Run independent verifier
python3 tools/run_verifier_units.py --jobs 64 --resume

# Aggregate
python3 tools/aggregate_search_certificate.py
python3 verifiers/verify_global_search_certificate.py

# Final release verification
python3 verify_all.py --profile theorem-artifacts
python3 verify_all.py --profile full-replay --jobs 64
```

### 12.2 Runner requirements

Reuse useful features from `scripts/run_tasks.py`, but generalize them to work units:

- exclusive output-directory lock;
- atomic writes;
- resumable operation;
- status files outside proof payload;
- stale-partial quarantine;
- validation of existing output before skipping;
- per-task stdout/stderr capture;
- process-group termination;
- no shell interpolation;
- CPU and memory limit support;
- deterministic task ordering option;
- machine-readable progress summary;
- failure isolation;
- final nonzero exit if any unit is missing or invalid.

### 12.3 Production computation order

1. Complete `m=92` and `m=93`; expected to be trivial.
2. Complete `m=94`; use as the first full-scale cross-engine validation.
3. Complete `m=95`; validate adaptive partitioning and cluster orchestration.
4. Pilot selected hard `m=96` branches, including historically slow `k1=12`.
5. Freeze the final `m=96` partition.
6. Run all C++ prover units.
7. Run all Rust verifier units, preferably on a different machine or cloud account.
8. Aggregate and freeze the search certificate.
9. Rerun a statistically and structurally diverse sample on a third environment.

### 12.4 Resource planning

The historical optimized computation totals about 1,022 CPU-hours. Trace/replay refactoring and smaller root intervals may change this. Budget conservatively:

- C++ prover: 1,200–1,600 CPU-hours;
- Rust independent replay: 1,500–3,000 CPU-hours until benchmarked;
- reruns/mutations/overhead: 300–600 CPU-hours.

Initial capacity plan: **4,000 CPU-hours** and enough wall-clock concurrency to handle the slowest units. On 128 sustained cores this is roughly 31 idealized hours, but allow several days for stragglers, retries, I/O, and verification.

Storage should be modest because units/results are compact. Reserve 100 GB for logs, temporary artifacts, binaries, and release assembly. Do not permit unbounded per-node tracing.

---

## 13. Build and environment reproducibility

### 13.1 Pinning

The current Dockerfile is not sufficiently pinned. The final release must use one of:

- Nix flake with locked inputs; or
- Docker base image by immutable digest plus Debian snapshot repositories; or
- a published OCI image with digest and SBOM.

Pin:

- OS/base-image digest;
- GCC version;
- GMP version;
- Rust toolchain version;
- crate versions through `Cargo.lock`;
- Python major/minor version;
- zstd version if used;
- build flags.

### 13.2 Required provenance

For each authoritative engine store:

- source tree hash;
- source-file hashes;
- compiler identity;
- full command line;
- linked library versions;
- binary SHA-256;
- container/Nix closure identity;
- architecture;
- reproducible-build result.

The production result file references the exact binary hash. The release verifier checks that every result references an allowlisted authoritative binary.

### 13.3 Independent build diversity

Prefer:

- C++ prover built with GCC;
- Rust verifier built with the pinned Rust toolchain;
- production runs on different hosts.

A Clang build of the prover can be used as a secondary regression, but does not replace the independently coded verifier.

---

## 14. Schemas and validation

Provide JSON Schema Draft 2020-12 files, but do not rely on schema validation alone. Semantic verifiers must check arithmetic relations.

Required schemas:

1. `case_config.schema.json`
2. `root_partition.schema.json`
3. `work_unit.schema.json`
4. `engine_result.schema.json`
5. `branch_certificate.schema.json`
6. `global_search_certificate.schema.json`

Each parser must reject duplicate keys before invoking schema validation.

The blueprint package includes skeleton schemas. The engineer may add fields but must preserve the stated invariants and version them if semantics change.

---

## 15. Testing specification

### 15.1 Arithmetic unit tests

Test both engines independently for:

- floor/ceiling division with all sign combinations;
- canonical modulo powers of two;
- `v2` on random and boundary integers;
- progression normalization;
- empty/singleton/large progressions;
- interval intersections;
- congruence intersections;
- modular inverses;
- floor-alpha decisions;
- overflow checks.

### 15.2 Property tests

For randomly generated small states, compare symbolic operations against brute-force sets:

- normalized progression equals enumerated set;
- interval cut equals brute-force filter;
- linear-congruence intersection equals brute-force filter;
- Hensel exact and continuation children are disjoint and their union equals the parent continuation class;
- `ell` branches cover every exact valuation;
- deterministic simulation equals direct Collatz evaluation;
- root partition leaves exactly cover the root.

Use fixed seeds in release tests and additional random seeds in development.

### 15.3 Differential tests

- Run C++ and Rust on thousands of small synthetic units and require identical survivor sets.
- Run both on all `m=92` and `m=93` units in CI/nightly.
- Compare terminal dumps on tiny fixtures.
- Compare full result counters on cases where semantics are identical.
- Verify that different root partitionings produce the same aggregate zero-hit result.

### 15.4 Known-survivor fixtures

Create synthetic configurations where:

- one terminal survivor is intentionally present;
- a final congruence is satisfiable;
- a prefix gate is disabled;
- a cap is deliberately too small.

Both engines and the aggregator must refuse theorem acceptance. A test suite containing only zero-hit cases is insufficient.

### 15.5 Mutation tests

At minimum, reject:

- missing case;
- missing root branch;
- missing work unit;
- duplicate unit;
- overlapping units;
- one-index partition gap;
- altered `j_start`/`j_end`;
- wrong `k1`;
- wrong window/cap/stage minimum;
- false zero-hit result;
- changed config ID;
- changed binary/source hash;
- duplicate JSON key;
- noncanonical integer;
- extra unmanifested file;
- symlink/path traversal;
- truncated result;
- timeout presented as success;
- prover success with verifier missing;
- prover/verifier disagreement;
- altered analytic certificate;
- altered A28 cutoff or witness;
- undecided logarithmic boundary;
- unexpected schema version.

### 15.6 Fault injection

Development-only flags shall introduce controlled errors:

- skip one `ell`;
- reverse one Hensel child;
- omit one `a1` in deterministic iteration;
- weaken one minimum bound;
- change one floor-alpha result;
- report a false hit count.

The independent engine or global verifier must detect every injected fault.

---

## 16. CI and release profiles

### 16.1 Pull-request CI

Run:

- formatting/linting;
- all arithmetic and property tests;
- mathematical-reduction verifier;
- independent A28 verifier if runtime permits;
- schema and manifest tests;
- small C++/Rust differential fixtures;
- full `m=92` and `m=93` replay if practical.

### 16.2 Nightly CI

Run:

- full `m=94` replay;
- selected hard `m=95`/`m=96` work units;
- mutation and fault-injection suite;
- reproducible build comparison.

### 16.3 Release-only computation

Run the complete C++ and Rust work-unit sets on controlled compute. Store signed/checksummed run summaries. The release process must fail if any unit is unresolved.

### 16.4 Verification profiles

`verify_all.py` shall expose explicit profiles:

```text
--profile fast
```

Checks mathematics, A28, schemas, manifests, partition coverage, stored engine results, and tests. It does **not** rerun the expensive searches.

```text
--profile theorem-artifacts
```

Checks the complete frozen certificate inventory, both-engine result coverage, all hashes, and zero unresolved/hits. It may emit `ACCEPT_THEOREM_M_LE_96_ARTIFACT_SET`.

```text
--profile full-replay
```

Actually reruns the independent verifier on all units. Only this profile may emit `ACCEPT_THEOREM_M_LE_96` during a fresh verification.

The output must state exactly which profile was executed.

---

## 17. Global certificate aggregation

### 17.1 Branch certificate

For one `(m,k1)`, aggregate:

- case/config ID;
- root first/last/count;
- partition manifest hash;
- ordered unit IDs;
- prover result IDs;
- verifier result IDs;
- total input count;
- total hits from both engines;
- unresolved count;
- result.

Accept only if both total hit counts are zero and unresolved count is zero.

### 17.2 Case certificate

For one `m`, require exactly the expected `k1` range and aggregate all branch certificates. Verify no branch outside the range is treated as authoritative.

### 17.3 Global certificate

Require case certificates for exactly `92,93,94,95,96`, the analytic certificate, and A28 certificate. Its result is `NO_M_CYCLE_92_TO_96` only when all case results pass.

The final theorem combines this with the cited Hercher theorem for `m<=91`; do not encode Hercher’s external theorem as a computational result.

---

## 18. Manuscript and documentation synchronization

After all production computations pass:

1. Replace the conditional finite-search theorem with an unconditional theorem for `m=92,...,96`.
2. State that `m<=91` follows from Hercher.
3. State exactly that the finite searches were independently replayed by two implementations.
4. Avoid saying “compact proof trace” unless such a compact trace exists.
5. Include:
   - total work-unit counts;
   - engine/source/binary hashes;
   - CPU and wall-clock totals;
   - maximum memory;
   - hardware summary;
   - verification commands;
   - release DOI/tag;
   - theorem-to-certificate table.
6. Make Data Availability paths exact and case-sensitive.
7. Archive obsolete status documents rather than leaving contradictory notes in active documentation.
8. Include a trust-base paragraph: external published theorems, Python exact-math checker, C++ prover, Rust verifier, SHA-256 implementation, and arbitrary-precision libraries.

---

## 19. Implementation milestones and definitions of done

### Milestone 1 — Mathematical integration

**Deliverables:** unified analytic verifier, case configs, independent A28 verifier.
**Done when:** mutation of any load-bearing input causes rejection and generated configs match C++ case data exactly.

### Milestone 2 — C++ unit engine

**Deliverables:** refactored CLI, canonical input/result, unit tests.
**Done when:** it reproduces historical aggregate results for representative branches and supports arbitrary root subintervals.

### Milestone 3 — Rust independent engine

**Deliverables:** separate implementation and schemas.
**Done when:** all small differential/property tests pass and it independently reproduces full `m=92` and `m=93` results.

### Milestone 4 — Partition and runner system

**Deliverables:** planner, bisection, resumable runners, partition verifier.
**Done when:** deliberate gaps/overlaps are rejected and a timed-out unit can be replaced by two exact children.

### Milestone 5 — Medium cases

**Deliverables:** complete `m=94` and `m=95` dual-engine certificates.
**Done when:** every branch/unit passes and final case certificates contain zero hits/unresolved units.

### Milestone 6 — `m=96` production

**Deliverables:** frozen partition, all prover and verifier results.
**Done when:** all 75 root branches are exactly covered by accepted work units in both engines.

### Milestone 7 — Release hardening

**Deliverables:** pinned builds, complete tests, CI, root manifest, paper update.
**Done when:** a clean checkout passes `verify_all.py --profile theorem-artifacts`, and an independent compute environment passes `--profile full-replay`.

---

## 20. Risk register and mitigations

### Risk: Rust verifier is substantially slower

Mitigation: benchmark `rug`, optimize power-of-three caching, use release LTO, partition more finely, and scale horizontally. Do not copy C++ code to gain speed.

### Risk: Root interval splitting changes performance unpredictably

Mitigation: adaptive bisection and pilot runs. Correctness is unaffected because coverage is checked exactly.

### Risk: Result archive becomes too large

Mitigation: store only canonical unit inputs and compact result summaries; compress operational logs with zstd; exclude per-node traces.

### Risk: A hidden common-mode logic error remains

Mitigation: separate languages and code structures, property tests against brute force, known-survivor fixtures, fault injection, different production hosts, and review by a third party.

### Risk: Search configuration drifts from the mathematics

Mitigation: generate all configs from the exact analytic certificate and hash them; both engines reject unverified configs.

### Risk: A task result is mistaken for a certificate

Mitigation: global acceptance requires complete partition coverage plus two independent outcomes. Legacy transcript acceptance is explicitly excluded.

### Risk: Publication claims exceed artifact capability

Mitigation: derive the paper’s certificate table automatically from `global_search_certificate.json` and include a release preflight that searches for prohibited stale claims.

---

## 21. Final implementation checklist

- [ ] Integrate `verify_completed_mathematics.py` as authoritative analytic verifier.
- [ ] Generate exact case configs for `m=92,...,96`.
- [ ] Integrate the independent A28 cutoff and complete scan.
- [ ] Refactor C++ into a root-subinterval work-unit engine.
- [ ] Implement canonical parsers and atomic result output.
- [ ] Implement Rust independent replay engine.
- [ ] Implement root partition planner and exact verifier.
- [ ] Implement adaptive bisection and resumable runners.
- [ ] Add all schemas and semantic validators.
- [ ] Add arithmetic, property, differential, survivor, mutation, and fault-injection tests.
- [ ] Freeze pinned build environments and binary provenance.
- [ ] Complete dual-engine searches for `m=92` and `m=93`.
- [ ] Complete dual-engine searches for `m=94`.
- [ ] Complete dual-engine searches for `m=95`.
- [ ] Complete dual-engine searches for all 75 `m=96` branches.
- [ ] Aggregate branch, case, and global certificates.
- [ ] Ensure zero hits and zero unresolved units.
- [ ] Run independent full replay in a clean environment.
- [ ] Update manuscript, certificate map, trust model, and data availability.
- [ ] Create immutable release manifest and DOI/tag.
- [ ] Emit `ACCEPT_THEOREM_M_LE_96` only after the full-replay profile succeeds.

---

## 22. Handoff summary for the engineer

The engineer should not attempt to convert the old logs into proof objects. The correct path is to reuse the completed mathematics, refactor the exact search to accept small root subintervals, implement a genuinely separate verifier, partition all 372 branches into manageable exact work units, run both engines over every unit, and aggregate the zero-hit results under a strict manifest.

The highest-priority implementation order is:

1. unified generated configurations;
2. root-subinterval C++ engine;
3. independent Rust engine;
4. partition/runner infrastructure;
5. full dual-engine computation;
6. release aggregation and manuscript synchronization.

The theorem is complete only when the mathematical root cover and every final work unit have been independently checked, with no missing region and no survivor.
