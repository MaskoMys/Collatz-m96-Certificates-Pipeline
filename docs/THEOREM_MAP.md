# Theorem-to-certificate map

This document states the proof contract for the `m=92..96` affine-ladder
artifact. Acceptance is conditional only on the cited published inputs and the
human-audited mathematical lemmas listed below; all derived numerical decisions
are checked with exact integer or rational arithmetic.

## Published inputs

| Input | Used statement | Local check |
|---|---|---|
| Barina (2025) | A nontrivial positive cycle has no member below `X=2^71`. | `X` is fixed in every reduction certificate and engine case. |
| Hercher (2023), Lemma 20 | Successive local minima satisfy `n_(i+1) < n_i^delta`. | Used to derive dynamic `k_i` caps and suffix stage bounds. |
| Hercher (2023), Corollary 24 | For `m<=98`, `K>7.76*10^19`. | The common initial denominator lift starts from the weaker safe input `K>=77600000000000000000`. |
| Simons--de Weger (2005/2010), Lemma 16 and Theorem 3(d) | `K < 1.4784*m*delta^m` in the required range. | Each case checks `1.4784*m*(317/200)^m < Q` by integer cross multiplication. |

Here `delta=log2(3)`. The exact logarithm enclosure is regenerated from the
positive atanh series with a rigorous geometric tail.

## Common reduction

Every `certificates/reductions/m*_reduction.json` contains the same independently
verified common block:

- a 256-bit outward rational enclosure for `ln(2)`, `ln(3)`, and `delta`;
- the suffix-balanced denominator lift from Hercher's lower bound to
  `K0=205632218873398596256`;
- adjacent Farey endpoints with determinant `-1` and denominator sum `K0`;
- a direct check of the Prefix-Hugging positive-surplus obstruction for every
  engine prefix `1<=u<=3143`.

The local prefix check is exactly what the engine needs and is cross-checked by
the complete `A28` frontier certificate.

## Frontier and descent certificates

| Manuscript result | Artifact | Independent check |
|---|---|---|
| Theorem 3.4 finite first-spike range | `certificates/first_spike.json` | Recomputes all `m=2..102` integer inequalities and the two `m=103` threshold checks. |
| Theorems 7.3--7.8, `A28` | `certificates/frontier/A28_certificate.csv` and `frontier_summary.json` | Reclassifies all 560,277 distance witnesses, proves the `27/50` decision margin, and checks counts, bands, extrema, gap and rho maxima. |
| Proposition 10.2 | `certificates/frontier/oracle_summary.json` | Two interval-bounded rational floor sums reproduce every count through `Q40` and the three tau values. |
| Independent `A29` scan | `src/frontier/independent_a29_scan.cpp` and `a29_scan_summary.json` | Recompiles and classifies all 37,862,796 witnesses with exact 100-bit dyadic bounds. |
| Theorem 8.3 | `certificates/descent/primitive_*` | Recomputes every affine descent cell and checks four complete prefix-free depth-24 tilings. |
| Corollary 8.4 | `certificates/descent/endpoint_m2_*` | Recomputes 173,892 cells and the complete depth-28 tiling with 716,705 residual leaves. |

## Per-case cover

| Case | Finite least-minimum window | Branches | Depth | Final threshold |
|---:|---|---:|---:|---:|
| 92 | `[X,(73/10)X]` | 73 | 2 | `Q=7941964418702608664581` |
| 93 | `[X,15X]` | 74 | 3 | `Q` |
| 94 | `[X,24X]` | 75 | 5 | `Q` |
| 95 | `[X,24X]` | 75 | 6 | `Q` |
| 96 | `[X,29X]` | 75 | 7 | `Q` |

For each case, `scripts/verify_reduction_certificates.py` recomputes the window
cover, conservative dynamic caps, suffix-derived stage minima, complement error
bound, final adjacent Farey interval, and Simons--de Weger contradiction. The
`m=92` complement uses its distinguished first block term; the other cases use
the generic suffix-block bound.

## Finite searches

The accepted branch surfaces are:

- `examples/m92_m95_full_runs_2026-07-09/m*/runs/` for `m=92..95`;
- `examples/m96_full_run_2026-07-06/runs/` for `m=96`.

`scripts/verify_certificate.py` checks source identity, exact task cover,
metadata schema, command arguments, exit status, timeout status, log hashes,
case and branch markers, and the unique zero-hit result. The fixed-branch
partition argument is documented in `docs/m96/fixed_branch_completeness.md`.

## Trust boundary

`verify_all.py` verifies artifact integrity and every arithmetic certificate
without rerunning the expensive branch searches. The raw branch logs are
execution records, not compact proof traces: independent confirmation of the
search computation requires rerunning the frozen source or producing a future
pruning-witness certificate format.

The following remain human proof-review obligations:

- the suffix-balanced rotation lemma and denominator-lift inequality;
- the imported theorem normalizations and strictness;
- the fixed-branch completeness argument for the C++ recursion.

These obligations must receive independent mathematical review before the
project is described as a peer-reviewed theorem.
