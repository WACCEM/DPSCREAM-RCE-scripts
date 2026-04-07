# DP-SCREAM RCE 1 km — Perlmutter CPU Node Configuration

Script: `run_cpu_dpxx_scream_RCE_dx1km.sh`

---

## Domain geometry

| Parameter | Value |
|---|---|
| `num_ne_x` × `num_ne_y` | 200 × 200 = **40,000 elements** |
| Unique dynamics columns (3×3/element) | **360,000** |
| dx = dy | 600,000 / (200 × 3) = **1 km** |
| Timesteps for a 12 h segment | 1,440 physics (30 s), 17,280 dynamics (2.5 s) |
| Vertical levels | 128 |

## Perlmutter CPU hardware constraint

Each node has **128 physical cores** (2 × AMD EPYC 7763, 64-core). Because 40,000 = 2⁶ × 5⁴ and 128 = 2⁷, **128 does not divide 40,000**. Any `num_procs` that cleanly fills nodes at 128 tasks/node will have a slight load imbalance.

## Recommended configurations

### Option A — current: `num_procs=1024`, **8 nodes** (128 tasks/node) ✓
- 40,000 / 1024 ≈ 39 elements/rank — only 64 of 1,024 ranks carry 40 elements (6% of ranks, ~2.5% load imbalance). **Acceptable.**
- 1024 = 128 × 8 → perfectly fills 8 nodes (clean SLURM request)
- Reasonable for short tests; walltime of 2:30h may be tight for a full 12 h simulation at 1 km with 128 levels

### Option B — better throughput: `num_procs=2048`, **16 nodes** (128 tasks/node) ✓✓
- 40,000 / 2048 ≈ 19.5 → ~1,088 ranks get 20 elements, ~960 get 19 (slight imbalance, ~5%)
- 2048 = 128 × 16 → perfectly fills 16 nodes
- ~2× the compute of Option A; better TTTS (time to solution)

### Option C — exact balance: `num_procs=1600`, **25 nodes** (64 tasks/node) ✓✓✓
- 40,000 / 1600 = **exactly 25 elements/rank** — perfectly balanced
- To use all 128 cores per node: request `--ntasks-per-node=64 --cpus-per-task=2` and set `OMP_NUM_THREADS=2` (EAMxx/Kokkos can use OpenMP threads)
- Slight downside: requires more nodes (25 vs. 16), and non-standard 64-tasks/node setup

## Summary table

| Option | `num_procs` | Nodes | Tasks/node | Ele/rank | Balance |
|---|---|---|---|---|---|
| A (current) | 1,024 | 8 | 128 | 39–40 | ~2.5% imbalance |
| **B (recommended)** | **2,048** | **16** | **128** | **19–20** | ~5% imbalance |
| C (perfect balance) | 1,600 | 25 | 64 + 2 OMP threads | **25 (exact)** | perfect |

## Practical bottom line

For a **production 1 km RCE run** (12 h segments × 10 resubmits = 5 simulated days), **Option B (num_procs=2048, 16 nodes)** is the best practical choice: it cleanly fills standard Perlmutter nodes at 128 tasks/node, roughly halves the walltime relative to the current 8-node setup, and the ~5% load imbalance is inconsequential. Option C is worth trying if you want perfectly balanced runs or the walltime with 16 nodes is still too long.

The current `num_procs=1024` (8 nodes) is workable but likely under-resourced for sustained production at 1 km resolution.

---

## Lustre File System Striping for the Run Directory

After building the case, the run script applies Lustre striping to the run output directory:

```bash
lfs setstripe -c 16 -S 16M ${case_run_dir}
```

### What this does

Lustre (the parallel filesystem on `$PSCRATCH`) stripes files across multiple Object Storage Targets (OSTs) to allow parallel I/O. The flags set:

| Flag | Value | Meaning |
|---|---|---|
| `-c` | `16` | **Stripe count** — each new file in the directory is spread across 16 OSTs |
| `-S` | `16M` | **Stripe size** — each OST holds 16 MB chunks before moving to the next OST |

This only affects files created *after* the command is run. It is placed inside the `run_build` block because `case_run_dir` is created during the build step.

### Why 16 MB instead of the NERSC default 1 MB

The NERSC default 1 MB stripe size is tuned for a broad mix of workloads and performs well for codes that produce many medium-sized files with independent I/O. DP-SCREAM has a fundamentally different I/O profile:

| Quantity | Value |
|---|---|
| File sizes | ~17 GB (AVERAGE) + ~24 GB (INSTANT) |
| Records per file | 12 (one per 5-min output step) |
| Data per record | ~1.4 GB (AVG) / ~2 GB (INST) |
| MPI writers | 2048 ranks via scorpio/pnetcdf |
| Data per rank per record | ~0.7 MB (AVG) / ~1 MB (INST) |

With pnetcdf collective I/O, ROMIO (the MPI-IO layer) aggregates all ranks' contributions into large collective buffers before writing to the filesystem. The effective I/O unit hitting Lustre is the **ROMIO collective buffer size**, which defaults to **16–32 MB per aggregator**. If the Lustre stripe size is only 1 MB:

- Each collective buffer write crosses 16–32 stripe boundaries
- Each boundary crossing requires a separate Lustre lock acquisition
- What should be parallel I/O is effectively serialised

At 16 MB stripes:
- Each aggregated write lands on a single stripe → minimal lock contention
- A 2 GB record crosses only ~125 stripe boundaries instead of ~2,000
- Ranks' per-record contributions (~0.7–1 MB each) are far less likely to compete for the same stripe lock

### Could a larger stripe size help?

For files in the 17–24 GB range written by 2048 ranks, **32 MB** is also reasonable and is used in some E3SM benchmarks. The gain from 16 → 32 MB is much smaller than the gain from 1 → 16 MB, so 16 MB is a practical and well-tested choice. Going beyond 64 MB typically yields no further benefit and wastes OST space for smaller auxiliary files in the same directory.
