# m=92..95 Full Branch Run Examples (2026-07-09)

This directory contains completed branch-certificate runs for the companion
cases `m=92`, `m=93`, `m=94`, and `m=95`.

## Result

All four cases verify with `result: ACCEPT`.

| case | cover | verified tasks | combined log hash |
|---:|---|---:|---|
| 92 | `m92_k1_1_73` | 73 | `ffb745aa8226dcb48a3389bf2581157f0c4def031db606c06614d3e3c1754a51` |
| 93 | `m93_k1_1_74` | 74 | `99b4ba724a45fa0c7b865156e62beb472a46480c4eaaef9a6ee16efb4b546f72` |
| 94 | `m94_k1_1_75` | 75 | `24719b6162ac277a6814862839105c64e6398571fafbd6bacc7f1d183cdd0970` |
| 95 | `m95_k1_1_75` | 75 | `9c0b50f74d3a0fdcd57b3cc7abefb4efd7ed5bf1eb6f1a20697e5045ddb60fe3` |

Total verified tasks: `297`.

The source SHA-256 recorded in each manifest is
`2e364660d26cd7d06ea07f22d555e8b758bc75955b7d71e0a98fb98f846ba3b0`.

## Reverify

From the repository root:

```bash
for m in 92 93 94 95; do
  python3 scripts/verify_certificate.py \
    --tasks "examples/m92_m95_full_runs_2026-07-09/manifests/tasks_m${m}.jsonl" \
    --runs "examples/m92_m95_full_runs_2026-07-09/m${m}/runs" \
    --source src/m96/affine_ladder_prefix.cpp \
    --exe ./build/affine_ladder_prefix
done
```

## Machine And Run

- CPU: AMD Ryzen 5 3600 6-Core Processor
- Logical CPUs: 12
- Physical cores: 6 core(s), 2 thread(s) per core
- OS/kernel: `Linux sinruda 7.1.2-zen3-1-zen #1 ZEN SMP PREEMPT_DYNAMIC Fri, 03 Jul 2026 23:25:06 +0000 x86_64 GNU/Linux`
- Runner jobs: `8`
- Runner timeout: `0` (disabled)
- Runner order: `desc`
- Summed successful branch CPU time: 31.10 hours

Approximate observed wall-clock times from the local runner logs:

| case | observed wall time | summed branch CPU time | slowest accepted branch |
|---:|---:|---:|---|
| 92 | 6s | 0.010h | `m92_k1_37` at 0.507s |
| 93 | 8s | 0.014h | `m93_k1_14` at 1.015s |
| 94 | 5m12s | 0.667h | `m94_k1_16` at 99.199s |
| 95 | 4h29m38s | 30.410h | `m95_k1_12` at 5816.427s |

The `m=95` local runner status records `quarantined: 16` because the run was
gracefully interrupted twice during monitoring and then resumed. These hidden
quarantine files are not included here and are not part of the certificate
surface. The accepted root log/meta pairs verify cleanly.

## Files

- `manifests/`: exact manifests used for `m=92..95`
- `mXX/runs/`: accepted root certificate surface for that case
- `mXX/verify_certificate.accept.json`: final verifier output
- `mXX/status_final.json`: final runner status summary
- `mXX/branch_timings.tsv`: per-branch seconds, hours, result, hits, and log SHA-256
- `mXX/run_summary.json`: compact per-case timing and verifier summary
- `mXX/runner_final_tail.log`: final excerpt of the local runner log
- `machine/`: captured `lscpu` and `uname -a` output

## Trust Boundary

This example proves that the configured finite branch searches for `m=92..95`
complete with `HITS=0` under the committed engine and manifests. As documented
in `docs/m92_m95_companion_runs.md`, the final theorem still needs the analytic
derivation of any case-specific reduction constants, especially the tighter
`m=94` and `m=95` caps.
