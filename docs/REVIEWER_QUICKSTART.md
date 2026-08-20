# Reviewer quick start

This file gives the shortest reproducibility path for the theorem paper
**There Are No Collatz m-Cycles with m <= 96**. The authoritative computational
artifact is release `v1.0.0`, archived at DOI
[`10.5281/zenodo.21724745`](https://doi.org/10.5281/zenodo.21724745).

The software authenticates the exact finite reductions and exhaustive
computations. It does **not** replace human review of the imported mathematical
results or of the proof that the finite search covers every admissible case.
See `docs/THEOREM_MAP.md` for that trust boundary.

## Level 1: authenticate the frozen theorem artifacts

From the repository root, run

```bash
python3 -B verify_all.py --profile theorem-artifacts
```

The run should accept all five cases `m=92,...,96`, verify 372 root branches
and 464 final work units, and emit

```text
ACCEPT_COMPUTATIONAL_ARTIFACT_SET_M_LE_96
```

This is the recommended first check for an editor or referee. It verifies the
frozen certificate, schemas, hashes, exact analytic reductions, partition
coverage, dual-engine results, and provenance without rerunning the expensive
production search.

## Level 2: small independent dual-engine smoke test

To build the development engines and run the repository's complete dual-engine
smoke replay for the small configured cases `m=92` and `m=93`, run

```bash
make build-all
make engineering-smoke
```

This is a diagnostic/reproducibility check, not a replacement for the frozen
five-case theorem certificate.

## Level 3: complete independent Rust replay

A referee who intentionally wants to recompute every frozen work unit with the
independent Rust/rug engine should use the pinned Docker environment described
in the root `README.md` and then run

```bash
python3 -B verify_all.py --profile full-replay --jobs <N>
```

Successful completion emits

```text
ACCEPT_COMPUTATIONAL_REPLAY_M_LE_96
```

The full replay is expensive: the repository's measured production budget is
approximately 4,000 CPU-hours. It is therefore not expected as an ordinary
first-pass review step.

## Mathematical review checklist

A mathematical referee should separately check the following load-bearing
points in the manuscript and theorem map:

1. the normalization of Barina's verification floor and the Hercher/Hercher-
   corrigendum inputs;
2. the suffix-balanced denominator reduction and Farey-neighbor lift;
3. the cap-complement stage minima while the cycle remains rotated at its
   global least local minimum;
4. the finite prefix condition used by the search;
5. completeness of the valuation split, one-bit Hensel split, interval cuts,
   deterministic tail, and work-unit partition;
6. the final second denominator lift and comparison with the Simons--de Weger
   upper bound.

## Artifact identifiers

- Zenodo DOI: `10.5281/zenodo.21724745`
- GitHub tag: `v1.0.0`
- Global result: `NO_M_CYCLE_92_TO_96`
- Root branches: `372`
- Final work units: `464`
- Hits: `0`
- Unresolved units: `0`

The paper reports the release archive SHA-256 and the digest of the top-level
`SHA256SUMS` file. The top-level verifier should be used to authenticate the
complete current release rather than manually trusting individual files.
