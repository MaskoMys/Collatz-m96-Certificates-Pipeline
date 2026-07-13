# m=92..95 Companion Runs

The C++ engine supports the four companion cases through `make_case(92)`,
`make_case(93)`, `make_case(94)`, and `make_case(95)`. These runs are intended
to make a final `m <= 96` statement depend on this repository's own certified
pipeline for `m=92..96`, with external announcements treated as corroboration
rather than load-bearing inputs.

## Branch Ranges

`scripts/generate_manifest.py` encodes the natural branch range for each
supported case:

| case | manifest | branch cover | expected tasks |
|---:|---|---|---:|
| 92 | `manifests/tasks_m92.jsonl` | `k1=1..73` | 73 |
| 93 | `manifests/tasks_m93.jsonl` | `k1=1..74` | 74 |
| 94 | `manifests/tasks_m94.jsonl` | `k1=1..75` | 75 |
| 95 | `manifests/tasks_m95.jsonl` | `k1=1..75` | 75 |

The verifier accepts a case only when every root-level log/meta pair exists,
matches the manifest and source hash, has the expected command metadata, exits
successfully, and reports `RESULT: PASS` with `HITS=0`.

## Accepted Example

The repository includes a completed companion-run example at
`examples/m92_m95_full_runs_2026-07-09/`.

| case | result | verified tasks | combined log hash |
|---:|---|---:|---|
| 92 | `ACCEPT` | 73 | `ffb745aa8226dcb48a3389bf2581157f0c4def031db606c06614d3e3c1754a51` |
| 93 | `ACCEPT` | 74 | `99b4ba724a45fa0c7b865156e62beb472a46480c4eaaef9a6ee16efb4b546f72` |
| 94 | `ACCEPT` | 75 | `24719b6162ac277a6814862839105c64e6398571fafbd6bacc7f1d183cdd0970` |
| 95 | `ACCEPT` | 75 | `9c0b50f74d3a0fdcd57b3cc7abefb4efd7ed5bf1eb6f1a20697e5045ddb60fe3` |

## Run Commands

Build and regenerate manifests:

```bash
make build

for m in 92 93 94 95; do
  python3 scripts/generate_manifest.py \
    --m "$m" \
    --out "manifests/tasks_m${m}.jsonl" \
    --mode k1 \
    --source src/m96/affine_ladder_prefix.cpp
done
```

Run one case, detached and resumable:

```bash
m=95
mkdir -p dist/run_logs
setsid -f python3 scripts/run_tasks.py \
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
```

Check status:

```bash
m=95
python3 scripts/run_tasks.py \
  --status \
  --human \
  --order desc \
  --tasks "manifests/tasks_m${m}.jsonl" \
  --out "dist/runs_m${m}" \
  --exe ./build/affine_ladder_prefix
```

Stop cleanly:

```bash
m=95
python3 scripts/run_tasks.py --stop --out "dist/runs_m${m}" --human
```

Verify:

```bash
m=95
python3 scripts/verify_certificate.py \
  --tasks "manifests/tasks_m${m}.jsonl" \
  --runs "dist/runs_m${m}" \
  --source src/m96/affine_ladder_prefix.cpp \
  --exe ./build/affine_ladder_prefix
```

## Current Trust Boundary

`scripts/verify_reduction_certificates.py` now checks the exact analytic
reduction for every case. In particular, it derives the tighter `m=94` and
`m=95` caps from successive exact integer growth bounds, verifies every suffix
stage target, and checks the complement denominator contradiction. The accepted
proof objects live in `certificates/reductions/`.
