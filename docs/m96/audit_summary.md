# m=96 cycle-exclusion pipeline — audit summary (points 1, 2, 4, 5)

Audit of `m96_certificate_pipeline` on a single-core sandbox. Source SHA-256 matches the manifest
(`2e364660…ba3b0`); compiled with `g++ -O3 -std=c++17 … -lgmpxx -lgmp`; the k1=1 sample reproduces
exactly (`HUG_PRUNES=5, HITS=0, PASS`). Below, "certified" means proved by exact arithmetic here;
"imported" means it is the Hercher/Simons–de Weger reduction content = your point 3.

Repository status note: this is a partial audit record. It documents completed checks and
remaining work; it is not a complete 75-branch certificate archive.

## Point 5 — constant certification (DONE, all pass)

`scripts/certify_constants.py` checks every constant in `make_case(96)` with exact rational/integer
arithmetic. Each is a *soundness* check: a cap must be an upper bound on `k_i`, a stage must be a
lower bound on `n_i`, the CF bracket must decide `⌊n·log2 3⌋`. Results:

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

## Points 1, 2 — branch runs (32/75 confirmed, all HITS=0)

Single core, so branches run serially. Cost falls monotonically with k1; **every branch run to
completion returns HITS=0**:

| region | branches | result |
|---|---|---|
| k1 = 1 | 1 | HITS=0 (instant) |
| k1 = 45–75 | 31 | HITS=0 (149.5 s … <0.04 s) |
| k1 = 2 | 1 | HITS=0 so far (partial, det=429M @148 s, unfinished) |
| k1 = 3–44 | 42 | hard region — not run here (see estimate) |

So 32 of 75 branches are fully confirmed HITS=0; no branch has ever produced a hit. Representative
completed hard-ish points: k1=45 → 149.5 s (det 312M), k1=47 → 61.5 s, k1=50 → 18.5 s.

## Calibrated total-cost estimate

Cost grows ×1.8 per unit decrease in k1 for k1≥52, **decelerating to ×1.5 below k1=50**, and
**saturating** for small k1: k1=2 reaches det=429M at 148 s — larger than k1=45's *total* (312M) but
the same order of magnitude, not exponentially larger. The level-5 combination count is bounded by
`kcap` (independent of k1), so once the a_1 range covers all combinations (k1≲44) the per-branch cost
plateaus.

- **Fast region k1=45–75 (31 branches):** ≈ **250 s total** on 1 core (measured).
- **Hard region k1=2–44 (43 branches):** saturated at ≈ **150–800 s each** → **1.8–9.6 core-hours**.
- **Grand total ≈ 2–10 core-hours** on 1 core; on the author's `--jobs 16` design, **≈ 20–40 min
  wall-clock**. Memory per branch is modest (progressions + ~few-thousand-bit GMP integers).

This is well within reach on a normal multi-core machine; it is only impractical in this single-core,
short-window sandbox. The hard branches can be run one-by-one (`./affine_ladder_prefix 96 K 0 256`)
and checked with `scripts/verify_certificate.py`.

## What remains for the record

1. **Run k1 = 2–44 to completion** on multi-core hardware and confirm HITS=0 (≈ 20–40 min on 16 cores).
   32/75 are already confirmed; nothing suggests any hit.
2. **Point 3 (branch cover, your analytical work):** prove every m=96 cycle has `1 ≤ k1 ≤ 75` and that
   the depth-7 prefix with these stages covers it. Points 4–5 above make the engine and constants
   sound *given* this; it is the remaining gap to the unconditional theorem.

Optional engineering note: `enum_threshold` is a real lever (it trades symbolic interval-pruning
against one-by-one `det_values` — e.g. k1=2 shows det=109M at th=256 vs 6M at th=8), but I did not find
a setting that changes the asymptotics, so I did not alter the verified engine; tuning it per-branch
may shave constant factors on a cluster.

## Deliverables
- `scripts/certify_constants.py` — exact certification of all make_case(96) constants.
- `docs/m96/fixed_branch_completeness.md` — rigorous Lemma 2 proof (point 4).
- `docs/m96/branch_results.txt` — per-branch timings and HITS=0 confirmations.
- this summary.
