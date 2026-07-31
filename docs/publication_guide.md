# Publication readiness guide

This guide distinguishes the completed public computational certificate from
the remaining manuscript, review, licensing, and archival work.

The current checkout contains the frozen dual-engine certificate excluding
nontrivial positive Collatz `m`-cycles for `m=92,...,96`. It covers all 372
mathematical branches with 464 final work units and verifies with
`python3 -B verify_all.py --profile theorem-artifacts`.

## 1. Local Smoke Check

From the repository root:

```bash
mkdir -p build
g++ -O3 -std=c++17 src/m96/affine_ladder_prefix.cpp -lgmpxx -lgmp \
  -o build/affine_ladder_prefix

python3 scripts/certify_constants.py
python3 scripts/verify_reduction_certificates.py

rm -rf build/runs_sample
python3 scripts/run_tasks.py \
  --exe ./build/affine_ladder_prefix \
  --tasks manifests/tasks_sample_k1_1.jsonl \
  --out build/runs_sample \
  --jobs 1 \
  --timeout 60

python3 scripts/verify_certificate.py \
  --tasks manifests/tasks_sample_k1_1.jsonl \
  --runs build/runs_sample \
  --source src/m96/affine_ladder_prefix.cpp \
  --exe ./build/affine_ladder_prefix
```

The final command should print `"result": "ACCEPT"`.

## 2. Full Branch Reproduction

For the expensive `m=96` run:

```bash
rm -rf dist/runs
mkdir -p dist/run_logs
python3 scripts/run_tasks.py \
  --exe ./build/affine_ladder_prefix \
  --tasks manifests/tasks.jsonl \
  --out dist/runs \
  --jobs 8 \
  --timeout 0 \
  --resume \
  --retry-invalid \
  --heartbeat-seconds 60 \
  --progress \
  --order desc

python3 scripts/verify_certificate.py \
  --tasks manifests/tasks.jsonl \
  --runs dist/runs \
  --source src/m96/affine_ladder_prefix.cpp \
  --exe ./build/affine_ladder_prefix
```

Use a `--jobs` value that leaves the machine responsive. Keep the completed
`dist/runs/` directory unchanged after verification; any changed log must create
a new archive version.

To interrupt a detached run gracefully:

```bash
python3 scripts/run_tasks.py --stop --out dist/runs --human
```

The runner keeps accepted root artifacts, quarantines active partial attempts,
and can be resumed later with the same run command.

An accepted example output is committed at
`examples/m96_full_run_2026-07-06/`. It was run with `--jobs 8` on an AMD Ryzen
5 3600 and accepted all 75 tasks.

## 3. m=92..95 Reproduction

The same runner/verifier flow applies to `m=92..95`. Generate the manifests:

```bash
for m in 92 93 94 95; do
  python3 scripts/generate_manifest.py \
    --m "$m" \
    --out "manifests/tasks_m${m}.jsonl" \
    --mode k1 \
    --source src/m96/affine_ladder_prefix.cpp
done
```

Run and verify each case in its own directory:

```bash
for m in 92 93 94 95; do
  mkdir -p dist/run_logs
  python3 scripts/run_tasks.py \
    --exe ./build/affine_ladder_prefix \
    --tasks "manifests/tasks_m${m}.jsonl" \
    --out "dist/runs_m${m}" \
    --jobs 8 \
    --timeout 0 \
    --resume \
    --retry-invalid \
    --heartbeat-seconds 60 \
    --progress \
    --order desc \
    > "dist/run_logs/m${m}_run.log" 2>&1

  python3 scripts/verify_certificate.py \
    --tasks "manifests/tasks_m${m}.jsonl" \
    --runs "dist/runs_m${m}" \
    --source src/m96/affine_ladder_prefix.cpp \
    --exe ./build/affine_ladder_prefix \
    > "dist/run_logs/m${m}_verify.json"
done
```

Expected accepted task counts are `m=92: 73`, `m=93: 74`, `m=94: 75`, and
`m=95: 75`. The tighter `m=94` and `m=95` caps and stage targets are now
derived by the exact reduction verifier.

An accepted example output is committed at
`examples/m92_m95_full_runs_2026-07-09/`.

## 4. Work Outside the Computational Certificate

The computational release has exact reductions, all manuscript certificate
families, two independently implemented exhaustive engines, a whole-file
manifest, `SHA256SUMS`, one-command verification, and adversarial tests. A
complete paper publication still needs:

- the LaTeX source and a reproducible PDF build;
- independent mathematical review;
- paper and data licenses selected by the author;
- manuscript synchronization with the in-house `m=92,...,95` certificates.

## 5. GitHub Publication Checklist

- [x] README status matches the completed v2 certificate.
- [x] `python3 scripts/certify_constants.py` succeeds.
- [x] `python3 scripts/verify_reduction_certificates.py` succeeds.
- [x] CI smoke test is green.
- [x] The sample branch verifier accepts.
- [x] The `m=92`, `m=93`, `m=94`, and `m=95` branch verifiers accept.
- [x] The `m=96` full branch verifier accepts all 75 tasks.
- [ ] The manuscript data-availability statement matches the release contents.
- [x] The two authoritative binaries are tracked with reproducible-build
      provenance.
- [ ] A license is present.
- [x] The release tag points to the verified commit.

## 6. Archival Submission

The immutable GitHub release is the first external integrity anchor. Consider
archiving it with Zenodo and cite the release tag or DOI, not the moving `main`
branch, in a manuscript or submission form.

If the full raw archive is large, attach it to the GitHub release or Zenodo
record rather than relying on local files outside version control.
