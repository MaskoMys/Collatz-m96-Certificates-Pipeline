# Publication readiness guide

This guide tracks what must be true before this repository should be advertised
as a completed public certificate release.

The current checkout is a reorganized, partial pipeline. It is suitable for
reviewing the source, manifests, proof notes, and smoke-test verifier. It is not
yet the immutable supplementary archive described by the manuscript PDF.

## 1. Local Smoke Check

From the repository root:

```bash
mkdir -p build
g++ -O3 -std=c++17 src/m96/affine_ladder_prefix.cpp -lgmpxx -lgmp \
  -o build/affine_ladder_prefix

python3 scripts/certify_constants.py
python3 scripts/audit_lower_bound.py

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

## 3. Release Artifact Still Needed

A finished certificate release should add:

- `dist/runs/` or an archived equivalent containing all 75 branch logs and metadata;
- a whole-file SHA-256 manifest for the release archive;
- a one-command `verify_all.py` that checks the full release without rerunning
  the expensive search;
- adversarial verifier tests for missing branches, altered hit counts, modified
  logs, source mismatches, unexpected files, malformed metadata, and path-safety
  cases;
- exact analytic certificate files referenced by the manuscript;
- a license selected by the author;
- release notes that state exactly what is proved and what remains conditional.

## 4. GitHub Publication Checklist

- [ ] README status matches the shipped artifacts.
- [ ] `python3 scripts/certify_constants.py` succeeds.
- [ ] `python3 scripts/audit_lower_bound.py` succeeds.
- [ ] CI smoke test is green.
- [ ] The sample branch verifier accepts.
- [ ] The full branch verifier accepts all 75 tasks.
- [ ] The manuscript data-availability statement matches the release contents.
- [ ] No compiled binary is tracked.
- [ ] A license is present.
- [ ] The release tag points to the verified commit.

## 5. Archival Submission

After the full artifact exists, create an immutable GitHub release and consider
archiving it with Zenodo. Cite the release tag or DOI, not the moving `main`
branch, in a manuscript or submission form.

If the full raw archive is large, attach it to the GitHub release or Zenodo
record rather than relying on local files outside version control.
