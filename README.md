# m=96 Collatz cycle certificate pipeline

This package is a certificate-producing pipeline scaffold for the Hercher/Simons--de Weger style `m`-cycle route.

It does **not** by itself prove that no `m=96` cycles exist. A proof is obtained only after:

1. the branch-cover theorem is accepted/checked;
2. every task in `tasks.jsonl` has been run with the exact `affine_ladder_prefix.cpp` source;
3. the independent verifier accepts the complete run log manifest with zero hits;
4. the lower-bound/continued-fraction audit is independently accepted.

The intended theorem shape is:

> If `verify_certificate.py` accepts a complete certificate directory for `cover_m96_k1_1_75`, then no nontrivial Collatz `m=96`-cycle exists, relative only to the imported lemmas explicitly listed in `theorem_template.md`.

## Why the cover is split by k1

The search engine's internal recursion is designed to enumerate all downstream valuation choices once the first block parameter `k1` is fixed. The manifest therefore splits the branch cover into the disjoint range

```text
k1 = 1,2,...,75.
```

This is only a valid mathematical cover if the branch-cover lemma proves that every possible `m=96` cycle in the reduced model has `1 <= k1 <= 75`. That lemma is separated in `branch_cover_theorem.md` and should be formalized or independently audited.

## Quick start

Compile:

```bash
g++ -O3 -std=c++17 affine_ladder_prefix.cpp -lgmpxx -lgmp -o affine_ladder_prefix
```

Generate the branch manifest:

```bash
python3 generate_manifest.py --out tasks.jsonl --mode k1
```

Run tasks in parallel:

```bash
python3 run_tasks.py --exe ./affine_ladder_prefix --tasks tasks.jsonl --out runs --jobs 16 --timeout 3600
```

Verify:

```bash
python3 verify_certificate.py --tasks tasks.jsonl --runs runs --source affine_ladder_prefix.cpp
```

The verifier accepts only if every task exists, every process exits 0, every output contains `RESULT: PASS`, every parsed `HITS` value is zero, and the task cover is exactly `k1=1..75` with no omissions.

## Trust boundary

Trusted kernel:
- `verify_certificate.py` parsing and cover audit;
- exact SHA-256 hashes;
- independently audited branch-cover/lower-bound lemmas.

Untrusted payload:
- generated task logs;
- wall-clock timing;
- partial runs;
- any output not checked by the verifier.

