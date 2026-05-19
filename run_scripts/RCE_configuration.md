# DP-SCREAM RCE 1 km — Perlmutter CPU Node Configuration

Script: `run_cpu_dpxx_scream_RCE_dx1km.sh`

---

## Domain geometry

### "1km" grid
| Parameter | Value |
|---|---|
| `num_ne_x` × `num_ne_y` | 200 × 200 = **40,000 elements** |
| Unique dynamics columns (3×3/element) | **360,000** (600×600 GLL grid) |
| Dynamics dx = dy | 600,000 / (200 × 3) = **1 km** |
| Unique physics columns (PG2, 2×2/element) | **160,000** (400×400 Gauss grid) |
| Physics dx = dy (PG2) | 600,000 / (200 × 2) = **1.5 km** |
| Timesteps for a 12 h segment | 1,440 physics (30 s), 17,280 dynamics (2.5 s) |
| Vertical levels | 128 |

### "3km" grid
| Parameter | Value |
|---|---|
| `num_ne_x` × `num_ne_y` | 60 × 60 = **3,600 elements** |
| Unique dynamics columns (3×3/element) | **32,400** (180×180 GLL grid) |
| Dynamics dx = dy | 600,000 / (60 × 3) = **3.33 km** |
| Unique physics columns (PG2, 2×2/element) | **14,400** (120×120 Gauss grid) |
| Physics dx = dy (PG2) | 600,000 / (60 × 2) = **5 km** |
| Timesteps for a 12 h segment | 1,440 physics (100 s), 17,280 dynamics (8.33 s) |
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

- **Default `lambda_high` changed from 0.04 to 0.08** (PR #6797, **non-BFB**):
  `lambda_high` is an upper bound on the SHOC turbulence length scale parameter
  $\lambda$, which controls the mixing length in the TKE closure. The value was
  doubled (0.04 → 0.08), allowing more vigorous vertical mixing in convective
  conditions. This change affects TKE, cloud fraction, and moisture in the PBL
  in all simulations.
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

---

## EAMxx Changes: `8e96857632` → `8426cb31c7` (`v3.1.0-alpha-3683`)

**Period:** February 26, 2025 → September 23, 2025 (~7 months, ~995 eamxx commits)

Note: The external forcing (elevated emissions) bug fix (PR #7315) described
below affects only simulations using the full MAM4xx aerosol package with
prescribed 3D elevated emissions. The `FRCE-SCREAMv1-DP` RCE compset uses SPA
(Simple Prescribed Aerosols) instead, so **this bug is not relevant to DP-SCREAM
RCE simulations**.

### Boundary Layer (SHOC)

- **1.5 TKE closure option added** (PR #7188, **non-BFB**): New runtime flag
  `shoc_1p5tke=true` reduces SHOC to a simpler 1.5-order TKE scheme by zeroing
  SGS scalar variances/covariances and the third moment of vertical velocity.
  This collapses the assumed-PDF to an all-or-nothing closure and changes how
  eddy diffusivities and mixing length are defined. A significant new option for
  idealized and high-resolution runs such as DP-SCREAM.
- **FPE fix in SHOC** (PR #7368): Fixed a floating-point exception that could
  cause crashes on some platforms.
- **SHOC condensation/evaporation diagnostics**: Added `shoc_cond` and
  `shoc_evap` as diagnostic outputs; fixed their computation order (now before
  `ql` update).
- **Tracer turbulence advection control** (PR #6789, **non-BFB for MAM**):
  Processes can now opt out of SHOC turbulence advection for individual tracers
  (`turbulence_advected=false`), allowing aerosol tracers to be advected only by
  dynamics.

### Microphysics (P3)

- **Separate liquid/ice cloud fractions in P3** (PR #6966, BFB): P3 now receives
  separate `cldfrac_liq` and `cldfrac_ice` instead of a single `cldfrac_tot`,
  and the Wegener-Bergeron-Findeisen (WBF) process is modified accordingly (based
  on Lin Lin's work in THREAD). Lays the groundwork for improved mixed-phase
  cloud treatment.
- **Mixed-phase cloud improvements, part 2** (PR #7223, BFB): Further
  refinements to the separate mixed-phase cloud fraction option.
- **New default cloud fraction `r` values** (PR #7412, **non-BFB**):
  Resolution-dependent defaults for the cloud fraction parameter `r` updated
  based on group evaluation — directly affects cloud cover and radiation.
- **P3 extra diagnostics** (PR #7245): Additional P3 diagnostic output fields
  enabled.
- **Equivalent radar reflectivity diagnostic**: Added `diag_equiv_reflectivity`
  as a P3 output field.
- **Nested parallelism in P3 pre/post-processing** (PR #7168): GPU performance
  improvement using nested Kokkos team policies.

### Aerosols (MAM4xx)

- **External forcing (elevated emissions) bug fix** (PR #7315, **non-BFB**):
  Critical bug where BC, POM, and SO4 elevated emission fluxes were ~50% of
  their correct values (off by a factor of ~2). Significant error correction for
  simulations using MAM4xx with prescribed elevated emissions. *Not relevant to
  RCE/DP-SCREAM which uses SPA.*
- **SPA CCN→Nc activation functionalized** (PR #7120): Ability to use different
  functional forms for the CCN-to-droplet-number activation in SPA.
- **Aerosol dry deposition fix** (PR #7083): Fixed the dry deposition update.
- **`ndrop` top-level fix** (PR #7141): Fixed droplet number calculation at the
  model top.
- **3D SO4/H2SO4 aqueous chemistry diagnostic fields** added.
- **Prescribed ozone option in MAM4xx**: Added ability to prescribe ozone
  independently in MAM.
- **Linoz on/off toggle** added.

### Gravity Wave Drag (GWD)

- **GWD ported to C++** (PR #7597): `gwd_compute_stress_profiles_and_diffusivities`
  converted from Fortran to C++.

### Deep Convection (ZM)

- **ZM placeholder infrastructure added**: Initial scaffolding for bridging the
  Zhang-McFarlane deep convection scheme into EAMxx. Not yet functional — only
  the framework was created in this period.

### Radiation (RRTMGP / COSP)

- **YAKL dependency removed** (PR #7345): RRTMGP fully migrated to Kokkos,
  eliminating the YAKL GPU library dependency.
- **Radiation/COSP frequency logic fixed** (PR #7337, **non-BFB**): Radiation
  now runs on steps 1, `rad_freq+1`, `2*rad_freq+1`, etc., consistent with the
  output frequency convention. Previously the timing was offset. This changes
  when radiation is called relative to the timestep count.
- **Radiation restart fix**: Radiation can now correctly run on the first step
  after a restart.

---

## P3 Subgrid Cloud Fraction Flags: Details and RCE Implications

### What the flags do

PR #6849 (in the `v3.0.2 → 8e96857632` range) added three boolean namelist
parameters to `P3Runtime`:

```cpp
bool set_cld_frac_l_to_one = false;  // liquid cloud fraction seen by P3
bool set_cld_frac_i_to_one = false;  // ice cloud fraction seen by P3
bool set_cld_frac_r_to_one = false;  // rain fraction seen by P3
```

**Default: `false` in both `8e96857632` and `8426cb31c7`.** The subgrid cloud
fraction treatment is still active by default — the flags are opt-in only.

Normally P3 receives a subgrid cloud fraction from SHOC (e.g., `cld_frac_t < 1`
in a partially cloudy grid cell). P3 uses these fractions to derive in-cloud/in-
rain mixing ratios, which control process rates such as autoconversion,
accretion, and rain evaporation. For example, if only 30% of a grid cell is
cloudy, P3 concentrates the cloud liquid into that 30%, giving a higher in-cloud
value that affects microphysical rates.

When any flag is set to `true`, P3 replaces the corresponding cloud/rain
fraction with 1 everywhere — the "overcast" or "no subgrid variability"
assumption — so the in-cloud mixing ratio equals the grid-mean value.

The merge commit message for PR #6849 states explicitly:

> *"Currently they default to False, but we will likely enable them as part of
> the effort to address the **popcorn convection problem**."*

### Additional flags in `8426cb31c7`

Compared to `8e96857632`, the newer version adds two more opt-in P3 flags:

```cpp
bool use_separate_ice_liq_frac = false;  // PR #6966: separate cld_frac_l/i
bool extra_p3_diags            = false;  // PR #7245: extra diagnostic fields
```

All subgrid cloud fraction override flags remain `false` (opt-in) across both
versions.

### Implications for DP-SCREAM RCE simulations

At convection-permitting resolutions (1–3 km), individual convective updrafts
are partially resolved explicitly, but SHOC still parameterizes *subgrid*
variability and produces fractional cloud cover < 1. This creates a physical
inconsistency: the explicit dynamics resolves the convective cell while SHOC
tells P3 that only a fraction of the grid cell is cloudy. P3 then concentrates
mixing ratios into that fraction, artificially inflating in-cloud values and
process rates.

**With default (`false`):** P3 uses subgrid cloud fractions from SHOC. Rain
fraction < 1 concentrates rain into a sub-portion of the cell, increasing the
effective rain evaporation rate. More rain evaporation → stronger cold pools →
more widespread triggering of new convection → tendency toward disorganized
"popcorn" convection and potentially too-frequent precipitation.

**With flags set to `true`:** Cloud and rain fractions are all 1. P3 uses
grid-mean mixing ratios directly, reducing rain evaporation. Weaker/fewer cold
pools → less triggering of new convection → potentially more organized
convective systems, which is more physically consistent with explicitly resolved
convection at these resolutions.

For RCE in particular, convective self-aggregation is a key phenomenon of
scientific interest. Setting `set_cld_frac_r_to_one = true` (the rain fraction
flag, which primarily affects rain evaporation) could promote aggregation by
suppressing excessive cold-pool-driven triggering. If popcorn-like convection is
observed in your RCE runs, this is one of the first namelist parameters worth
testing via `atmchange`:

```bash
./atmchange physics::p3::set_cld_frac_r_to_one=true
./atmchange physics::p3::set_cld_frac_l_to_one=true
./atmchange physics::p3::set_cld_frac_i_to_one=true
```

---

## Why domain-mean PW is lower (and spatial variance higher) in v3.1.0-alpha vs. v3.0.2

**Observed symptom:** domain-mean precipitable water is higher with the older
code (v3.0.2 / `ksa/uvwinds`); spatial variance is lower. Changing
`lambda_high` from 0.04 to 0.08 in the older code (RCE03) did not close the
gap, so the cause lies elsewhere.

The combination of **lower mean PW + higher spatial variance** is the signature
of increased convective self-aggregation: the dry subsiding regions (which
dominate by area) are drier, and the moisture contrast between moist convective
cores and the dry environment is sharper.

### Most likely candidates in the v3.0.2 → `8e96857632` transition

Since both `8e96857632` and `8426cb31c7` show the same departure from v3.0.2,
the primary cause must originate in this first transition.

#### 1. IOP refactored into a standalone ATM process (PR #6787) — **highest priority**

The RCE configuration uses `do_iop_subsidence=true`, so this change directly
applies. Moving IOP forcing from an embedded step into a standalone atmosphere
process changes **where in the physics timestep sequence large-scale subsidence
is applied** — before or after SHOC, before or after P3, etc. Even with
identical subsidence values, the order-of-operations relative to condensation
and turbulent moistening changes the effective drying:

- If subsidence now acts *after* SHOC instead of before, SHOC can no longer
  partially counteract the imposed drying through turbulent moistening before
  subsidence removes that moisture.
- A systematic shift in application timing lowers domain-mean PW without any
  change to the subsidence profile.
- The ordering change also affects columns differently depending on their
  convective state, amplifying moisture contrasts between ascending and
  subsiding columns — directly explaining the higher spatial variance.

**How to check:** inspect the `atmosphere_processes` order in `scream_input.yaml`
for both cases:

```bash
grep -A 60 "atmosphere_processes" \
  /pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE01_dx3km_gpu/run/data/scream_input.yaml \
  | grep -E "type:|iop|shoc|p3|mac"

grep -A 60 "atmosphere_processes" \
  /pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE02_dx3km_gpu/run/data/scream_input.yaml \
  | grep -E "type:|iop|shoc|p3|mac"
```

#### 2. P3 runtime parameters: compile-time constants → XML-based defaults (non-BFB)

Autoconversion radius, accretion exponents (now split into two separate
parameters), and cloud water autoconversion tuning were previously **hard-coded
compile-time constants**. They are now exposed as runtime parameters with their
own XML defaults. If those XML defaults differ even slightly from the old
compiled-in values, precipitation efficiency changes:

- A smaller autoconversion threshold radius → more efficient warm rain →
  faster removal of cloud water → **lower PW**
- Split accretion exponents with asymmetric defaults → changed rain growth
  rate → affects how quickly rain reaches the surface vs. evaporates

**How to check:** compare the P3 parameter block in `RCE02`'s `scream_input.yaml`
against the hard-coded values in the v3.0.2 source:

```bash
grep -A 30 "^\s*p3:" \
  /pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE02_dx3km_gpu/run/data/scream_input.yaml
```

### Additional candidates in the `8e96857632` → `8426cb31c7` transition

If the PW difference grows further in the second transition, these are the
relevant non-BFB changes:

#### 3. New default cloud fraction `r` parameter values (PR #7412, non-BFB)

The cloud fraction PDF shape parameter `r` was updated with
**resolution-dependent defaults** based on group evaluation. This directly
affects fractional cloud cover → longwave cloud radiative effect (CRE) in
subsiding regions → the radiative aggregation feedback. Reduced cloud fraction
in clear-sky/subsiding regions enhances the longwave cooling contrast between
moist and dry columns, which is the primary radiative mechanism driving
self-aggregation.

#### 4. Separate liquid/ice cloud fractions in P3 (PR #6966)

P3 now receives `cldfrac_liq` and `cldfrac_ice` separately instead of a single
`cldfrac_tot`, and the Wegener-Bergeron-Findeisen (WBF) process is modified
accordingly. More efficient WBF (ice growth at the expense of supercooled
liquid) → faster glaciation → faster sedimentation → more efficient
precipitation → **lower PW**.

#### 5. Radiation timing fix (PR #7337, non-BFB)

Radiation now runs on steps 1, `rad_freq+1`, `2*rad_freq+1`, ... instead of
the previously offset schedule. In RCE, the **phase of the radiation call
relative to the convective-dynamics cycle** matters for the radiative-convective
feedback that drives aggregation. A systematic shift in when the clear-sky
radiative cooling differential is applied can change the aggregation tendency.

### Summary table

| Change | Transition | Mechanism | PW↓ | Variance↑ |
|---|---|---|---|---|
| IOP as ATM process (PR #6787) | v3.0.2 → `8e96857632` | Subsidence applied at different timestep position | ✓✓ | ✓✓ |
| ~~P3 compile-time → XML defaults~~ | v3.0.2 → `8e96857632` | All constants unchanged (verified) | — | — |
| **Fixed TSI 551.58 vs. full ~1361 W/m²** | v3.0.2 → `8e96857632` | Fundamentally different radiative forcing regime | **✓✓✓** | **✓✓✓** |
| Cloud fraction `r` defaults (PR #7412) | `8e96857632` → `8426cb31c7` | CRE contrast → aggregation feedback | ✓ | ✓✓ |
| Separate liq/ice cldfrac in P3 (PR #6966) | `8e96857632` → `8426cb31c7` | WBF efficiency, precipitation rate | ✓ | ✓ |
| Radiation timing fix (PR #7337) | `8e96857632` → `8426cb31c7` | Radiative-convective coupling phase | ✓ | ✓ |

The IOP process reordering and the P3 parameter defaults are the most
actionable to investigate first, since they apply to the first transition where
the bulk of the PW difference must originate.

---

## Findings from YAML comparison: RCE01 vs RCE02 `scream_input.yaml`

Files compared (copied to `run_scripts/debug_files/`):
- `scream_input_RCE01_dx3km_gpu.yaml` — v3.0.2 (`ksa/uvwinds`, `75de3ed0f8`)
- `scream_input_RCE02_dx3km_gpu.yaml` — v3.1.0-alpha-3683 (`8426cb31c7`)

### Finding 1 — IOP process sequence (PR #6787 confirmed)

**RCE01 physics process list:**
```yaml
physics:
  atm_procs_list:
  - mac_aero_mic   # tms → shoc → cldFraction → spa → p3
  - rrtmgp
```
There is no `iop_forcing` entry anywhere in the process list. IOP was handled
by the **driver** as a special code path keyed on `enable_iop: true` in
`driver_options`. In v3.0.2, IOP forcing was applied from inside
`eamxx_homme_driver_mod.F90` — effectively within the Homme dynamics step,
**before** the physics group ran.

**RCE02 physics process list:**
```yaml
physics:
  atm_procs_list:
  - iop_forcing    # ← standalone process, FIRST in physics
  - mac_aero_mic   # tms → shoc → cld_fraction → spa → p3
  - rrtmgp
```
IOP forcing is now an explicit atmosphere process and is the first to execute
in the physics sequence.

**Net effect on timestep order:**

| Stage | RCE01 (v3.0.2) | RCE02 (new) |
|---|---|---|
| 1 | `sc_import` | `sc_import` |
| 2 | `homme` (dynamics) | `homme` (dynamics) |
| 3 | *(IOP forcing embedded here, inside homme driver)* | `iop_forcing` ← **subsidence here** |
| 4 | `tms` | `tms` |
| 5 | `shoc` | `shoc` |
| 6 | `cldFraction` | `cld_fraction` |
| 7 | `spa` | `spa` |
| 8 | `p3` | `p3` |
| 9 | `rrtmgp` | `rrtmgp` |
| 10 | `sc_export` | `sc_export` |

The practical ordering difference is **small**: in both versions, subsidence
acts after dynamics and before SHOC/P3. The IOP refactor moved it from a
hard-coded hook inside the dynamics module to an explicit first-in-physics
step. The critical distinction is **whether the fields seen by SHOC at step 5
are pre- or post-subsidence**: in both cases the answer is post-subsidence, so
the sequence impact of PR #6787 alone is likely **minor**.

**Conclusion on PR #6787 as PW cause:** the process reordering itself is not
the primary driver of the PW difference. The larger changes are in P3
microphysics parameters (see below).

**Can you run the old code with the new process order?** No — v3.0.2 does not
have the `IOPForcing` process class; it cannot be configured via `atmchange`.
In the new code, you can experiment with moving `iop_forcing` to a different
position (e.g., after `mac_aero_mic`) using `atmchange` to quantify any
ordering sensitivity, but this is unlikely to explain the bulk of the PW gap.

### Finding 2 — SPA CCN → Nc activation (most impactful P3 change) ⚠️

| Parameter | RCE01 (v3.0.2) | RCE02 (new) |
|---|---|---|
| `p3_spa_to_nc` | `1.0` (linear, `Nc = 1.0 × CCN`) | — |
| `spa_ccn_to_nc_factor` | — | `2000.0` |
| `spa_ccn_to_nc_exponent` | — | `0.55` |

In RCE01, the CCN-to-droplet-number conversion is a simple linear multiplier:
$N_c = 1.0 \times \text{CCN}$ (in the same units). In RCE02 (PR #7120), a
Twomey-type power law is used:

$$N_c = 2000 \times \text{CCN}^{0.55}$$

This is a **qualitatively different functional form**, not just a changed
coefficient. For typical maritime SPA values (~10⁸ m⁻³), the new formula gives
~5×10⁷ m⁻³ (50 cm⁻³), while for continental values (~10⁹ m⁻³) it gives
~2×10⁸ m⁻³ (200 cm⁻³). The sublinear exponent (0.55 < 1) means $N_c$ is less
sensitive to CCN than in the old linear scheme. Changes to $N_c$ directly
affect cloud droplet effective radius, autoconversion onset, and precipitation
efficiency — making this a strong candidate for the PW difference.

### Finding 3 — P3 autoconversion/accretion exponents

| Parameter | XML/YAML name (new code) | RCE01 old value | RCE02 new default | Changed? |
|---|---|---|---|---|
| Autoconversion prefactor | `autoconversion_prefactor` | `1350.0` (`P3_Constants`) | `1350.0` | No |
| Autoconversion radius | `autoconversion_radius` | `25.0e-6 m` (via `CONS3 = 1/(CONS2·r³)`, `physics_constants.hpp:59`) | `25.0e-6 m` | **No** |
| Autoconversion `qc` exponent | `autoconversion_qc_exponent` | `2.47` (hardcoded in formula) | `2.47` | No |
| Autoconversion `Nc` exponent | `autoconversion_nc_exponent` | `1.79` (hardcoded in formula) | `1.79` | No |
| Accretion prefactor | `accretion_prefactor` | `67.0` (`P3_Constants`) | `67.0` | No |
| Accretion `qc` exponent | `accretion_qc_exponent` | `1.15` (single exponent on product `qc·qr`) | `1.15` | No |
| Accretion `qr` exponent | `accretion_qr_exponent` | `1.15` (same product exponent) | `1.15` | No |

**Conclusion: none of these parameters changed.** The old compile-time constants in v3.0.2
exactly match the new XML defaults. Finding 3 is **not a source of the PW difference**.

Key sources in `model/E3SM`:
- `physics_constants.hpp:59`: `CONS3 = 1.0/(CONS2*1.562500000000000e-14) // 1./(CONS2*pow(25.e-6,3.0))`
- `p3_autoconversion_impl.hpp:35`: `pow(qc_incld,sp(2.47))*pow(nc_incld*sp(1.e-6)*rho,sp(-1.79))`
- `p3_cloud_rain_acc_impl.hpp:38`: `sp(p3_k_accretion) * pow(qc_incld * qr_incld, sp(1.15))`

The new code refactored the accretion from a single `pow(qc·qr, 1.15)` into two separate
exponents `qc^1.15 * qr^1.15`, but this is mathematically identical.

To change any of these via `atmchange`, use `physics::mac_aero_mic::p3::<name>`, e.g.:
```bash
./atmchange physics::mac_aero_mic::p3::autoconversion_qc_exponent=2.47
```

### Finding 4 — SHOC `lambda_high`

| | RCE01 | RCE02 |
|---|---|---|
| `lambda_high` | `0.04` | `0.08` |

Confirmed as expected from PR #6797. This was already tested in RCE03 (old
code + `lambda_high=0.08`) and did **not** close the PW gap, ruling it out as
the primary cause.

### Finding 5 — Additional RCE02-only P3 options

RCE02 carries new flags absent from RCE01, all currently at their defaults:

```yaml
use_hetfrz_classnuc: false       # heterogeneous freezing (PR #6947)
set_cld_frac_l_to_one: false     # subgrid cloud fraction override (PR #6849)
set_cld_frac_r_to_one: false
set_cld_frac_i_to_one: false
use_separate_ice_liq_frac: false # separate liq/ice cldfrac (PR #6966)
extra_p3_diags: false
do_ice_production: true
```

All default to the behavior most compatible with RCE01 (subgrid fractions
active, single cldfrac), so these are not the cause of the PW difference in
the default RCE02 setup — but `set_cld_frac_r_to_one=true` remains a useful
sensitivity test for popcorn convection (see the earlier section on this).

### Finding 6 — `fixed_total_solar_irradiance` (RCE02 only) ⚠️

RCE02 sets:
```yaml
fixed_total_solar_irradiance: 551.58
```

**This parameter does not exist in the old code (v3.0.2).** A search of
`model/E3SM/components/eamxx/` confirms zero occurrences of
`fixed_total_solar_irradiance`. Instead, the old code reads `tsi_default` from
the RRTMGP SW coefficients file and scales it by an orbital eccentricity factor
(`eccf`) computed from the model clock:

- `tsi_default` in `rrtmgp-data-sw-g112-210809.nc` = **1360.858 W/m²**
- `eccf` ≈ 1 on annual average, varying ±3.3% with Earth-Sun distance

So the effective TSI differs dramatically between the two runs:

| Run | Solar irradiance | How determined |
|-----|-----------------|---------------|
| RCE01 (old code) | **~1360.9 W/m²** (full TSI × eccf) | `tsi_default` from RRTMGP file, orbit-based scaling |
| RCE02 (new code) | **551.58 W/m²** (fixed) | `fixed_total_solar_irradiance` in YAML |

551.58 / 1360.86 = **40.5%** of the full solar constant. This is a **large difference
in net shortwave forcing** that directly affects the radiative-convective equilibrium
temperature and moisture profile. Lower insolation → lower equilibrium SST-relative
temperature aloft → different lapse rate → different PW at equilibrium.

The value 551.58 W/m² is appropriate for an idealized RCE with a fixed solar zenith
angle: it represents the time-mean shortwave flux at some zenith angle (here approximately
cos⁻¹(551.58/1360.86) ≈ 66° or a geometry-weighted mean). In the old code, since
`Fixed Solar Zenith Angle = -9999` (disabled), the zenith angle varies realistically
with the simulated time of day and year, and the full TSI ~1361 W/m² is used — which
means the instantaneous solar forcing can range from 0 (night) to ~1361 W/m² (overhead),
with a domain-average that depends on the diurnal cycle and latitude.

**This is likely a major contributor to the PW difference** and should be investigated
before the CCN→Nc change. The two runs are not in the same radiative equilibrium regime.

### Recommended investigation order

1. **Fixed solar irradiance vs. full TSI** (Finding 6) — **highest priority ⚠️**: RCE01
   uses the full solar constant (~1361 W/m²) with a diurnal/seasonal cycle; RCE02 uses a
   fixed 551.58 W/m² (40.5% of the full TSI). These two runs are in fundamentally different
   radiative forcing regimes. To isolate the microphysics effects, first make the solar
   forcing consistent between the two runs. Either:
   - Add `fixed_total_solar_irradiance` to RCE01 (not possible — the parameter doesn't
     exist in v3.0.2), OR
   - Set `fixed_total_solar_irradiance` to the full TSI in RCE02 and compare with
     orbit-based insolation, OR
   - Accept that the solar forcing difference dominates and factor it out before
     attributing PW changes to microphysics.

2. **CCN→Nc activation change** (Finding 2): the old value is `p3_spa_to_nc: 1.0`
   in the RCE01 yaml — a simple linear multiplier, not a hardcoded constant.
   Setting `spa_ccn_to_nc_factor=1.0` and `spa_ccn_to_nc_exponent=1.0` in RCE02
   exactly reproduces `Nc = 1.0 × CCN`:
   ```bash
   ./atmchange physics::mac_aero_mic::p3::spa_ccn_to_nc_factor=1.0
   ./atmchange physics::mac_aero_mic::p3::spa_ccn_to_nc_exponent=1.0
   ```
   This directly isolates whether the CCN→Nc functional form change explains
   the PW shift.

3. ~~**Autoconversion exponents** (Finding 3)~~: verified — all compile-time constants
   in v3.0.2 are identical to the new XML defaults. This is **not a source** of the PW difference.

---

## Is large-scale subsidence (`iop_dosubsidence=true`) appropriate for RCE?

**Short answer: for a doubly-periodic domain, no — it is physically
inconsistent and should generally be disabled.**

### Why subsidence is inconsistent with a doubly-periodic domain

A doubly-periodic domain with uniform SST is a **closed system** in the
horizontal. By continuity, the domain-mean vertical mass flux must be zero at
every level:

$$\langle \omega \rangle_\text{domain} = 0$$

Prescribing a non-zero large-scale subsidence velocity $\omega_\text{ls} < 0$
(downwelling) from the IOP file adds a net downward flux with no compensating
upwelling anywhere in the domain, violating mass conservation. The model works
around this by applying the subsidence as a forcing tendency rather than
modifying the divergence field, but the physical inconsistency remains: the
prescribed drying from subsidence is uncompensated.

### What the IOP file provides

`RCE_300K_iopfile_4scam.nc` was designed for **SCAM** (Single-Column
Atmospheric Model) and SCAM-style DP experiments, where a single column
represents a region embedded in a larger-scale circulation. In that context,
the prescribed subsidence represents the remote compensating ascent (Walker
cell, Hadley cell) that balances the column's convection — physically
meaningful for a single column but not for a domain that should self-determine
its own circulation.

### Effect of `iop_dosubsidence=true` on RCE

- Imposes a systematic drying (subsiding air is warmer and drier) that biases
  PW downward regardless of the model's convective state.
- Suppresses self-organization: prescribed subsidence dries the environment
  uniformly, competing with the radiative-convective feedback that would
  naturally produce moist/dry column contrasts through self-aggregation.
- Makes it harder to diagnose true model behavior — any PW differences between
  code versions are convolved with the sensitivity of subsidence drying to
  process order (see Finding 1 above).

### Recommendation

For a clean idealized RCE study:
```bash
./atmchange iop_dosubsidence=false
```

or equivalently, in `namelist_scream.xml`:
```xml
<iop_dosubsidence>false</iop_dosubsidence>
```

With subsidence off, the domain finds its own thermodynamic equilibrium and
self-aggregation evolves freely. This is the setup used in most CRM and SAM
RCE studies that serve as the reference for EAMxx comparisons.

If the goal is to mimic a specific large-scale tropical environment (e.g., a
particular SST regime with known subsidence), keep `iop_dosubsidence=true` but
be aware that the prescribed forcing will dominate the moisture budget and any
version sensitivity in PW is likely amplified by the subsidence sensitivity.
