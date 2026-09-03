# Radiative-Convective Equilibrium by DP-SCREAM: Doubly-Periodic SCREAM and PINACLES model

Scripts and configuration files for running
**DP-SCREAM** (Doubly-Periodic Simple Cloud-Resolving E3SM Atmosphere Model)
simulations of idealized **Radiative-Convective Equilibrium (RCE)** cases and analysis of the outputs to compare DP-SCREAM and PINACLES RCE simulations.

---

## Table of Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Requirements](#requirements)
- [Simulations](#simulations)
  - [Running](#running)
  - [Post-Processing](#post-processing)
  - [Output](#output)
  - [Archive](#archive)

---

## Overview

This repository provides tools to:

- Bash scripts to build and launch DP-SCREAM RCE simulations on NERSC Perlmutter CPU and GPU nodes: model source code in a separate directory
- Configure model output via YAML files
- Concatenate, regrid, and horizontally average model output
- Analyze and visualize the results using Python scripts
- Bash scripts for NCO, HPSS archive, and GNU parallel tasks

---

## Repository Structure

```
DP-SCREAM/
├── batch/                                # Bash scripts for executing batch/parallel processing jobs
├── docs/                                 # Documentation for DP-SCREAM and PINACLES RCE simulations
├── dpscream_doc/                         # (external / not tracked) Notes and LaTeX write-ups
├── giobiagioli_organization_indices/     # Original reference code for computing organization indices
├── hpss/                                 # Bash scripts for archiving simulation data to HPSS
├── input/                                # Initial conditions and forcing profile files (e.g. RCEMIP)
├── mcs/                                  # Scripts to format and prepare outputs for MCS tracking
├── nco/                                  # Bash scripts utilizing NCO for regridding or data manipulation
├── organization_indices/                 # Python scripts and notebooks for computing organization indices
├── python_DP-SCREAM/                     # Python scripts and Jupyter notebooks for post-processing
│   ├── remap/                            # Horizontal remapping weights and regridding scripts
│   └── *.py / *.ipynb
├── rce_tools/                            # Shared Python package with analysis and plotting tools
├── run_scripts/                          # Bash job-submission scripts for HPC
│   └── yaml_files/                       # SCREAM output YAML configuration files
├── scmlib/                               # (external / not tracked) SCM/DP utility library
└── vs_pinacles/                          # Python scripts and notebooks for comparing DP-SCREAM and PINACLES
```
---

## Requirements

### Run DP-SCREAM (E3SM with eamxx)

- cray-python module (not the standard Python module)

Other dependancies are already taken care of in the E3SM code for the Perlmutter system
later)
- It is better to load the cray Python module than the NERSC Python modules. As of 2026-05, the default is `cray-python/3.11.7`.
- DO NOT load the standard Python module nor activate the E3SM unified environment when configuring and manupilating DP-SCREAM (E3SM) cases
- See the "CIME Python Version Warning and Its Side Effects" section in `run_scripts/build_failures.md`.

### Analysis

**Recommended Conda Environment (`dpscream_analysis`)**

Shared `dpscream_analysis` Conda environment is available on Perlmutter for WACCEM repo members. To use it:
```bash
module load python
conda activate dpscream_analysis
```

*Current configuration (as of Sep 2026):*
- **Python:** 3.11.14
- **Data & I/O:** `xarray` (2025.10.1), `numpy` (2.2.6), `scipy` (1.16.2), `netCDF4` (1.7.3), `h5py` (3.16.0)
- **Visualization:** `matplotlib` (3.10.7), `cartopy` (0.25.0)

---

## Simulations

### Running

Job scripts are located in `run_scripts/`. Edit the relevant script for your
allocation and paths, then submit:

```bash
# Example — GPU run
sbatch run_scripts/run_gpu_dpxx_scream_RCE_dx1km.sh
```

See `run_scripts/RCE_configuration.md` for a description of the RCE case setup.

## PINACLES model

See another code project for configuring/running the PINACLES model for RCE (https://github.com/WACCEM/pinacles-rce-runscripts).

---

### List of DP-SCREAM Simulations

**RCE02_dx1km_gpu** is the primary simulation for the analysis. See the linked document for detail.

| Case name | Domain Size | Resolution | Initialization | Description |
|-----------|-------------|------------|----------------|-------------|
| RCE01_dx3km_gpu | 600x600 km | 3 km | | v3.0.2 release code default |
| RCE02_dx3km_gpu | 600x600 km | 3 km | | v3.1.0 alpha 8426cb31c7   |
| RCE03_dx3km_gpu | 600x600 km | 3 km | | v3.0.2 with `lambda_high = 0.08` |
| RCE04_dx3km_gpu | 600x600 km | 3 km | | v3.0.2 with `do_iop_subsidence=false` |
| RCE05_dx3km_gpu | 600x600 km | 3 km | | v3.1.0 8426cb31c7 with `do_iop_subsidence=false` |
| RCE06_dx3km_gpu | 600x600 km | 3 km | | v3.1.0 8426cb31c7 with P3 linear ccn function as in v3.0.2 |
| RCE07_dx3km_gpu | 600x600 km | 3 km | | v3.1.0 8426cb31c7 with the high solar irradiance in v3.0.2 |
| [**RCE02_dx1km_gpu**](docs/DPSCREAM_RCE02_dx1km.md) | 600x600 km | 1 km | | v3.1.0 8426cb31c7 with RCEMIP config |
| dx1km_L150km_RCE01_gpu | 150x150 km | 1 km | | v3.1.0 8426cb31c7 with RCEMIP config & RCEMIP IC |
| dx1km_L150km_RCE02_gpu | 150x150 km | 1 km | | v3.1.0 8426cb31c7 with RCEMIP config & default RCE IC |
| dx1km_L150km_RCE03_gpu? | 150x150 km | 1 km | | v3.1.0 8426cb31c7 with RCEMIP config & PINACLES IC |
| dx1km_L600km_RCE03_gpu | 600x600 km | 1 km | | v3.1.0 8426cb31c7 with RCEMIP config & PINACLES IC |

### List of PINACLES Simulations

**RCE01_dx1km_600x600km** is the primary simulation for the analysis. See the linked documents for detail.

| Case name | Domain Size | Resolution | Initialization | Description |
|-----------|-------------|------------|----------------|-------------|
| test_300x300_1km_init100 | 300×300 km | 1 km | init100 | |
| test_500x500_3km_scream_init_100dZ | 500×500 km | 3 km | SCREAM | 100m vertical spacing, half vertical levels |
| test_500x500_3km_scream_init_100dZ_nz330 | 500×500 km | 3 km | SCREAM | 100m vertical spacing, full vertical levels |
| test_600x600_3km_coldstart | 600×600 km | 3 km | Cold start | |
| test_600x600_3km_init100 | 600×600 km | 3 km | init100 | |
| test_600x600_3km_init100_2dhighfreq | 600×600 km | 3 km | init100 | 10-min 2D output |
| test_600x600_3km_scream_init | 600×600 km | 3 km | SCREAM | |
| test_600x600_3km_scream_init_2dhighfreq | 600×600 km | 3 km | SCREAM | 10-min 2D output |
| test_600x600_3km_scream_init_2dhighfreq_v2 | 600×600 km | 3 km | SCREAM | 10-min 2D output (v2) |
| test_600x600_4km_scream_init_100dz | 600×600 km | 4 km | SCREAM | 100m vertical spacing |
| RCE_150x150_1km (test_150x150_1km) | 150×150 km | 1 km | SCREAM linear profile | Base test: 12-hour run. |
| RCE02_150x150_1km (test02_150x150_1km) | 150×150 km | 1 km | SCREAM linear profile | 21-day run. |
| RCE03_150x150_1km (test03_150x150_1km) | 150×150 km | 1 km | SCREAM linear profile | 102-day run. `max_total_ni` added; 2D slice includes more microphysics vars (qnc, qni1, qi1). Daily 3D output. |
| RCE04_150x150_1km (test04_150x150_1km) | 150×150 km | 1 km | RCE03 profile | 1-day run. Initialized from `RCE03` profile. No restart. |
| RCE05_dx1km_150x150km | 150×150 km | 1 km | RCE03_v0 profile | 14-day run. Initialized from `RCE03_v0` profile. |
| RCE06_dx1km_150x150km | 150×150 km | 1 km | Cold start | 19-day run. Cold start (`spunup_init`: false, no profile). |
| [RCE00_dx1km_600x600km](docs/PINACLES_RCE00_dx1km.md) (RCE_600x600_1km) | 600×600 km | 1 km | SCREAM linear profile | 60-day run. |
| [**RCE01_dx1km_600x600km**](docs/PINACLES_RCE01_dx1km.md) | 600×600 km | 1 km | RCE03 profile | 44-day run. `max_total_ni` added; 2D slice includes more microphysics vars. |
| RCE02_dx1km_600x600km | 600×600 km | 1 km | RCE03 profile | 24-day run. |


---


## Post-Processing

Under development

```bash
# calculate vertically integrated MSE
python calc_imse_DPSCREAM.py

# calculate cold pool metrics
python calc_cp_DPSCREAM.py

# Concatenate (direct) output and/or processed (e.g., imse, cold pools) files
python python_DP-SCREAM/concat_DPSCREAM.py

# Horizontal average
python horiz_avg_DPSCREAM.py

# Regrid to a 2D grid specified by the SCRIP format file
python regrid_DPSCREAM.py
```

## Derived diagnostics

### cold pool (`python_DP-SCREAM/calc_cp_DPSCREAM.py`)

The script `python_DP-SCREAM/calc_cp_DPSCREAM.py` reads the 5-min instantaneous
snapshots and computes cold pool diagnostics following the PINACLES `CaseRCE.py`
methodology, adapted for the fully compressible equations used in DP-SCREAM.

#### Buoyancy

Buoyancy is defined via the **Density Potential Temperature**:

$$\theta_\rho = \theta \cdot \frac{1 + (R_v/R_d)\,q_v}{1 + q_v + q_c + q_i + q_r}$$

where $\theta$ is the model potential temperature (`PotentialTemperature`),
$q_v, q_c, q_i, q_r$ are the water vapour, cloud liquid, cloud ice, and rain
mixing ratios.  The numerator accounts for the density reduction due to water
vapour; the denominator accounts for the density increase due to condensate
loading.

> **Note on `qm` (P3 rime mass):** `qm` is a sub-component of the prognostic
> ice variable `qi` in the P3 microphysics scheme.  It is *not* added separately
> to avoid double-counting condensate in $\theta_\rho$.

Unlike PINACLES, which uses an anelastic reference density profile that is
constant in time and space, DP-SCREAM uses fully compressible dynamics.  The
**reference profile** is therefore the **area-weighted horizontal mean** of
$\theta_\rho$ computed at each output time step:

$$\overline{\theta}_\rho(t,k) = \frac{\sum_{\text{col}} \theta_\rho(t,\text{col},k)\,A_{\text{col}}}{\sum_{\text{col}} A_{\text{col}}}$$

The buoyancy perturbation is then:

$$b(t,\text{col},k) = g \,\frac{\theta_\rho(t,\text{col},k) - \overline{\theta}_\rho(t,k)}{\overline{\theta}_\rho(t,k)}$$

> **Precision note:** the dataset fields are stored as `float32`.  Accumulating
> 160,000 float32 values in the area-weighted mean introduces a ~0.2 K error
> that biases $b$ by ~0.02 m s⁻².  The script promotes all intermediate
> computations to `float64` before computing $\overline{\theta}_\rho$.

#### Cold pool detection and diagnostics

A fixed buoyancy threshold $b^* = -0.005\ \text{m s}^{-2}$ is applied
(same as PINACLES).

1. **Identify cold-pool columns** — a column is a cold-pool column if its
   lowest model level satisfies $b < b^*$.
2. **Find the first contiguous sub-threshold layer** — within each qualifying
   column, all levels with $b < b^*$ are gathered.  Consecutive indices
   separated by at most 1 level are merged into a single layer, and the bottom
   (`kbot`) and top (`ktop`) indices of the *first* (surface-rooted) layer are
   retained.
3. **Compute the three 2-D diagnostics:**

| Output variable | Formula | Units | Description |
|-----------------|---------|-------|-------------|
| `cp_base` | $z(k_\text{bot})$ | m | Height of the cold layer bottom |
| `cp_depth` | $z(k_\text{top} - k_\text{bot})$ | m | Proxy for cold layer vertical extent; equals $z[k_\text{top}]$ when $k_\text{bot}=0$ |
| `cp_intensity` | $\sqrt{-2\displaystyle\int_{z_\text{bot}}^{z_\text{top}} b\,dz}$ | m s⁻¹ | Analogous to the velocity acquired by a negatively buoyant parcel over the cold layer depth |

The vertical integral uses the **trapezoidal rule** over the model levels.

Additional output:

| Output variable | Description | Units |
|-----------------|-------------|-------|
| `buoy_sfc` | Buoyancy at the lowest model level (~13 m) | m s⁻² |
| `cp_area_frac` | Area-weighted fraction of cold-pool columns (scalar time series) | 1 |

Physical constants used: $g = 9.80665\ \text{m s}^{-2}$,
$R_d = 287.05\ \text{J kg}^{-1}\text{K}^{-1}$,
$R_v = 461.5\ \text{J kg}^{-1}\text{K}^{-1}$.

Output file naming: `{icase}.cp.INSTANT.nmins_x5.{timestamp}.nc`


## Archive 
screen and tmux

If you find screen a bit clunky, you might want to try tmux. It does the exact same thing but handles window resizing better and has a status bar at the bottom so you always know you are inside a virtual session.

```bash
tmux new -s hpss_transfer  #start a new session named hpss_transfer
Ctrl+b, then d  #detach from the session
tmux attach -t hpss_transfer #reattach to the session
```

HPSS Archive directory: ` /home/projects/m1867/RCE/DP-SCREAM/${casename}`

### Previous simulation

Chandru's raw outpus : /pscratch/sd/c/chandru/RCE_DP_SCREAM/scream_dpxx_RCE_300K/run/

```bash
// global attributes:
		:case_t0 = "2000-01-01-00000" ;
		:run_t0 = "2000-01-01-00000" ;
		:averaging_type = "AVERAGE" ;
		:averaging_frequency_units = "nhours" ;
		:averaging_frequency = 1 ;
		:file_max_storage_type = "num_snapshots" ;
		:max_snapshots_per_file = 721 ;
		:fp_precision = "single" ;
		:case = "scream_dpxx_RCE_300K" ;
		:source = "E3SM Atmosphere Model (EAMxx)" ;
		:eamxx_version = "1.0.0" ;
		:git_version = "8e96857632" ;
		:hostname = "pm-cpu" ;
		:username = "chandru" ;
		:atm_initial_conditions_file = "NONE" ;
		:topography_file = "NONE" ;
		:contact = "e3sm-data-support@llnl.gov" ;
		:institution_id = "E3SM-Project" ;
		:realm = "atmos" ;
		:history = "created on Thu Feb 27 22:17:08 2025" ;
		:Conventions = "CF-1.8" ;
		:product = "model-output" ;
}
```
Processed by Laura : /pscratch/sd/p/paccini/temp/output_dp_scream/processed_500x500/


---
