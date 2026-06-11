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
| RCE02 (new code) | **551.58 W/m²** (fixed) | `fixed_total_solar_irradiance` in YAML (same as RCEMIP)|

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

---

## RCEMIP Radiation Parameter Compliance

This section checks whether the EAMxx DP-SCREAM RCE configuration (`FRCE-SCREAMv1-DP` compset)
matches the radiation parameters specified by the RCE Model Intercomparison Project (RCEMIP)
protocol (Wing et al. 2018, *Geosci. Model Dev.*, 11, 793–813,
https://gmd.copernicus.org/articles/11/793/2018/).

**Source files checked:**
- `components/eamxx/cime_config/namelist_defaults_eamxx.xml` (lines 505–534)
- `components/eamxx/src/physics/rrtmgp/eamxx_rrtmgp_process_interface.cpp` (lines 477–484)
- `components/eamxx/cime_config/usermods_dirs/rcemip/user_nl_cpl`
- Actual case namelist: `/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE02_dx3km_gpu/case_scripts/namelist_scream.xml`

### Parameters that match RCEMIP ✅

| Parameter | RCEMIP value | EAMxx (RCE case) | Where set |
|---|---|---|---|
| CO2 concentration | 348 ppmv | **348.0e-6** | `<co2vmr COMPSET=".*SCREAM%RCE.*">348.0e-6</co2vmr>` in `namelist_defaults_eamxx.xml` |
| CH4 concentration | 1650 ppbv | **1650.e-9** | `<ch4vmr COMPSET=".*SCREAM%RCE.*">1650.e-9</ch4vmr>` |
| N2O concentration | 306 ppbv | **306.0e-9** | `<n2ovmr COMPSET=".*SCREAM%RCE.*">306.0e-9</n2ovmr>` |
| CFC11 concentration | 0 | **0.0** | `<f11vmr COMPSET=".*SCREAM%RCE.*">0.0</f11vmr>` |
| CFC12 concentration | 0 | **0.0** | `<f12vmr COMPSET=".*SCREAM%RCE.*">0.0</f12vmr>` |
| CFC22 concentration | 0 | **effectively 0** | Not in `active_gases` list; no `f22vmr` parameter exists in EAMxx |
| CCL4 concentration | 0 | **effectively 0** | Not in `active_gases` list; not modeled |
| Solar constant | 551.58 W m⁻² | **551.58** | `<fixed_total_solar_irradiance COMPSET=".*SCREAM%RCE.*">551.58</fixed_total_solar_irradiance>` |
| Zenith angle | 42.05° | **42.05** | `constant_zenith_deg = 42.05` in `usermods_dirs/rcemip/user_nl_cpl` |
| Surface albedo (direct & diffuse) | 0.07 | **0.07** | `seq_flux_mct_albdif = 0.07`, `seq_flux_mct_albdir = 0.07` in `usermods_dirs/rcemip/user_nl_cpl` |

The compset long name `2000_SCREAM%RCE_SLND_SICE_DOCN%AQPCONST_SROF_SGLC_SWAV_SIAC_SESP%DP-EAMxx`
contains `SCREAM%RCE`, which activates all the conditional `COMPSET=".*SCREAM%RCE.*"` overrides in
`namelist_defaults_eamxx.xml`. The rcemip usermod (`usermods_dirs/rcemip/`) is applied at case
creation and provides the orbital and surface boundary conditions.

### Parameter that does NOT follow RCEMIP ⚠️

| Parameter | RCEMIP specification | EAMxx (RCE case) |
|---|---|---|
| O3 profile (g1, g2, g3) | Analytic formula $O_3(p) = g_1\, p^{g_2}\, e^{-p/g_3}$ with g1 = 3.6478 ppmv hPa⁻ᵍ², g2 = 0.83209, g3 = 11.3515 hPa | **Not implemented.** Ozone is read from the global IC file `screami_ne30np4L128_20221004.nc` (2010 F2010 climatology) and held fixed throughout the run. |

The RCEMIP analytic ozone profile parameters (g1, g2, g3) do not appear anywhere in the EAMxx
codebase. The `o3_volume_mix_ratio` field is initialized from the standard ne30np4 global IC file
at the nearest equatorial column (lat ≈ 0°, lon ≈ 0°) and is not modified during the simulation.
This profile differs from the RCEMIP prescription, which specifies a smooth analytical function
of pressure designed to represent a tropical mean ozone climatology. The two profiles may agree
well in the lower-to-mid troposphere but can differ in the stratosphere, which affects longwave
cooling near the model top.

---

## RCEMIP Geophysical Constants Compliance

This section checks the geophysical/thermodynamic constants used by EAMxx against
the values prescribed by the RCEMIP protocol (Wing et al. 2018, Table 1).

**Source files checked:**
- `components/eamxx/src/physics/share/physics_constants.hpp` — primary C++ constants for P3, SHOC, RRTMGP
- `share/util/shr_const_mod.F90` — shared E3SM constants (used by HOMME dynamics in coupled mode)
- `components/homme/src/share/physical_constants.F90` — HOMME dynamics constants (standalone values, overridden by CAM/shr values in coupled runs)

### Earth rotation rate and Coriolis parameter

| Parameter | RCEMIP | EAMxx | Notes |
|---|---|---|---|
| Earth rotation rate Ω | 0 | **7.292×10⁻⁵ rad/s** (`SHR_CONST_OMEGA` = 2π/86164 s) | Not set to zero; see discussion below |
| Coriolis parameter f | 0 | **0 (effectively)** | f = 2Ω sin(lat) = 2×7.292×10⁻⁵×sin(0°) = **0** at target lat=0° |

The code does **not** set Ω = 0 for the RCE case. Instead, f = 0 is achieved
naturally because the doubly-periodic domain is centred on the equator
(`target_latitude = 0.0`). In HOMME's `cube_mod.F90`, the Coriolis parameter at
each GLL point is initialised as:
```fortran
elem%fcor(i,j) = 2.0D0 * omega * SIN(elem%spherep(i,j)%lat)
```
Since all points in the domain project to lat ≈ 0, `fcor = 0` throughout.
Additionally, the `iop_coriolis` flag (which controls Coriolis-based geostrophic
nudging in the IOP-forcing process) is set to `false` for the RCE case.
The RCEMIP intent (f = 0 everywhere) is therefore satisfied, even though Ω itself
is non-zero in the code.

### Thermodynamic and geometric constants

| Parameter | RCEMIP | EAMxx value | Source | Match? |
|---|---|---|---|---|
| Mean Earth radius R_E | 6371.0 km | **6371.22 km** | `SHR_CONST_REARTH = 6.37122e6 m` | ≈ (+0.22 km, 0.003%) |
| Surface gravity g | 9.79764 m s⁻² | **9.80616 m s⁻²** | `SHR_CONST_G = 9.80616` / `physics_constants.hpp: gravit = 9.80616` | ✗ (+0.00852, **+0.087%**) |
| Dry-air gas constant R_d | 287.04 J kg⁻¹ K⁻¹ | **287.042 J kg⁻¹ K⁻¹** | `SHR_CONST_RDAIR` = 8314.47/28.966; `Rair = 287.042` | ≈ (+0.002, 0.001%) |
| Dry-air specific heat C_pd | 1004.64 J kg⁻¹ K⁻¹ | **1004.64 J kg⁻¹ K⁻¹** | `SHR_CONST_CPDAIR = 1.00464e3`; `Cpair = 1004.64` | ✅ exact |
| Water vapor gas constant R_v | 461.50 J kg⁻¹ K⁻¹ | **461.505 J kg⁻¹ K⁻¹** | `SHR_CONST_RWV` = 8314.47/18.016; `RH2O = 461.505` | ≈ (+0.005, 0.001%) |
| Water vapor specific heat C_pv | 1846.0 J kg⁻¹ K⁻¹ | **1810.0 J kg⁻¹ K⁻¹** | `SHR_CONST_CPWV = 1.810e3` | ✗ (−36, **−1.95%**) |
| Latent heat of vaporization L_v0 | 2.501×10⁶ J kg⁻¹ | **2.501×10⁶ J kg⁻¹** | `SHR_CONST_LATVAP = 2.501e6`; `LatVap = 2501000.0` | ✅ exact |
| Latent heat of fusion L_f0 | 3.337×10⁵ J kg⁻¹ | **3.337×10⁵ J kg⁻¹** | `SHR_CONST_LATICE = 3.337e5`; `LatIce = 333700.0` | ✅ exact |
| Latent heat of sublimation L_s0 | 2.834×10⁶ J kg⁻¹ | **2.8347×10⁶ J kg⁻¹** | `SHR_CONST_LATSUB = LATICE + LATVAP = 2834700` | ≈ (+700, 0.025%; within RCEMIP's 4-sig-fig rounding) |

### Summary

**Constants that match RCEMIP (exact or negligible difference):**
- C_pd = 1004.64 J/kg/K ✅
- L_v0 = 2.501×10⁶ J/kg ✅
- L_f0 = 3.337×10⁵ J/kg ✅
- L_s0 = 2.8347×10⁶ J/kg ≈ 2.834×10⁶ (within rounding) ✅
- R_d = 287.042 vs 287.04 (0.001% — negligible) ≈
- R_v = 461.505 vs 461.50 (0.001% — negligible) ≈
- Coriolis f = 0 ✅ (achieved via equatorial latitude, not by setting Ω = 0)
- R_E = 6371.22 vs 6371.0 km (0.003% — negligible) ≈

**Constants that differ from RCEMIP:**
- **g = 9.80616 vs 9.79764 m/s²** — difference of +0.087%. EAMxx uses the standard
  WMO/IAU mean surface gravity (9.80616 m/s²), while RCEMIP specifies a slightly lower
  value (closer to the tropical mean). This will affect the pressure-height relationship
  throughout the column and is the most consequential constant deviation.
- **C_pv = 1810 vs 1846 J/kg/K** — difference of −1.95%. The shared E3SM constant
  `SHR_CONST_CPWV = 1.810e3 J/kg/K` is a standard meteorological value; RCEMIP
  uses a slightly higher value. Note that `C_pv` is **not** directly referenced in
  EAMxx's C++ physics (it is absent from `physics_constants.hpp`); it appears only in
  the Fortran ZM deep-convection bridge (`zm_eamxx_bridge_physconst.F90`). The P3 and
  SHOC microphysics/turbulence schemes do not use C_pv explicitly, so the practical
  impact is limited to ZM, which is not active in the standard RCE compset.

### Source-code evidence

```
# Gravity and Earth radius (coupled/CAM mode):
share/util/shr_const_mod.F90:
  SHR_CONST_G      = 9.80616      ! m/s²
  SHR_CONST_REARTH = 6.37122e6    ! m

# Gravity and latent heats (EAMxx C++ physics):
components/eamxx/src/physics/share/physics_constants.hpp:
  gravit  = 9.80616
  LatVap  = 2501000.0    (= 2.501e6)
  LatIce  = 333700.0     (= 3.337e5)
  Cpair   = 1004.64
  Rair    = 287.042
  RH2O    = 461.505

# Water vapor Cpv (Fortran shared):
share/util/shr_const_mod.F90:
  SHR_CONST_CPWV   = 1.810e3      ! J/kg/K  (RCEMIP: 1846)

# Earth rotation rate (used in fcor = 2*omega*sin(lat)):
share/util/shr_const_mod.F90:
  SHR_CONST_OMEGA  = 2π / 86164.0 = 7.292e-5 rad/s
components/homme/src/share/physical_constants.F90:
  omega0 = 7.292e-5                ! s⁻¹
  g      = 9.80616                 ! m/s²  (standalone; overridden by shr in coupled mode)
  Rwater_vapor = 461.50            ! J/kg/K (standalone)
  Cpwater_vapor = 1870.0           ! J/kg/K (standalone; irrelevant in coupled mode)
```

---

## RCEMIP Aerosol Compliance

The RCEMIP protocol states:
> "Aerosol effects are to be ignored by zeroing the aerosol concentrations. In some GCMs,
> aerosol effects may be ignored by excluding aerosol from the radiative transfer calculation
> and fixing the cloud droplet number concentration (we suggest N_c = 1.0×10⁸ m⁻³) and
> ice crystal number concentration (we suggest N_i = 1.0×10⁵ m⁻³) within the microphysics
> parameterizations."

**EAMxx has a dedicated `noAero` mechanism** (compset suffix `SCREAM.*noAero`) that removes
SPA from the physics list and disables aerosol radiative effects. The standard RCE compset
`SCREAM%RCE` does **not** invoke this mechanism.

### Aerosol treatment in the actual case (RCE02_dx3km_gpu)

The generated `namelist_scream.xml` shows:

```xml
<mac_aero_mic>
  <atm_procs_list>tms,shoc,cld_fraction,spa,p3</atm_procs_list>
  <spa>
    <spa_data_file>.../spa_file_unified_and_complete_ne30pg2_20240111.nc</spa_data_file>
  </spa>
  <do_prescribed_ccn>true</do_prescribed_ccn>
  <do_predict_nc>true</do_predict_nc>
  <spa_ccn_to_nc_factor>2000.0</spa_ccn_to_nc_factor>
  <spa_ccn_to_nc_exponent>0.55</spa_ccn_to_nc_exponent>
</mac_aero_mic>
<do_aerosol_rad>true</do_aerosol_rad>
```

### 1. Aerosol effects in radiative transfer

| RCEMIP | EAMxx | Compliant? |
|---|---|---|
| Exclude aerosols from radiation (zero concentrations or bypass) | `do_aerosol_rad = true`; SPA active with ne30pg2 climatology | ❌ |

The Simple Prescribed Aerosol (SPA) process reads from `spa_file_unified_and_complete_ne30pg2_20240111.nc`
and provides five fields to RRTMGP each timestep:
- `nccn` — cloud condensation nuclei number concentration
- `aero_tau_sw` — SW aerosol optical depth (14 bands)
- `aero_ssa_sw` — SW single-scattering albedo
- `aero_g_sw` — SW asymmetry factor
- `aero_tau_lw` — LW aerosol optical depth (16 bands)

Because `do_aerosol_rad = true`, these optical properties enter the SW and LW radiative transfer
calculations directly in RRTMGP. This is non-compliant with RCEMIP, which requires aerosol
effects to be absent from radiation.

The `noAero` compsets available in EAMxx (`SCREAM.*noAero`) set `do_aerosol_rad = false` and
remove SPA from the physics process list. The RCEMIP compset `SCREAM%RCE` does not inherit
these settings.

### 2. Cloud droplet number concentration N_c

| RCEMIP | EAMxx | Compliant? |
|---|---|---|
| Fixed N_c = 1.0×10⁸ m⁻³ (suggested) | Prognostic, SPA-driven: N_c = max(N_c, 2000 × CCN^0.55) | ❌ |

With `do_prescribed_CCN = true` and `do_predict_nc = true`, the P3 code (in
`p3_main_impl_part1.hpp`) sets:
```cpp
// From p3_main_impl_part1.hpp:
// Nc = max ( Nc , spa_ccn_to_nc_factor * (nccn_prescribed / inv_cld_frac_l) ^ spa_ccn_to_nc_exponent )
auto nccn_scaled = nccn_prescribed(k) / inv_cld_frac_l(k);
nccn_scaled = pow(nccn_scaled, spa_ccn_to_nc_exponent);  // ^ 0.55
nc(k).set(not_drymass, max(nc(k), spa_ccn_to_nc_factor * nccn_scaled));  // × 2000
```

N_c is therefore a spatially varying, aerosol-climatology-driven quantity — not a fixed constant.

If both flags were false (no SPA, no prediction), the fallback would be the constant
`NCCNST = 200×10⁶ m⁻³` (`physics_constants.hpp` line 82), but this also differs from
RCEMIP's suggested 1.0×10⁸ m⁻³.

### 3. Ice crystal number concentration N_i

| RCEMIP | EAMxx | Compliant? |
|---|---|---|
| Fixed N_i = 1.0×10⁵ m⁻³ (suggested) | Prognostic via Cooper formula; hard cap `max_total_ni = 740×10³ m⁻³` | ❌ |

Ice nucleation in P3 (`p3_ice_nucleation_impl.hpp`) selects its branch based on
`do_log = (!do_predict_nc || do_prescribed_CCN)`. For the RCE case:
```
do_log = (!true || true) = true
```
This activates the Cooper-based nucleation formula: `ni_activated` is the temperature-dependent
DeMott/Cooper activated fraction, and `ni_nucleat_tend = max(0, (ni_activated - ni) / dt)`.
The total ice number is capped by `max_total_ni = 740×10³ m⁻³` (namelist default), which is
much larger than RCEMIP's suggested 1.0×10⁵ m⁻³.

Note: the deposition nucleation branch (used when `do_predict_nc=true AND do_prescribed_CCN=false`)
does enforce an internal cap of `1.0×10⁵/ρ` (#/kg), which converts to ~1.0×10⁵ m⁻³ at ρ ≈ 1 kg/m³ —
coinciding with the RCEMIP suggestion — but this branch is NOT reached in the RCE configuration.

### Summary

| Component | RCEMIP requirement | EAMxx RCE setting | Match? |
|---|---|---|---|
| Aerosol optical effects in radiation | Off (zero/excluded) | **On** (`do_aerosol_rad = true`) | ❌ |
| SPA aerosol process | Absent or zero | **Active**, ne30pg2 climatology | ❌ |
| N_c cloud droplet number | Fixed 1.0×10⁸ m⁻³ | **Prognostic**, SPA-driven via 2000×CCN^0.55 | ❌ |
| N_i ice crystal number | Fixed 1.0×10⁵ m⁻³ | **Prognostic**, Cooper formula, cap 740×10³ m⁻³ | ❌ |
| Heterogeneous freezing (aerosol-based) | Off | `use_hetfrz_classnuc = false` | ✅ |

EAMxx's RCE configuration does **not** follow the RCEMIP aerosol protocol.
A compliant configuration would require switching to the `noAero`-style setup:
- Set `do_aerosol_rad = false`
- Remove `spa` from the physics process list (or use a zero-aerosol SPA file)
- Set `do_prescribed_CCN = false` and `do_predict_nc = false` to activate the
  fallback constant `NCCNST` (currently 200×10⁶ m⁻³; the RCEMIP-recommended
  1.0×10⁸ m⁻³ could be set via `atmchange` if desired)

---

## noAero Configuration: RCE09_dx3km_gpu

`run_RCE09_dx3km_gpu.sh` implements the `noAero`-style setup to match RCEMIP aerosol compliance.
The following `atmchange` calls were added at the end of the `edit_atmconf` block:

```bash
# noAero configuration: mirrors the SCREAM.*noAero compsets for RCEMIP aerosol compliance.
# 1. Remove 'spa' from the mac_aero_mic process list so no aerosol climatology is read.
./atmchange physics::mac_aero_mic::atm_procs_list=tms,shoc,cld_fraction,p3
# 2. Disable aerosol optical properties in RRTMGP radiative transfer.
./atmchange physics::rrtmgp::do_aerosol_rad=false
# 3. Switch P3 from SPA-driven prognostic N_c to the fallback constant NCCNST.
./atmchange physics::mac_aero_mic::p3::do_prescribed_ccn=false
./atmchange physics::mac_aero_mic::p3::do_predict_nc=false
# 4. NCCNST is a compile-time constant in physics_constants.hpp (200e6 m^-3). 
#    It is NOT a runtime parameter accessible via atmchange.
#    To change it, the source code file eamxx/src/physics/share/physics_constants.hpp 
#    was modified directly on the ksa/nersc branch in the source clone.
```

| `atmchange` call | Effect |
|---|---|
| `physics::mac_aero_mic::atm_procs_list=tms,shoc,cld_fraction,p3` | Removes `spa` from the process list — no aerosol climatology file is read |
| `physics::rrtmgp::do_aerosol_rad=false` | Passes zero aerosol optical properties to RRTMGP (SW+LW) |
| `physics::mac_aero_mic::p3::do_prescribed_ccn=false` | Stops P3 from pulling CCN from SPA |
| `physics::mac_aero_mic::p3::do_predict_nc=false` | Deactivates prognostic N_c; falls back to constant `NCCNST` |

Because `spa` is removed from `atm_procs_list`, no valid `spa_data_file` is needed — the `spa`
parameter block is ignored entirely. The `compute_tendencies` calls for `shoc` and `p3` in the
`edit_output` block are unaffected.

---

## N_i Ice Crystal Number: RCEMIP Compliance and `max_total_ni`

The RCEMIP protocol suggests fixing N_i = 1.0×10⁵ m⁻³. Unlike N_c (which falls back to the
compile-time constant `NCCNST` when `do_predict_nc=false`), ice crystal number in the noAero
configuration is controlled by **two separate mechanisms**.

### Ice nucleation branch active in noAero

In the noAero setup (`do_predict_nc=false`, `do_prescribed_ccn=false`), the logical
`do_log = (!do_predict_nc || do_prescribed_CCN) = true`, which activates the **deposition
nucleation branch** in `p3_ice_nucleation_impl.hpp`:

```cpp
dum = 0.005 * exp(deposition_nucleation_exponent * (Tmelt - T)) * 1.0e3 * inv_rho;
dum = min(dum, 1.0e5 * inv_rho);   // hard-coded nucleation cap ≈ 1.0e5 m⁻³
N_nuc = max(0, (dum - ni) * inv_dt);
```

The hard-coded `min(dum, 1.0e5 * inv_rho)` cap means nucleation tendencies are already limited
to ~1.0×10⁵ m⁻³ at ρ ≈ 1 kg/m³ — coincidentally matching the RCEMIP suggestion.

### `max_total_ni` — the broader safety limiter

`max_total_ni` is a separate, stronger cap applied by `impose_max_total_ni` **throughout the
microphysics loop**, capping the total in-cloud ice number from *all* sources (nucleation,
heterogeneous freezing, rime splintering, aggregation). It is a member of `P3Runtime` and is
**accessible via `atmchange`**:

| Parameter | Default | Source |
|---|---|---|
| `max_total_ni` | **740.0×10³ m⁻³** | `P3Runtime` struct, `p3_functions.hpp` line 113 |

The default 740×10³ m⁻³ is ~7× larger than the RCEMIP-recommended 1.0×10⁵ m⁻³. Without
changing it, secondary ice production processes could build N_i well above the RCEMIP target.

### Fix applied in `run_RCE09_dx3km_gpu.sh`

The following `atmchange` call was added (step 5 of the noAero block):

```bash
./atmchange physics::mac_aero_mic::p3::max_total_ni=1.0e5
```

This sets the overall in-cloud ice number cap to 1.0×10⁵ m⁻³, consistent with RCEMIP.
The nucleation branch cap and `max_total_ni` are now both at 1.0×10⁵ m⁻³.

### Complete updated noAero block

```bash
# noAero configuration: mirrors the SCREAM.*noAero compsets for RCEMIP aerosol compliance.
# 1. Remove 'spa' from the mac_aero_mic process list so no aerosol climatology is read.
./atmchange physics::mac_aero_mic::atm_procs_list=tms,shoc,cld_fraction,p3
# 2. Disable aerosol optical properties in RRTMGP radiative transfer.
./atmchange physics::rrtmgp::do_aerosol_rad=false
# 3. Switch P3 from SPA-driven prognostic N_c to the fallback constant NCCNST.
./atmchange physics::mac_aero_mic::p3::do_prescribed_ccn=false
./atmchange physics::mac_aero_mic::p3::do_predict_nc=false
# 4. NCCNST is a compile-time constant in physics_constants.hpp (200e6 m^-3).
#    To change it to the RCEMIP-recommended 1.0e8 m^-3, the file 
#    eamxx/src/physics/share/physics_constants.hpp was modified directly 
#    on the ksa/nersc branch in the source clone (/global/cfs/cdirs/wcm_code/ksa/E3SM/code_tests/8426cb31c7_clone)
#    because eamxx does not support the SourceMods approach.
# 5. Cap total in-cloud ice number at the RCEMIP-recommended 1.0e5 m^-3.
#    The deposition nucleation branch (active when do_predict_nc=false) already has a
#    hard-coded nucleation cap of 1.0e5*inv_rho, but max_total_ni is the broader limiter
#    applied throughout the microphysics loop (default is 740e3 m^-3).
./atmchange physics::mac_aero_mic::p3::max_total_ni=1.0e5
```

### Updated compliance summary

| Component | RCEMIP requirement | RCE09 setting | Match? |
|---|---|---|---|
| Aerosol optical effects in radiation | Off | `do_aerosol_rad=false` | ✅ |
| SPA aerosol process | Absent | Removed from `atm_procs_list` | ✅ |
| N_c cloud droplet number | Fixed 1.0×10⁸ m⁻³ | `NCCNST=1.0e8` via source branch `ksa/nersc` | ✅ |
| N_i ice crystal number | Fixed 1.0×10⁵ m⁻³ | Deposition nucleation cap ~1.0×10⁵ m⁻³ (hard-coded) + `max_total_ni=1.0e5` | ✅ |
| Heterogeneous freezing | Off | `use_hetfrz_classnuc=false` (default) | ✅ |

---

## Verifying N_c and N_i in Model Output

Both `nc` (cloud droplet number) and `ni` (ice crystal number) are **already included** in
the configured output stream `scream_test2_output_inst_1hour.yaml` under the `# P3` block.
No changes to the yaml files or run script are needed to access them.

### Output field names and units

| Variable | Field name | Units | Output stream |
|---|---|---|---|
| Cloud droplet number | **`nc`** | #/kg | `scream_test2_output_inst_1hour.yaml` |
| Ice crystal number | **`ni`** | #/kg | `scream_test2_output_inst_1hour.yaml` |
| Rain drop number | `nr` | #/kg | `scream_test2_output_inst_1hour.yaml` |
| Liquid effective radius | `eff_radius_qc` | µm | Commented out; add if needed |
| Ice effective radius | `eff_radius_qi` | µm | Commented out; add if needed |

Both fields are in **mixing ratio units** (#/kg). To convert to number concentration (#/m³)
for comparison with RCEMIP target values, multiply by air density ρ:

$$N_c \ [\text{m}^{-3}] = \texttt{nc} \times \rho, \qquad \rho = \frac{p}{R_d T}$$

At typical lower-tropospheric conditions (ρ ≈ 1 kg/m³), `nc` [#/kg] ≈ N_c [#/m³] numerically.

### What to look for

**For N_c** — with `do_predict_nc=false` and `NCCNST=1.0e8 m⁻³` set via source branch `ksa/nersc`,
`nc` should be spatially uniform wherever cloud liquid is present (`qc > 0`), equal to
`NCCNST × inv_rho`. Any spatial variability or values inconsistent with 1.0×10⁸ m⁻³ × inv_rho
would indicate the prognostic path is still active.

**For N_i** — with `max_total_ni=1.0e5 m⁻³`, `ni × ρ` should never exceed 1.0×10⁵ m⁻³
anywhere in the domain. Check the domain maximum.

## Why N_i Cannot Be Fixed Like N_c in P3

### Why fixing N_c works

In the 1-moment P3 code (`module_mp_p3.f95`, line 1824), `nc` is literally overwritten at every time step:

```fortran
if (.not.(log_predictNc)) then
    nc(i,k) = nccnst * inv_rho(i,k)   ! reset every time step
endif
```

This is physically defensible because:

1. Cloud droplets are activated from CCN at cloud base and the CCN spectrum is approximately fixed for a given environment.
2. Droplets don't multiply — coalescence removes drops but doesn't create them; evaporation at grid-cell scale zeroes N_c together with q_c anyway.
3. The only source is activation, which is well-approximated by a constant for bulk schemes without interactive aerosols.

### Why the same approach fails for N_i

Ice number evolves through at least **six distinct processes** in P3, all updating `nitot` within a single call to `p3_main` (`module_mp_p3.f95`, lines 3261–3263):

```fortran
nitot(i,k,iice) = nitot(i,k,iice) + (ninuc(iice)   ! + deposition/cond-freezing nucleation
                                    - nimlt(iice)   ! - melting (ice→rain)
                                    - nisub(iice)   ! - sublimation
                                    - nislf(iice)   ! - self-aggregation
                                    + nrhetc(iice)  ! + heterogeneous freezing of rain
                                    + nrheti(iice)  ! + (rain)
                                    + nchetc(iice)  ! + heterogeneous freezing of cloud
                                    + ncheti(iice)  ! + (cloud)
                                    + nimul(iice)   ! + Hallett-Mossop rime splintering
                                    ) * dt
```

| Process | What it does to N_i | Why resetting fails |
|---|---|---|
| **Deposition/condensation-freezing nucleation** (`ninuc`) | Temperature-dependent: Cooper formula gives ~10² m⁻³ at −10 °C but ~10⁶ m⁻³ at −40 °C | Resetting would either starve nucleation at cold T or overseed at warm T |
| **Hallett-Mossop rime splintering** (`nimul`, line 2577) | Can multiply N_i by ×100–1000 in the −3 to −8 °C zone | Secondary production is a burst — resetting destroys the causal chain |
| **Self-aggregation** (`nislf`, line 2317) | Reduces N_i as crystals stick together; rate ∝ N_i² | Resetting upward makes aggregation unrealistically fast; downward misrepresents large-crystal populations |
| **Melting** (`nimlt`, line 2340) | N_i tendency proportional to q_imlt/q_itot — particle size matters | Resetting conflates number with mass ratio |
| **Sublimation** (`nisub`) | Removes the smallest crystals preferentially | Has memory: large anvil crystals persist long after convection ends |
| **Heterogeneous freezing** (`nrhetc/i`, `nchetc/i`) | Freezing of rain/cloud drops creates ice; rate depends on liquid number and temperature | Sources are unrelated to the ice number itself |

### The deeper physical reason: ice has "memory" but droplets don't

Cloud droplets at a given grid point are essentially **locally produced** (activated from below) and **locally consumed** (evaporate when q_c → 0). Their number returns to a predictable value whenever they reform.

Ice crystals, by contrast, are **advected** from their nucleation location, **grow for hours** through deposition in the anvil, **sediment** downward through layers, and can **persist long after the convection that created them is gone**. Fixing N_i would destroy this history: a spreading cirrus anvil with 10² m⁻³ large crystals would be incorrectly "corrected" to 10⁵ m⁻³ tiny ones every timestep, making the ice radiative properties and precipitation completely wrong.

### What `max_total_ni` does instead (the correct approach)

Rather than fixing N_i (which would break the physics), `impose_max_total_Ni` (`module_mp_p3.f95`, lines 6288–6310) **caps** the total ice number across all categories by proportionally scaling down each category when the sum exceeds the limit:

```fortran
dum = max_total_Ni * inv_rho_local / sum(nitot_local(:))
! if sum > max, scale all categories by dum < 1
```

This limits unrealistic explosive nucleation events (e.g., homogeneous freezing producing 10⁷ m⁻³) without forcing a fixed value — all the *relative* evolution (aggregation, melting, advection) continues physically. The RCEMIP value of 1×10⁵ m⁻³ is appropriate as a **cap** (maximum upper bound), not a baseline reset, which is why it is the approach used in both PINACLES and EAMxx.

---

### Quick verification commands

```bash
# domain-mean nc (should be ~1e8 * inv_rho; at surface ρ≈1.2, nc_mean ≈ 8.3e7 kg⁻¹)
ncap2 -s 'nc_dommean=nc.avg($ncol,$lev)' -v output.nc check_nc.nc

# domain max ni (should not exceed ~1e5 * inv_rho ≈ 8.3e4 kg⁻¹ at surface)
ncap2 -s 'ni_max=ni.max($ncol,$lev)' -v output.nc check_ni.nc

# or with nco directly on first timestep:
ncks -v nc,ni -d time,0 output.nc | head -40
```

For a more complete check, compute column-mean or level-mean values using Python/xarray:

```python
import xarray as xr
ds = xr.open_dataset("output.nc")
rho = ds.p_mid / (287.042 * ds.T_mid)   # dry air density [kg/m³]
Nc_conc = ds.nc * rho                    # convert to #/m³
Ni_conc = ds.ni * rho
print(f"N_c mean: {Nc_conc.mean().item():.3e} m⁻³  (target: 1.0e8)")
print(f"N_i max:  {Ni_conc.max().item():.3e} m⁻³  (target: ≤1.0e5)")
```

---

## FAQ: Do N_c and N_i Represent Always-Present Particles or Maximums?

**Question:** Does setting these constants mean there are always $N_c$ cloud droplets and $N_i$ ice cloud crystals? Or are they just the numbers of aerosol particles that can become cloud droplets/ice crystals if the environment and other conditions allow? In other words, $N_c$ and $N_i$ are the possible, maximum numbers of cloud droplets and ice crystals, correct?

**Answer:** No, they do not represent a pool of available aerosol particles waiting to activate, and they behave differently from each other. In the idealized `noAero` RCEMIP configuration, the complex aerosol activation process is bypassed entirely. Here is exactly what setting those constants means for $N_c$ and $N_i$ in the P3 microphysics scheme:

### For $N_c$ (Cloud Droplet Number Concentration)
$N_c$ is **not a maximum**, it is an **exact, prescribed value**—but it is only applied where a cloud actually exists. 
- When the model determines that liquid cloud water ($q_c > 0$) has formed in a grid cell, it mathematically overwrites the droplet number in that cloud to be exactly $N_c$ (which we set to $1.0 \times 10^8 \text{ m}^{-3}$).
- If there is no cloud in a grid cell (clear sky), the droplet number is zero. 
- It does not represent a "potential" number of aerosols. The model simply assumes: *"Whenever and wherever liquid water condenses, it will automatically partition into exactly $N_c$ droplets per cubic meter."*

### For $N_i$ (Ice Crystal Number Concentration)
Your intuition about it being a **maximum possible number** is actually **100% correct for ice!**
- Unlike droplets, ice crystals have "memory"—they can advect for hundreds of miles in cirrus anvils, aggregate into larger snowflakes, or undergo explosive secondary multiplication (rime splintering).
- Because of this, forcing $N_i$ to be a fixed constant everywhere there is ice would physically break the model (e.g., a sparse cirrus anvil with huge crystals would suddenly be "corrected" into a dense cloud of tiny crystals at the next timestep).
- Instead, the RCEMIP target ($1.0 \times 10^5 \text{ m}^{-3}$) is applied as a parameter called `max_total_ni`. The ice number is fully prognostic (it grows and shrinks based on temperature, nucleation, and advection), but the model strictly **caps** it so it never exceeds $1.0 \times 10^5 \text{ m}^{-3}$.

### Summary
*   **$N_c$** is the **exact** number of droplets present *within any given liquid cloud*. 
*   **$N_i$** is the **maximum cap** for the number of ice crystals, but the actual number can be much lower depending on the cloud's history and temperature.

---

## FAQ: Why are there intermediate values of N_c in instantaneous output?

**Question:** When plotting $N_c$ at a specific level (e.g., level 79 / ~5000m) from the instantaneous hourly history file, most grid points are either 0 or $1.0\times10^8$, but a few have intermediate values like $0.9\times10^8$ or $0.45\times10^8$. No interpolation or averaging has been done. What could explain this discrepancy? Is the output $N_c$ weighted by cloud fraction?

![N_c raw values plot](../python_DP-SCREAM/testfigs/RCE09_dx3km_gpu.nc_m3_level_79.2000-02-01_to_2000-02-01_time_raw.png)

**Answer:** No, the output $N_c$ is **not** weighted by cloud fraction. The intermediate values you are seeing are "ghost" tracer concentrations caused by the interaction between the model's **dynamical advection** and an **early-exit optimization** in the P3 microphysics code.

Here is exactly how these "ghost" values get created and preserved in the output:

### 1. Dynamics (Advection) Mixes the Tracers
In EAMxx, $N_c$ is treated as an advecting tracer. When the dynamical core (HOMME) advects air between grid cells, it mixes them. If a cloudy grid cell (where P3 previously forced $N_c = 1.0\times10^8$) mixes with a clear-sky grid cell ($N_c = 0$), the resulting grid cell will end up with an intermediate, mathematically mixed tracer value (e.g., $0.45\times10^8$). During this mixing, the cloud water mass ($q_c$) is also mixed and reduced.

### 2. P3's `skip_all` Optimization 
At the very beginning of the P3 microphysics step, there is a performance optimization flag called `skip_all`. P3 will completely skip all calculations for a vertical column pack if:
* There are practically no hydrometeors ($q_c, q_r, q_i < 10^{-8}$ kg/kg)
* The temperature is below freezing ($T < 0^\circ$C)
* The air is subsaturated with respect to ice ($RH_{\text{ice}} < 95\%$)

At level 79 (~5,000 meters), the temperature is below freezing. In clear-sky regions away from convection, the air is also subsaturated. Thus, the `skip_all` condition is met for cells where the liquid water has evaporated or dispersed.

### 3. The Missed Clipping
Normally, at the end of the P3 physics step, there is a cleanup routine that says: *"If $q_c$ is effectively zero, force $N_c$ back to 0."* 
However, **because the `skip_all` condition was met, P3 skips the entire cell, including the cleanup routine.** As a result, the $N_c$ tracer is completely untouched by the physics step and retains whatever mixed, intermediate value the dynamical advection left it with (e.g., $0.45\times10^8$). It simply passes right through to your instantaneous history output.

### Is this a problem?
**No, this does not affect the simulation.** Even though there is a non-zero droplet number ($N_c$) lingering in that cell, the actual liquid water mass ($q_c$) is effectively zero ($< 10^{-8}$ kg/kg). Because there is no mass, the droplets cannot absorb radiation, interact with aerosols, or precipitate. They are just inert "ghost" numbers advecting through the clear air. 

If conditions change and a cloud actually forms in that grid cell later, the `skip_all` flag will turn off, P3 will run, and it will immediately overwrite the intermediate $N_c$ value back to exactly $1.0\times10^8$ inside the new cloud.

---

## Initial Conditions

### File Paths and Roles
The RCE configuration in DP-SCREAM uses two primary files for initialization:

1. **Initial Condition Profiles (IOP File):**
   Provides the initial horizontally uniform profiles (e.g., temperature and moisture) and boundary conditions.
   * **Absolute Path:** `/global/cfs/cdirs/e3sm/inputdata/atm/cam/scam/iop/RCE_300K_iopfile_4scam.nc`
   * **Configured via:** `./atmchange iop_file=...`

2. **Base 3D Initial Conditions File:**
   Provides the base 3D initial state and the global grid definition (which is subsequently overwritten by the IOP profiles).
   * **Absolute Path:** `/global/cfs/cdirs/e3sm/inputdata/atm/scream/init/screami_ne30np4L128_20221004.nc`
   * **Configured via:** `./atmchange initial_conditions::filename=...`

### Step-by-Step Initialization Flow
The initialization process follows these steps internally within EAMxx (specifically controlled by `atmosphere_driver.cpp`):

1. **Base Allocation:** The model first loads the 3D base state from `initial_conditions::filename`. It uses this file to establish the core global grid geometry, allocate memory for the arrays, and fill the domain with placeholder physical state variables.
2. **IOP Overwrite:** Immediately after the base Initial Conditions are processed, the driver checks if an `iop_file` was provided.
3. **Broadcasting:** The driver then calls a dedicated function (`m_iop_data_manager->set_fields_from_iop_data`). This function takes the horizontally uniform 1D profiles (such as Temperature and Moisture) from the specified `iop_file` and explicitly overwrites the placeholder values in every single column across the 3D grid.

This ensures that the thermodynamic starting state is uniformly set by the IOP file, overriding the base 3D file entirely.

### The Time Dimension in the IOP File
When examining the IOP file (`RCE_300K_iopfile_4scam.nc`), one might notice that it contains exactly two time levels (`tsec = 0` and `tsec = 43200000`, which corresponds to 500 days), and the variable values at these two times are identical. 

This structure is a standard convention for Single Column Model (SCM) or Intensive Observation Period (IOP) forcing frameworks used in E3SM/EAMxx:
* **Time Interpolation:** The `IOPDataManager` component is designed to read time-varying weather conditions and linearly interpolate between the "previous" and "next" time stamps.
* **Providing Bounding Points:** If the file only contained a single time slice, the interpolation routine would fail because it wouldn't have a bounding "next" time step to interpolate towards.
* **Constant Forcing:** By providing two identical time slices bridging a 500-day window, the model successfully interpolates values at every time step. Because the start and end values are exactly the same, the resulting forcing remains perfectly constant throughout the simulation. This fulfills the idealized RCE requirement without needing special "constant forcing" logic in the source code.

### Verification and Plotting Script
A Python script is available to verify the contents of the initial condition IOP file:
* **Location:** `python_DP-SCREAM/check_ICfile.py`
* **Functionality:** 
  - Automatically identifies variables that do not depend on height (like surface pressure, $P_s$) and prints their values to the terminal.
  - Computes the physical height above sea level (in km) by integrating the hydrostatic equation layer-by-layer.
  - Generates line plots for all multi-level variables (e.g., $T, q, u, v, \omega$) against the calculated physical height.
  - Designed with `# %%` separators to be run interactively cell-by-cell in an IDE, or as a standalone script using the `dpscream_analysis` conda environment.

---

## History Files: Timestamps and Restart Behavior

In EAMxx (and E3SM in general), the timestamp in a history filename (e.g., `...00000.nc` vs `...03600.nc`) does **not** represent the time of the first snapshot written into it. Instead, it represents the **exact time the file was created and opened**, which corresponds to the start of the tracking/accumulation interval.

This distinction leads to different naming and splitting behaviors between `AVERAGE` and `INSTANT` output streams, particularly across restart boundaries.

### AVERAGE History Streams
For an `AVERAGE` history stream (e.g., a 1-hour average), the snapshot written at `01:00` accumulates data over the time bounds `[00:00, 01:00]`. 
* To start accumulating data over that interval, the model opens the file right at the beginning of the run (at exactly `00:00:00`). Because the file is "born" at `00:00`, it gets the `00000.nc` suffix.
* When the simulation hits a restart boundary (e.g., exactly at `00:00` of day 6), the restart job immediately opens a new file at `00:00` to start accumulating the next interval. 
* **Result:** `AVERAGE` streams cleanly maintain the `00000.nc` suffix across all initial runs and restart runs.

### INSTANT History Streams
By default, `INSTANT` history streams output a snapshot of the initial state at the exact moment the simulation begins (`t=0` or `00:00:00`). This causes a phase shift:
* For a 5-day continuous run outputting hourly, there are 120 hours. But because of the `t=0` snapshot, the first run actually writes **121 snapshots**.
* If `max_snapshots_per_file: 24` is set, the history manager packs the first 120 snapshots into 5 files. The 121st snapshot (exactly `00:00:00` of the 6th day) gets stranded all by itself in a newly created file: `...2000-01-06-00000.nc`.
* When the restart job begins at `00:00:00`, it knows that time was already output. Its first actual output is triggered one hour later at `01:00:00` (`03600` seconds).
* Because it waits until `01:00` to open its file, the restart file is named `...2000-01-06-03600.nc`. Every subsequent file in the restart runs will also start at `01:00` and have the `03600` suffix.

### The Solution: `skip_t0_output: true`
To make `INSTANT` output consistent and avoid 1-snapshot stranded files at restart boundaries, you can instruct EAMxx to skip the `t=0` output by adding `skip_t0_output: true` to the `output_control` section of your instantaneous YAML file:

```yaml
output_control:
  frequency: 1
  frequency_units: nhours
  skip_t0_output: true
```

* **Effect on INSTANT:** The output manager waits until `01:00` to open its very first file. It creates the file at exactly `03600` seconds, permanently adopting `03600.nc` as its filename suffix for both the initial run and all subsequent restarts. Each file will cleanly hold exactly 24 snapshots.
* **Effect on AVERAGE:** You do not need to add this flag to average YAML files. Average streams never output a `t=0` snapshot to begin with, which is why they naturally avoid this issue.
