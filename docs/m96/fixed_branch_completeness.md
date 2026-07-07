# Fixed-branch completeness of `src/m96/affine_ladder_prefix.cpp` (Lemma 2)

This document is the independent source audit required by point 4 / `docs/m96/branch_cover_theorem.md`
Lemma 2: *for fixed `k1=j`, the C++ recursion enumerates every downstream valuation pattern
allowed by the reduced model.* It establishes completeness **conditional on** the five imported
facts (A)–(E) listed in §7, which are certified separately (`scripts/certify_constants.py`) or are the
branch-cover content (point 3).

Throughout, all engine arithmetic is exact GMP integer arithmetic; there is no floating point in
any decision path. `floor_alpha` is the only place a real number (`log2 3`) enters, and it is
evaluated through a certified rational bracket that *throws* rather than guess if it cannot decide
(so it is self-checking).

## 1. The reduced model and the block map

A nontrivial Collatz `m`-cycle, rotated to its least odd element `n_1`, is written block by block in
endpoint-quotient form. Each local minimum is
$$n_i = 2^{k_i} a_i - 1, \qquad a_i \text{ odd}, \quad k_i = \nu_2(n_i+1).$$
The transition from one local minimum to the next (one leading valuation-one run of length `k_i`
followed by the first spike) is
$$n_{i+1} = \frac{3^{k_i} a_i - 1}{2^{\ell_i}}, \qquad \ell_i = \nu_2\!\big(3^{k_i} a_i - 1\big),
\qquad a_{i+1} = \frac{n_{i+1}+1}{2^{k_{i+1}}},\quad k_{i+1}=\nu_2(n_{i+1}+1).$$
This is exactly the map coded in `deterministic_finish` (`ni=(ai<<curk)-1`, `v=ai*p3(curk)-1`,
`ell=v2(v)`, `nn=v>>ell`, `kn=v2(nn+1)`). The search fixes `k1` and explores the first `depth=7`
transitions, producing `n_1,…,n_8`. If no admissible `n_1` survives, no `m`-cycle exists (given the
reduction).

## 2. The recursion invariant

`rec(i, k1, k, Ksum, Lsum, p, q, s, live)` is entered with the following invariant, which we verify is
preserved:

- the parameters `k_1=k1, k_2,…,k_i` (with `k = k_i`) and `ℓ_1,…,ℓ_{i-1}` are fixed;
- `Ksum = k_1+⋯+k_i`, `Lsum = ℓ_1+⋯+ℓ_{i-1}`;
- the map `a_1 ↦ a_i` is the affine form `a_i = (p·a_1 + q)/2^s`, an exact integer for every admissible
  `a_1` (the composition of the first `i−1` transitions);
- `live` is the exact set `{a_1 : a_1 ≡ r (mod 2^{bits}), L ≤ a_1 ≤ U}` of first-block quotients still
  consistent with every constraint imposed so far.

The initial call `rec(1, k1, k1, k1, 0, 1, 0, 0, z)` has `a_1 = (1·a_1+0)/2^0` (identity) and
`z = {a_1 : a_1 odd, ⌈(X+1)/2^{k1}⌉ ≤ a_1 ≤ ⌊(29X+1)/2^{k1}⌋}`, i.e. exactly the odd `a_1` with
`n_1 = 2^{k1}a_1−1 ∈ [X, 29X]`. The progression algebra (`normalize`, `intsect_interval`,
`intsect_linear_congruence`) is exact: `normalize` recomputes `L,U` to the true first/last members of
the residue class, and the linear-congruence lift uses `mpz_invert` on an **odd** modulus coefficient
(see §5), which always succeeds. Hence `live` always represents its set with no rounding.

## 3. Completeness of the `ℓ` enumeration

At level `i` the actual spike valuation `ℓ_i = ν_2(3^{k_i}a_i − 1)` is a function of `a_1`. The engine
does **not** read it off; it iterates `ℓ = 1,…,ℓ_max` and, for each, refines `live`. We show every
admissible `a_1` is covered under exactly its true `ℓ_i`, so the disjoint union of branches is a
partition (no omission, no double count of solutions).

Write `p2·a_1 + qbase = 2^s(3^{k_i}a_i − 1 + 2^{ℓ})` (this identity is forced by
`p2 = 3^{k_i}p`, `qbase = 3^{k_i}q + (2^{ℓ}−1)2^s`, derivation below). Let `ℓ' = ν_2(3^{k_i}a_i−1)`
be the true valuation. Then:

- **`ℓ < ℓ'`:** `3^{k_i}a_i−1 = 2^{ℓ'}·odd`, so `3^{k_i}a_i−1+2^{ℓ} = 2^{ℓ}(2^{ℓ'−ℓ}·odd+1) = 2^{ℓ}·odd`,
  giving `ν_2(p2·a_1+qbase) = s+ℓ`. The next-level constraint (§5) requires
  `ν_2(p2·a_1+qbase) ≥ s+ℓ+1`, i.e. `k_{i+1} ≥ 1`; it fails, so this `a_1` is pruned in this branch.
  (Equivalently: `n_{i+1}=(3^{k_i}a_i−1)/2^{ℓ}` is even, not a valid odd minimum.)
- **`ℓ = ℓ'`:** `3^{k_i}a_i−1+2^{ℓ} = 2^{ℓ}(odd+1)`, so `ν_2 = s+ℓ+ν_2(odd+1)` with `ν_2(odd+1) ≥ 1`.
  The constraint is satisfied and `k_{i+1}=ν_2(odd+1)≥1` is the genuine next valuation. The branch
  proceeds correctly.
- **`ℓ > ℓ'`:** `3^{k_i}a_i−1+2^{ℓ} = 2^{ℓ'}(odd+2^{ℓ−ℓ'}) = 2^{ℓ'}·odd`, so `ν_2 = s+ℓ' < s+ℓ+1`;
  the constraint `ν_2 ≥ s+ℓ+1` fails and `a_1` is pruned.

Thus each admissible `a_1` survives in exactly the branch `ℓ = ℓ'`. It remains to check
`ℓ' ≤ ℓ_max`. The engine sets `ℓ_max = ⌊log2 T⌋` with `T = (3^{k}(n_{i,max}+1)−2^{k})/(2^{k}·nlb)`
and `nlb = max(extra[i+1], X, n_{1,min})`. Since a genuine cycle has `n_{i+1} ≥ nlb` (Barina `X`,
minimality `n_1`, and the imported stage bound `extra[i+1]`), and
`n_{i+1} = (3^{k}(n_i+1)−2^{k})/2^{k+ℓ'}`, the requirement `n_{i+1} ≥ nlb` gives
`2^{ℓ'} ≤ (3^{k}(n_i+1)−2^{k})/(2^{k}·nlb) ≤ T`, hence `ℓ' ≤ ⌊log2 T⌋ = ℓ_max`. So no admissible `ℓ'`
is skipped — **conditional on `extra[i+1]` being a valid lower bound** (fact (B)).

## 4. Completeness of the `k_{i+1}` enumeration (Hensel valuation split)

Fix a surviving `ℓ`. Then `n_{i+1}+1 = (p2·a_1 + qbase)/2^{s+ℓ}` and
`k_{i+1} = ν_2(n_{i+1}+1) = ν_2(p2·a_1+qbase) − (s+ℓ)`. The engine enumerates `k_{i+1}=kn` for
`kn = 1,…,kmax` by a single 2-adic (Hensel) walk:

- it first intersects `live` with `ν_2(p2·a_1+qbase) ≥ s+ℓ+1` (`kn≥1`), one residue class mod `2^{E}`,
  `E=s+ℓ+1`;
- at each `kn` it holds a class `cont` with `ν_2 ≥ E=s+ℓ+kn`; it reads the bit of the numerator at
  position `E` for the representative and splits into `exact` (`ν_2` **exactly** `E`, i.e. `k_{i+1}=kn`)
  and `next` (`ν_2 ≥ E+1`, i.e. `k_{i+1} ≥ kn+1`). Because `p2` is odd, adding `2^{E}` to `a_1` toggles
  bit `E` of the numerator, so exactly one of the two children carries the `2^{E}` offset; this is the
  standard binary Hensel lift and is a **partition** of `cont` into `{k_{i+1}=kn}` and `{k_{i+1}≥kn+1}`.
- it recurses on `exact` (with `k_{i+1}=kn`) and continues the walk with `cont ← next`.

Hence the branches `kn=1,2,…` partition `live` by the exact value of `k_{i+1}`, with no value missed
below the cutoff. The walk stops at `kmax = min(⌊log2(n_{i+1,max}+1)⌋, kcap[i+1])`:

- `⌊log2(n_{i+1,max}+1)⌋` is a hard arithmetic bound: `ν_2(N) ≤ ⌊log2 N⌋` for any `N`, so no admissible
  `k_{i+1}` exceeds it;
- `kcap[i+1]` is the imported valuation cap. Dropping `k_{i+1} > kcap[i+1]` is sound **iff** the cap is
  a valid upper bound (fact (A)); `scripts/certify_constants.py` checks each `kcap[i] ≥ ⌈(317/200)^{i-1}·76⌉−1`,
  the largest integer below the imported bound `k_i < α^{i-1}·log2(n_1+1)` with `α<317/200`,
  `log2(n_1+1)<76`.

The `fixedk` filter (`fixedk[i+1]==0 || ==kn`) is inert in `k1`-only mode (only `k1` is fixed), so it
discards nothing here.

### Derivation of the affine numerator (used in §3–§4)
From the invariant `a_i=(p·a_1+q)/2^s` and `n_i+1=2^{k}a_i`:
`3^{k}(n_i+1) = 3^{k}2^{k}a_i`, so `n_{i+1} = (3^{k}(n_i+1)−2^{k})/2^{k+ℓ} = (3^{k}(p a_1+q)−2^{s})/2^{s+ℓ}`.
Therefore `n_{i+1}+1 = (3^{k}p·a_1 + 3^{k}q + 2^{s+ℓ} − 2^{s})/2^{s+ℓ} = (p2·a_1+qbase)/2^{s+ℓ}` with
`p2=3^{k}p`, `qbase=3^{k}q+(2^{ℓ}−1)2^{s}`, matching the code exactly.

## 5. The minimality and lower-bound refinements are exact and sound

Inside each `ℓ`-branch the engine applies, before recursing:

- `Lb = ⌈(extra·2^{s+ℓ} + 2^{s} − 3^{k}q)/(3^{k}p)⌉`, i.e. `n_{i+1} ≥ extra[i+1]` (lower-bound stage);
- `linear_ge(z, C, D)` with `C=3^{k}p − 2^{k1+s+ℓ}`, `D=3^{k}q − 2^{s}+2^{s+ℓ}`. A short computation
  gives `C·a_1+D = 2^{s+ℓ}((n_{i+1}+1) − (n_1+1))`, so this enforces **`n_{i+1} ≥ n_1`** (the global
  minimality of `n_1`). For block 1 this is precisely the first-spike/negative-branch gate:
  positive-branch first spikes have `n_2 < n_1` and are removed here.

Both are exact interval/linear refinements of the progression. They only *remove* `a_1` that violate
necessary conditions, so they never drop a genuine cycle.

## 6. The deterministic tail and the final closure test

When `live` holds at most `enum_threshold` members, `deterministic_finish` iterates them one by one
and simulates the remaining blocks with the exact map of §1 (computing the true `ℓ`, `k` by `ν_2`,
testing `n ≥ max(extra,X,n_1)`, the caps, and `hugging`). This is a faithful exact run of the model on
each `a_1`, hence complete on that set. The switch is sound because `live_count_capped` over-counts
only by saturating at `enum_threshold+1`, never undercounts.

At `i = depth` the engine, after the same `extra[depth+1]` and minimality refinements, tests whether
**any** `a_1` remains for which `n_{depth+1}` is a valid odd minimum, via one exact congruence
`intsect_linear_congruence(z, 3^{k}p, rhs, s+ℓ+1)`. If a survivor exists it increments `HITS`.
Therefore `HITS = 0` for a branch means *no* `a_1` survives the full 7-block prefix together with
`n_8 ≥ extra[8]` — there is no admissible cycle prefix in that branch.

The guard `if(Ksum ≥ FIRST_POSITIVE_SURPLUS) throw` ensures the prefix never reaches the Paper-2
frontier without being pruned; if it ever did, the process aborts (non-zero exit), which the verifier
rejects. So this guard cannot silently hide a survivor.

## 7. Statement of completeness

**Lemma 2 (fixed-branch completeness).** Fix `k1=j ∈ {1,…,75}`. Assume:

- **(A)** the caps `kcap[i]` are valid upper bounds for `k_i` (certified given the imported
  `k_{i+j} < α^j log2(n_1+1)`, `α<317/200`, `n_1<2^{76}`);
- **(B)** the stage bounds `extra[i]` are valid lower bounds for `n_i` (imported m-cycle reduction;
  the staged audit `scripts/audit_lower_bound.py` accepts for `m=96`);
- **(C)** the height window `n_1 ∈ [2^{71}, 29·2^{71}]` is valid (imported);
- **(D)** the hugging/frontier data (`floor_alpha`, `FIRST_POSITIVE_SURPLUS=72057431991`) are valid
  (Paper 2; CF bracket certified);
- **(E)** the CF bracket decides `⌊n·log2 3⌋` over the used range (certified; self-checking via throw).

Then `src/m96/affine_ladder_prefix.cpp`, compiled and run as `affine_ladder_prefix 96 "j" ...`,
enumerates **every** `a_1` (equivalently every downstream
valuation pattern `k_2,…,k_7, ℓ_1,…,ℓ_7`) admissible in the reduced model for that `j`, with the
`ℓ`- and `k`-branches forming exact partitions and the deterministic tail an exact simulation.
Consequently `HITS = 0` for branch `j` is a sound proof that the reduced model has no admissible
cycle prefix with first valuation `k1 = j`.

**Proof.** §2 establishes the invariant and the exactness of the progression algebra. §3 shows the
`ℓ`-branches partition each `live` by the true spike valuation and that no admissible `ℓ` exceeds
`ℓ_max` (using (B)). §4 shows the Hensel walk partitions each `ℓ`-branch by the exact `k_{i+1}` and
that the cutoff `kmax` drops only values excluded by the hard `log2` bound or by a valid cap (using
(A)). §5 shows the minimality and stage refinements are exact and necessary (using (B),(C)). §6 shows
the deterministic tail and the final congruence are exact, and that the frontier guard (using (D),(E))
cannot hide survivors. Composing these over the at most seven levels, the set of `a_1` reaching a
`HITS` increment equals the set admissible in the model; its emptiness is therefore exact. ∎

## 8. Scope

This lemma is the *engine-completeness* half of the proof. It does **not** establish (A)–(E)
themselves: (A),(D),(E) are certified by `scripts/certify_constants.py`; (B),(C) are the imported
Hercher/Simons–de Weger reduction and the staged lower bound (point 3 / `docs/m96/branch_cover_theorem.md`
Lemma 1), to be supplied independently. Given (A)–(E) and the branch-cover Lemma 1 (every `m=96`
cycle has `1 ≤ k1 ≤ 75`), a complete run with `HITS=0` on all 75 branches proves no nontrivial
`m=96` cycle exists.
