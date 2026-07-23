# V2 production performance review

This note records operational evidence from the first AWS v2 production
attempt. None of these timings are mathematical inputs or certificate claims.

## Environment

- AWS `c8a.8xlarge`, 32 vCPUs, 64 GiB RAM
- 30 concurrent prover processes
- pinned `collatz-v2:release` container
- C++ prover SHA-256
  `10ffa2fba9669a2c205268867e19f855c64335d522ab07e6d496283105fa7733`

## Failed scheduling experiment

The original planner used committed legacy branch timings, targeted 1,800
seconds per unit, and rounded segment counts upward to powers of two. It
created 3,098 initial units across 372 branches. The prover used a two-hour
timeout with adaptive midpoint splitting.

The attempt was stopped with:

- 352 accepted units, covering all planned `m=92..95` units and `m=96,k1=1`;
- 960 timed-out attempts;
- 4,058 current leaves after those 960 splits;
- approximately 1,920 CPU-hours spent on timed-out attempts;
- zero newly accepted nontrivial `m=96` units.

An isolated branch-local retry of `m=96,k1=2` ran for about 23 hours 39
minutes. It timed out all 128 depth-7 leaves and 202 depth-8 leaves, producing
330 further splits and no accepted unit. The `k1=2` branch alone accumulated
394 two-hour timeouts, about 788 discarded CPU-hours.

The runner and workers remained healthy. This was a partitioning and
scheduling failure, not an arithmetic failure or survivor.

## Root cause

Root-interval subdivision preserves exact coverage but does not divide search
cost linearly. Each unit repeats part of the recursive prefix search, and a
smaller root interval changes when the engine switches to deterministic
enumeration.

A local `m=96,k1=50` benchmark measured:

| Root segments | Recursive nodes | Deterministic values | Deterministic nodes |
| ---: | ---: | ---: | ---: |
| 1 | 1,300,386 | 22,688,061 | 37,889,132 |
| 2 | 1,452,224 | 24,930,302 | 44,570,156 |
| 4 | 1,579,470 | 26,724,095 | 51,571,500 |
| 8 | 1,674,939 | 28,005,375 | 58,769,964 |
| 32 | 1,770,144 | 29,188,096 | 73,399,852 |
| 64 | 1,783,056 | 29,331,456 | 80,739,884 |

Two segments added moderate overhead while reducing the longest individual
unit. Aggressive subdivision increasingly duplicated work. A short AWS check
also confirmed that 30 workers keep the machine busy; worker count was not the
primary failure.

The FIFO adaptive runner compounded the problem by placing children behind all
untouched units. It therefore paid the timeout cost for whole generations
before testing whether one split was sufficient.

## Corrected production policy

1. Use the historical timings only to decide whether a branch receives one or
   two initial units.
2. Cap every branch at two units with
   `--max-segments-per-branch 2`.
3. Schedule expensive branches first with `--order timing-desc`.
4. Run accepted production units to completion with `--timeout 0`.
5. Keep adaptive splitting as a bounded diagnostic tool, not the default
   production path.
6. Report completed branches and discarded timeout CPU-hours separately from
   the mutable leaf count.

The search engines and authenticated binaries are unchanged. Existing
accepted results remain valid whenever their unit IDs remain in the corrected
plan.
