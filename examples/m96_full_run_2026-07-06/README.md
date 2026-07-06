# m=96 Full Branch Run Example (2026-07-06)

This directory contains a completed `m=96` branch-certificate run from the
existing manifest `manifests/tasks.jsonl`.

## Result

- Verifier result: `ACCEPT`
- Verified tasks: `75`
- Cover: `m96_k1_1_75`
- Combined log hash: `d8f99127dceeccd3a9fbcee254a0334fa9940a9cc8d231801e7d46adcd0b2f65`
- Source SHA-256 from manifest: `2e364660d26cd7d06ea07f22d555e8b758bc75955b7d71e0a98fb98f846ba3b0`

Reverify this example from the repository root with:

```bash
python3 scripts/verify_certificate.py \
  --tasks manifests/tasks.jsonl \
  --runs examples/m96_full_run_2026-07-06/runs \
  --source src/m96/affine_ladder_prefix.cpp \
  --exe ./build/affine_ladder_prefix
```

## Machine And Run

- CPU: AMD Ryzen 5 3600 6-Core Processor
- Logical CPUs: 12
- Physical cores: 6 core(s), 2 thread(s) per core
- OS/kernel: `Linux sinruda 7.0.13-zen1-1-zen #1 ZEN SMP PREEMPT_DYNAMIC Tue, 23 Jun 2026 11:14:06 +0000 x86_64 GNU/Linux`
- Runner jobs: `8`
- Runner timeout: `0` (disabled)
- Runner order: `desc`
- Approximate wall time: 5d 12h 6m 5s (475,565 seconds)
- Summed branch CPU time: 990.49 hours (41.27 core-days)

The wall time is estimated from the local `dist/run_logs/full_run.log` file birth
and final modification time. The full progress log was about 13 MB and is not
included here because it is mostly repeated heartbeat snapshots; a final excerpt
is kept as `runner_final_tail.log`.

## Timing Notes

- Slowest branch: `k1=12` at 214381.379 seconds (59.550 hours)
- Fastest branch: `k1=1` at 0.501 seconds (0.000139 hours)
- All branches exited with code `0`, `timed_out=false`, `RESULT: PASS`, and `HITS=0`.

See `branch_timings.tsv` for the complete per-branch timing and log-hash table.

## Files

- `runs/`: accepted root certificate surface, 75 `.log` files and 75 `.meta.json` files
- `verify_certificate.accept.json`: final verifier output
- `status_final.json`: final runner status summary
- `branch_timings.tsv`: per-branch seconds, hours, result, hits, and log SHA-256
- `machine/`: captured `lscpu` and `uname -a` output
- `runner_final_tail.log`: final excerpt of the detached runner log
