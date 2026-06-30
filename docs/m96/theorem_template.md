# Theorem template for the final `m=96` certificate

## Theorem

Assume the following imported results:

1. The Simons--de Weger/Hercher reduction from nontrivial Collatz `m`-cycles to the affine-ladder branch model used here.
2. The Barina convergence threshold below `2^71`, or the exact threshold required by the reduction.
3. The lower-bound stage inequalities audited in `scripts/audit_lower_bound.py` or in a replacement formal proof.
4. The branch-cover lemmas in `docs/m96/branch_cover_theorem.md`.

Let `C96` be a certificate directory containing:

- `manifests/tasks.jsonl`, generated from `cover_m96_k1_1_75`;
- one `.log` and one `.meta.json` file for every task;
- the exact source file `src/m96/affine_ladder_prefix.cpp` with matching SHA-256 hash.

If `scripts/verify_certificate.py` accepts `C96`, then no nontrivial Collatz `m=96`-cycle exists.

## Proof

Suppose a nontrivial Collatz `m=96`-cycle exists. By the imported reduction and branch-cover theorem, it belongs to exactly one branch `k1=j`, `1 <= j <= 75`, and is represented in the corresponding task of `manifests/tasks.jsonl`.

The verified source exhaustively searches that branch's reduced affine-ladder state space. The accepted certificate states that this task exited successfully with `HITS=0`. By fixed-branch completeness, no branch solution exists. This contradicts the assumed cycle. Therefore no nontrivial `m=96`-cycle exists.

## Important limitation

This theorem is not established until a complete run manifest has been generated and accepted. A partial set of task logs proves only exclusion of the corresponding subset of branches.
