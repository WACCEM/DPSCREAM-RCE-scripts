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

---

## Resolution-dependent parameters: 3 km → 1 km

This section documents which `atmchange` parameters need to be reviewed when refining the domain resolution. Reference scripts:

- 3 km reference: `run_dpxx_scream_RCE_300.sh` — `model_dtime=100s`, `dyn_dtime=8.333s`, `num_ne_x/y=50`, domain 500 km
- 1 km target: `run_cpu_dpxx_scream_RCE_dx1km.sh` — `model_dtime=30s`, `dyn_dtime=2.5s`, `num_ne_x/y=200`, domain 600 km

Resolution ratio: dx(3km) / dx(1km) ≈ 3.33×

### `rad_frequency` — **needs increasing** ⚠️

| Script | `model_dtime` | `rad_frequency` | Radiation interval |
|---|---|---|---|
| 3 km | 100 s | 3 | **300 s (~5 min)** |
| 1 km (current) | 30 s | 3 | **90 s (~1.5 min)** |
| 1 km (recommended) | 30 s | **10** | **300 s (~5 min)** |

Both scripts explicitly set `rad_frequency=3`, and the namelist default is also `3` for all `DP-EAMxx` compsets regardless of resolution. At 1 km this causes radiation to be called 3× more frequently than at 3 km, significantly increasing cost with no physical justification. To maintain a ~5 min radiation interval:

```bash
./atmchange rad_frequency=10   # 10 × 30 s = 300 s
```

### `nu` (4th-order hyperviscosity) — **keep as-is, but monitor**

Both scripts use `nu=0.216784`, which is the DP-EAMxx default in `namelist_defaults_scream.xml`. The developer intentionally kept this value across resolutions. The dynamics timestep already scales with resolution (2.5 s vs 8.33 s), providing some additional implicit damping. If numerical noise or blow-up occurs, the first steps are:

1. Increase `hypervis_subcycle` (see below)
2. Modestly reduce `nu` toward `~0.05`

### `nu_top` (2nd-order top-of-model sponge) — **already correctly scaled** ✓

| Script | `nu_top_dyn` | Notes |
|---|---|---|
| 3 km | `1.0e4` | Default for DP-EAMxx in XML |
| 1 km | `3000.0` | ≈ 1e4 / 3.33 — matches resolution ratio |

Comment in the run script: "factor of 2 increase in resolution → factor of 2 decrease of `nu_top`". Correctly applied.

### `hypervis_subcycle` — **increase if stability issues arise**

Default is `1` for all DP-EAMxx compsets (from `namelist_defaults_scream.xml`). Neither script changes it. At 1 km with the shorter dynamics timestep, the hyperviscosity CFL condition is tighter. If instability occurs:

```bash
./atmchange dynamics::hypervis_subcycle=2
```

Note: `hypervis_subcycle` is an integer namelist parameter not in the F90 `set_homme_int_param_f90` integer setter (which only handles `ftype`, `ne`, `qsize`, `num_steps`). It is set through the EAMxx XML parameter system via `atmchange dynamics::hypervis_subcycle`.

### `dt_remap_factor` — **keep as-is** ✓

Both scripts use `dt_remap_factor=2`. At 1 km: remap every `2 × 2.5 s = 5 s`. Fine.

### `mac_aero_mic number_of_subcycles` — **keep as-is** ✓

Default is `1` for DP-EAMxx in the XML. Both scripts use the default.

### `se_ftype` — **keep as-is** ✓

Both scripts set `se_ftype=2` (no change needed at 1 km).

### Summary

| Parameter | 3 km value | 1 km current | 1 km recommended | Action |
|---|---|---|---|---|
| `rad_frequency` | 3 (300 s) | 3 (90 s) | **10 (300 s)** | **Change** |
| `nu` | 0.216784 | 0.216784 | 0.216784 | Keep (monitor) |
| `nu_top` | 1.0e4 | 3000.0 | 3000.0 | Done ✓ |
| `hypervis_subcycle` | 1 | 1 | 2 if unstable | Contingency |
| `dt_remap_factor` | 2 | 2 | 2 | Keep ✓ |
| `model_dtime` | 100 s | 30 s | 30 s | Done ✓ |
| `dyn_dtime` | 8.333 s | 2.5 s | 2.5 s | Done ✓ |

---

## Why `nu` does not need to change with resolution

### Default value location

`namelist_defaults_scream.xml`:
```xml
<nu>3.4e-08</nu>                          <!-- global (spherical) default -->
<nu COMPSET=".*DP-EAMxx">0.216784</nu>    <!-- DP-SCREAM override, all resolutions -->
```

There is one single DP-EAMxx `nu` value with no `hgrid`-specific entries. Every DP-SCREAM reference script (MC3E, RCE 300K, RCE 1km) uses the same `nu=0.216784`.

### Tensor hyperviscosity makes `nu` resolution-independent

With `hypervis_scaling=3.0` (the EAMxx default in the XML, not overridden in any DP script), HOMME uses **tensor hyperviscosity**. For each element, the code in `planar_mod.F90::metric_atomic()` and `cube_mod.F90` builds a local viscosity tensor `tensorVisc` from the eigenvalues of the element metric tensor:

$$\lambda^*_i = \frac{1}{\text{eig}_i^{\;\texttt{hypervis\_scaling}/4}}$$

For a uniform planar grid, $\text{eig}_i \sim dx^{-2}$, so $\lambda^*_i \sim dx^{\texttt{hypervis\_scaling}/2}$. The biharmonic operator applies the tensor twice (two Laplace iterations), giving an effective local viscosity:

$$\nu_\text{eff}(x) = \nu \cdot V(x), \quad V \sim (\lambda^*)^4 \cdot \text{eig} \propto dx^{2\cdot\texttt{hypervis\_scaling}-2}$$

For `hypervis_scaling=3.0`:

$$\nu_\text{eff} \propto \nu \cdot dx^{4}$$

The tensor automatically scales the effective dissipation with the **4th power of the local grid spacing**. Going from 3 km to 1 km:

$$\frac{\nu_\text{eff}(1\text{km})}{\nu_\text{eff}(3\text{km})} = \left(\frac{1}{3}\right)^4 \approx \frac{1}{81}$$

The effective damping is already reduced by ~81× at 1 km relative to 3 km — with no change to `nu`. This is why `nu` is a dimensionless scaling factor, not a dimensional viscosity coefficient.

### Contrast with `nu_top`

`nu_top` uses **constant-coefficient** (non-tensor) 2nd-order viscosity. There is no automatic resolution scaling, which is why it must be reduced explicitly when refining the grid — and was correctly reduced from `1.0e4` to `3000.0` for the 1 km case (matching the ~3.33× resolution ratio).

---

## What is `dt_remap_factor`?

`dt_remap_factor` controls how often HOMME performs its **vertical remapping** step, expressed as a multiple of the dynamics timestep (`dyn_dtime`).

### Background: vertically Lagrangian dynamics

HOMME uses a vertically Lagrangian formulation during the dynamics integration. The vertical coordinate surfaces move with the flow (like air parcels floating up and down), which avoids vertical transport errors during the fast dynamics subcycling. After every `dt_remap_factor` dynamics timesteps, the solution is **remapped** back to fixed hybrid-sigma (Eulerian) pressure levels. From `control_mod.F90`:

```fortran
! If dt_remap_factor > 0, the vertical remap time step is
! dt_remap_factor * tstep.
```

### Effect in the two scripts

| Script | `dyn_dtime` | `dt_remap_factor` | Remap interval |
|---|---|---|---|
| 3 km | 8.333 s | 2 | **16.67 s** |
| 1 km | 2.5 s | 2 | **5.0 s** |

The remap is already applied more frequently at 1 km simply because the dynamics timestep is shorter. The factor of 2 means: do two dynamics subcycles in Lagrangian mode, then remap. This is a standard cost-accuracy tradeoff — remapping every step (`=1`) is most accurate but most expensive; larger values reduce cost but allow more Lagrangian distortion to accumulate.

### Is `dt_remap_factor=2` appropriate at 1 km?

Yes. The 5 s remap interval at 1 km is shorter (more frequent) than the 16.67 s interval at 3 km, so vertical accuracy is if anything improved. The EAMxx XML default is `2` for all resolutions, and there is no reason to change it.

---

## What is `se_ftype`?

`se_ftype` ("spectral element forcing type") controls **how physics tendencies are applied to the dynamics state** at the dynamics-physics coupling interface in HOMME. It is set via `./atmchange se_ftype=2`.

### Valid values in EAMxx/SCREAM

Only three values are accepted (enforced in `cxx_f90_interface_theta.cpp`):

| Value | Name | Meaning |
|---|---|---|
| `-1` | `FORCING_OFF` | Physics forcing ignored entirely — for energy balance testing only |
| `0` | `FORCING_0` | **Tendency-increment** style: $qdp_\text{new} = qdp_\text{old} + f_q \cdot \Delta t$ |
| `2` | `FORCING_2` | **Adjustment** style: $qdp_\text{new} = dp \cdot f_q$ (physics overwrites state directly) |

### The difference between `ftype=0` and `ftype=2`

With `ftype=0` (`adjustment=false`), physics provides a tracer **tendency** $f_q$, and the dynamics state is updated by adding the increment:

$$qdp_\text{new} = qdp_\text{old} + f_q \cdot \Delta t$$

With `ftype=2` (`adjustment=true`, in SCREAM builds), physics provides the **updated mixing ratio** directly, and the dynamics state is replaced:

$$qdp_\text{new} = dp \cdot f_q$$

In addition, `ftype=2` adjusts the surface pressure $ps$ to account for the mass change due to moisture:

$$\Delta ps = \sum_k dp_k \left(f_{q,k} - q_k\right)$$

### Why `se_ftype=2` is used in EAMxx

EAMxx physics packages (SHOC, P3, etc.) work with mixing ratios and deliver **updated state values** rather than finite-difference tendencies. Using `ftype=2` is the natural fit:
- No need to back-compute $(q_\text{new} - q_\text{old}) / \Delta t$
- No accumulation of floating-point error from adding small increments to large values
- Surface pressure and column mass are kept consistent with the updated moisture field

Both scripts correctly set `se_ftype=2`. This is the standard production setting for EAMxx and should not be changed.

---

## EAMxx Changes: `v3.0.2` → `8e96857632` (`v3.1.0-alpha-1452`)

**Period:** December 17, 2024 → February 26, 2025 (~10 weeks, ~629 eamxx commits)

The colleague's simulation (`scream_dpxx_RCE_300K`) used git version `8e96857632`.
The current model code at `/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM` is on branch
`ksa/uvwinds` at commit `75de3ed0f8` (`v3.0.2-81`), which diverged from `v3.0.2`.

### Microphysics (P3)

- **Heterogeneous freezing from aerosols** (PR #6947): Added aerosol-mediated
  heterogeneous ice nucleation (`use_hetfrz_classnuc`) into P3 as a
  runtime-controllable option, with logic to exclude ACI inputs to P3 when the
  option is off.
- **Expanded P3 runtime parameters** (`mahf708/p3/runtime-params`):
  Autoconversion radius, accretion exponents (split into two separate
  parameters), a flag for ice production processes, and cloud water
  autoconversion tuning are now configurable via namelist at runtime without
  recompilation — previously they were compile-time constants.
- **Subgrid cloud fraction overrides** (PR #6849): New namelist variables to
  disable P3's subgrid cloud fraction calculation; cloud fraction flags
  refactored into the `P3Runtime` struct.
- **`cld_frac_glaciated` fix**: Defined `cld_frac_glaciated`, applied `cldmin`
  to avoid division by zero, and applied the same procedure to `qisub`.
- **P3 init ported from Fortran to C++** (PR #6845): `p3_init` fully converted
  from F90 to CXX.
- **Bug fixes**: Fixed bug in `qr2qi` homogeneous freezing tendency; fixed ETI
  missing case with 5 sedimentation species.

### Boundary Layer (SHOC)

- **Default `lambda_high` changed to 0.08** (PR #6797, **non-BFB**):
  `lambda_high` controls the turbulence length scale in SHOC's closure. This
  default change affects TKE, cloud fraction, and moisture in the PBL in all
  simulations.
- **Bug fix in SHOC**: Fixed a conditional jump on uninitialized memory
  (potential GPU/reproducibility issue).
- **F90-to-CXX porting**: Several SHOC assumed-PDF functions converted to C++
  (buoyancy flux, liquid water flux, cloud liquid variance, SGS liquid, `qs`,
  temperature, PDF parameter routines).

### Aerosols (MAM4xx)

- **Marine organic emissions connected**: Full interface from file I/O through
  to MAM4xx for sea-spray organic aerosol.
- **Online dust/sea-salt emissions**: Added soil erodibility file read,
  sea-salt number flux computation, dust emission matched to EAM grid cells.
- **Aerosol dry deposition**: Completed missing code in the dry deposition
  interface.
- **Washout rates (scavenging)**: MAM4xx microphysics interface updated to
  include `sethet` (below-cloud scavenging washout rates).
- **Aerosol vertical mixing control** (PR #6926): New flag to control whether
  aerosol vertical mixing by `dropmixnuc` is active.
- **MAM4xx submodule fast-forwarded** multiple times for GPU fixes and interface
  alignment.

### IOP Forcing

- **IOP as an ATM process** (PR #6787): IOP forcing refactored into a standalone
  atmosphere process (`IOPForcing`), making it more modular for DP-SCREAM setups.

### Radiation (RRTMGP)

- **Performance overhaul**: Removed all dynamic memory allocations from
  `rrtmgp run_impl`; significant Kokkos-based GPU performance improvements.
