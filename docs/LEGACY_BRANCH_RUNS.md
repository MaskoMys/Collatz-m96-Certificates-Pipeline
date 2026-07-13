# Legacy branch-log reproduction

This document preserves the original `scripts/run_tasks.py` workflow for
reproducing the historical branch logs committed under `examples/`.

This is not the definitive v2 certificate workflow. Legacy logs do not satisfy
the dual-engine theorem profiles. New production work must use
`dist/search-v2/` and the commands in `README.md` or `ENGINEERING_V2.md`.

The commands below use `dist/legacy/` so they cannot overwrite a v2 run.

## Build the legacy engine

```bash
make build
mkdir -p dist/legacy/run_logs
```

## Reproduce m=96

Generate the manifest:

```bash
python3 scripts/generate_manifest.py \
  --out manifests/tasks.jsonl \
  --mode k1 \
  --source src/m96/affine_ladder_prefix.cpp
```

Run all 75 branches:

```bash
python3 scripts/run_tasks.py \
  --exe ./build/affine_ladder_prefix \
  --tasks manifests/tasks.jsonl \
  --out dist/legacy/runs_m96 \
  --jobs 8 \
  --timeout 0 \
  --resume \
  --retry-invalid \
  --heartbeat-seconds 60 \
  --progress \
  --order desc
```

Status is non-mutating:

```bash
python3 scripts/run_tasks.py \
  --status \
  --human \
  --order desc \
  --tasks manifests/tasks.jsonl \
  --out dist/legacy/runs_m96 \
  --exe ./build/affine_ladder_prefix
```

Stop a detached runner gracefully:

```bash
python3 scripts/run_tasks.py \
  --stop \
  --out dist/legacy/runs_m96 \
  --human
```

Verify the completed logs:

```bash
python3 scripts/verify_certificate.py \
  --tasks manifests/tasks.jsonl \
  --runs dist/legacy/runs_m96 \
  --source src/m96/affine_ladder_prefix.cpp \
  --exe ./build/affine_ladder_prefix
```

Success reports `"verified_tasks": 75` and `"result": "ACCEPT"`.

## Reproduce m=92 through m=95

Generate the manifests:

```bash
for m in 92 93 94 95; do
  python3 scripts/generate_manifest.py \
    --m "$m" \
    --out "manifests/tasks_m${m}.jsonl" \
    --mode k1 \
    --source src/m96/affine_ladder_prefix.cpp
done
```

Run and verify the cases sequentially:

```bash
for m in 92 93 94 95; do
  python3 scripts/run_tasks.py \
    --exe ./build/affine_ladder_prefix \
    --tasks "manifests/tasks_m${m}.jsonl" \
    --out "dist/legacy/runs_m${m}" \
    --jobs 8 \
    --timeout 0 \
    --resume \
    --retry-invalid \
    --heartbeat-seconds 60 \
    --progress \
    --order desc \
    > "dist/legacy/run_logs/m${m}_run.log" 2>&1

  python3 scripts/verify_certificate.py \
    --tasks "manifests/tasks_m${m}.jsonl" \
    --runs "dist/legacy/runs_m${m}" \
    --source src/m96/affine_ladder_prefix.cpp \
    --exe ./build/affine_ladder_prefix \
    > "dist/legacy/run_logs/m${m}_verify.json"
done
```

Expected accepted task counts are:

```text
m=92: 73
m=93: 74
m=94: 75
m=95: 75
```

## Committed historical reports

The original accepted runs remain under:

- `examples/m96_full_run_2026-07-06/`;
- `examples/m92_m95_full_runs_2026-07-09/`.

Their local READMEs record machine details, timings, hashes, and verification
results. Do not write new attempts into `examples/`; treat it as immutable
release evidence.
