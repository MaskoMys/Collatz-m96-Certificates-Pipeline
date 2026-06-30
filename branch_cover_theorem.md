# Branch-cover theorem needed for an unconditional `m=96` result

This file states the exact mathematical lemma that must be proved independently of the C++ search.

## Lemma 1: reduced `m=96` search cover

Assume the standard Simons--de Weger/Hercher reduction for a nontrivial Collatz `m`-cycle and the lower-bound stages encoded in `make_case(96)` of `affine_ladder_prefix.cpp`:

```text
extra = [0, X, X, X, X, X, 3*2^74, 7*2^117, (93*2^189)/50 rounded up]
kcap  = [0, 75, 120, 191, 303, 481, 763, 1210]
X     = 2^71
```

Then every possible `m=96` cycle surviving the imported lower-bound inequalities is represented in exactly one manifest task `k1 = j`, with `1 <= j <= 75`.

## Lemma 2: fixed-branch completeness

For any fixed `k1=j`, `affine_ladder_prefix.cpp 96 "j" ...` enumerates every downstream valuation pattern allowed by the reduced model, including all legal values of `k2,...,k7` satisfying the internal caps and all exact affine-ladder congruence constraints.

This lemma should be verified by source audit or by a second independent implementation. The theorem is not valid if this lemma is merely assumed from the C++ program's comments.

## Lemma 3: zero-hit implication

If every branch task exits with `RESULT: PASS` and `HITS=0`, then the reduced model has no surviving `m=96` branch.

Together with Lemma 1 and the standard reduction, this proves there is no nontrivial Collatz `m=96`-cycle.
