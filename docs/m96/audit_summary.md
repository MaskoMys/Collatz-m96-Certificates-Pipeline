# m=96 cycle-exclusion pipeline — audit summary (points 1, 2, 4, 5)

Audit of `m96_certificate_pipeline` on a single-core sandbox. Source SHA-256 matches the manifest
(`2e364660…ba3b0`); compiled with `g++ -O3 -std=c++17 … -lgmpxx -lgmp`; the k1=1 sample reproduces
exactly (`HUG_PRUNES=5, HITS=0, PASS`). Below, "certified" means proved by exact arithmetic here;
"imported" means it is the Hercher/Simons–de Weger reduction content = your point 3.

Repository status note: this audit began as a partial sandbox record. As of 2026-07-06, the full
75-branch computational run has completed and is archived in
`examples/m96_full_run_2026-07-06/`.

## Point 5 — constant certification (DONE, all pass)

`scripts/certify_constants.py` now checks the exact source tables for
`make_case(92)` through `make_case(96)`. For this `m=96` audit, it checks every
constant in `make_case(96)` with exact rational/integer arithmetic. Each is a
*soundness* check: a cap must be an upper bound on `k_i`, a stage must be a lower
bound on `n_i`, the CF bracket must decide `⌊n·log2 3⌋`. Results:

- **α = 317/200 > log2 3** (and integer witness `3^200 < 2^317`). OK.
- **Height window**: `29·2^71 < 2^76` and `log2(29·2^71+1) < 76` (so `log2(n_1+1)<76` is usable). OK.
- **Caps** `kcap=[75,120,191,303,481,763,1210]`: each `kcap[i] ≥ ⌈α^{i-1}·76⌉−1`, the largest integer
  below the imported bound `k_i < α^{i-1}·log2(n_1+1)`. The true maxima are `[75,120,190,302,479,760,1205]`
  — every cap is a valid (sometimes 1–5 loose) upper bound. OK.
- **CF bracket** `AL_LO=P28/Q28`, `AL_HI=P27/Q27`: brackets `log2 3`, and `FRONTIER·(AL_HI−AL_LO) < 1`
  so the two floors cannot straddle an integer below the frontier — `floor_alpha` decides exactly over
  the used range (and throws otherwise, so it is self-checking). `FRONTIER = 72057431991 = Q21+Q22`
  (Paper 2). OK.
- **Lower-bound stages** `extra=[…,3·2^74,7·2^117,⌈93·2^189/50⌉]`: the rounded term is exact;
  the stages are strictly increasing (`2^75.6 < 2^119.8 < 2^189.9`). OK.
- **Staged audit** `scripts/audit_lower_bound.py` **accepts for m=96** (all 6 stages `True`); it fails the last
  stage for m=98 and m=105, consistent with m=96 sitting at the provable boundary.

Caveat: this certifies the constants are *correctly computed and sound given the imported inequalities*
(the `k_{i+j} < α^j log2(n_1+1)` cap law and the m-cycle lower-bound stages). Deriving those
inequalities is point 3.

## Point 4 — fixed-branch completeness (DONE, written up)

`docs/m96/fixed_branch_completeness.md` proves Lemma 2: for fixed `k1`, the recursion enumerates **every** admissible
downstream pattern. Key points verified against the source:

- The block map `n_{i+1}=(3^{k_i}a_i−1)/2^{ℓ_i}`, `a_{i+1}=(n_{i+1}+1)/2^{k_{i+1}}` is the exact
  endpoint-quotient transition; all engine arithmetic is exact GMP (no floats in any decision).
- **`ℓ`-enumeration is a partition**: for the true valuation `ℓ'`, branches with `ℓ<ℓ'` force the next
  valuation to 0 (pruned), `ℓ>ℓ'` fail the `ν_2≥s+ℓ+1` test (pruned), only `ℓ=ℓ'` proceeds — so each
  `a_1` is covered under exactly its true `ℓ`, and `ℓ'≤ℓ_max` holds because `n_{i+1}≥nlb`.
- **`k_{i+1}`-enumeration is a Hensel partition**: since the numerator coefficient `p2=3^{k}p` is odd,
  adding `2^E` toggles the target bit, so the walk splits `live` exactly into `{k_{i+1}=kn}` and
  `{k_{i+1}≥kn+1}`; the cutoff `kmax=min(⌊log2(n+1)⌋, kcap)` drops only values excluded by the hard
  log bound or a valid cap.
- **Minimality** `linear_ge` enforces `n_{i+1}≥n_1` (for block 1 this *is* the negative-branch/first
  spike gate); the stage refinement enforces `n_{i+1}≥extra[i+1]`. Both are exact and necessary.
- `deterministic_finish` is a faithful exact simulation on the ≤`enum_threshold` residual set; the
  final-level test counts a survivor iff some `a_1` yields a valid odd `n_8≥extra[8]`. The frontier
  guard aborts (non-zero exit) rather than hide a survivor.

Completeness holds **conditional on** (A) caps, (B) stages, (C) window, (D) hugging/frontier, (E) CF
bracket — i.e. exactly the constants certified above plus the imported reduction.

## Points 1, 2 — branch runs (75/75 confirmed, all HITS=0)

The committed full-run example verifies all manifest branches:

```json
{
  "combined_log_hash": "d8f99127dceeccd3a9fbcee254a0334fa9940a9cc8d231801e7d46adcd0b2f65",
  "cover": "m96_k1_1_75",
  "result": "ACCEPT",
  "verified_tasks": 75
}
```

The accepted output surface is `examples/m96_full_run_2026-07-06/runs/`.
Every branch exits with code 0, `timed_out=false`, `RESULT: PASS`, and `HITS=0`.
The verifier checks the manifest cover, source hash, command metadata, log hashes,
result markers, hit counts, and branch ranges.

## Realized computational cost

The completed example was run on an AMD Ryzen 5 3600 using `--jobs 8`,
`--timeout 0`, and descending branch order. The run took approximately
5d 12h 6m wall time and 990.49 summed branch CPU-hours.

The earlier sandbox estimate in this document was too optimistic; the real low-`k1`
branches were much more expensive. Representative completed timings:

| branch | seconds | hours |
|---:|---:|---:|
| k1 = 12 | 214381.379 | 59.550 |
| k1 = 11 | 206819.943 | 57.450 |
| k1 = 9 | 202954.307 | 56.376 |
| k1 = 10 | 197782.945 | 54.940 |
| k1 = 8 | 194269.332 | 53.964 |
| k1 = 19 | 116780.018 | 32.439 |
| k1 = 20 | 103954.022 | 28.876 |
| k1 = 1 | 0.501 | 0.000139 |

See `examples/m96_full_run_2026-07-06/branch_timings.tsv` for the full table.

## What remains for the record

1. **Point 3 (branch cover, your analytical work):** prove every m=96 cycle has `1 ≤ k1 ≤ 75` and that
   the depth-7 prefix with these stages covers it. Points 4–5 above make the engine and constants
   sound *given* this; it is the remaining gap to the unconditional theorem.

Optional engineering note: `enum_threshold` is a real lever (it trades symbolic interval-pruning
against one-by-one `det_values` — e.g. k1=2 shows det=109M at th=256 vs 6M at th=8), but I did not find
a setting that changes the asymptotics, so I did not alter the verified engine; tuning it per-branch
may shave constant factors on a cluster.

## Deliverables
- `scripts/certify_constants.py` — exact certification of all configured source tables, including all make_case(96) constants.
- `docs/m96/fixed_branch_completeness.md` — rigorous Lemma 2 proof (point 4).
- `examples/m96_full_run_2026-07-06/` — accepted 75-branch run, verifier output, and timings.
- `docs/m96/branch_results.txt` — historical early per-branch timing notes.
- this summary.
