# DP-SCREAM: Doubly-Periodic SCREAM — Radiative-Convective Equilibrium

Scripts, notebooks, and configuration files for running and post-processing
**DP-SCREAM** (Doubly-Periodic Simple Cloud-Resolving E3SM Atmosphere Model)
simulations of idealized **Radiative-Convective Equilibrium (RCE)** cases.

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
- [Configuration](#configuration)
- [Contributing](#contributing)
- [Contact](#contact)

---

## Overview

This repository provides tools to:

- Launch DP-SCREAM RCE simulations on HPC systems (CPU and GPU)
- Configure model output via YAML files
- Concatenate, regrid, and horizontally average model output
- Analyse and visualise the results via Jupyter notebooks

---

## Repository Structure

```
DP-SCREAM/
├── python_DP-SCREAM/     # Python scripts and Jupyter notebooks for post-processing
│   ├── remap/            # Horizontal remapping weights and regridding scripts
│   └── *.py / *.ipynb
├── run_scripts/          # Bash job-submission scripts for HPC
│   └── yaml_files/       # SCREAM output YAML configuration files
├── theory/               # (external / not tracked) Notes and LaTeX write-ups
└── scmlib/               # (external / not tracked) SCM/DP utility library
```

---

## Requirements

| Dependency | Purpose |
|------------|---------|
| Python ≥ 3.9 | Post-processing and analysis |
| `xarray`, `numpy`, `scipy` | Data manipulation |
| `matplotlib`, `cartopy` | Visualisation |
| `xesmf` | Regridding |
| `netCDF4` / `h5py` | NetCDF I/O |
| E3SM / SCREAM source code | Running simulations |

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

---


### output

Output frequency: **5 min instantaneous snapshots** (`scream_new_output_inst_5min.yaml`).

| Variable | Description | Source |
|----------|-------------|--------|
| `z_mid` | Height at layer midpoints | Dynamics |
| `p_mid` | Pressure at layer midpoints | Dynamics |
| `ps` | Surface pressure | HOMME |
| `omega` | Vertical pressure velocity | HOMME |
| `cldfrac_liq` | Liquid cloud fraction | SHOC |
| `eddy_diff_mom` | Eddy diffusivity for momentum | SHOC |
| `sgs_buoy_flux` | Sub-grid buoyancy flux | SHOC |
| `tke` | Turbulent kinetic energy | SHOC |
| `inv_qc_relvar` | Inverse cloud liquid relative variance | SHOC |
| `pbl_height` | Planetary boundary layer height | SHOC |
| `cldfrac_ice` | Ice cloud fraction | CLD |
| `cldfrac_tot_for_analysis` | Total cloud fraction (for analysis) | CLD |
| `bm` | Ice rime volume mixing ratio | P3 |
| `nc` | Cloud droplet number concentration | P3 |
| `ni` | Cloud ice number concentration | P3 |
| `nr` | Rain drop number concentration | P3 |
| `qi` | Cloud ice mixing ratio | P3 |
| `qm` | Ice rime mass mixing ratio | P3 |
| `qr` | Rain mixing ratio | P3 |
| `U` | Zonal wind | SHOC / HOMME |
| `V` | Meridional wind | SHOC / HOMME |
| `qc` | Cloud liquid water mixing ratio | SHOC / P3 |
| `qv` | Water vapour mixing ratio | SHOC / P3 |
| `T_mid` | Air temperature at layer midpoints | SHOC / P3 / RRTMGP / HOMME |
| `LiqWaterPath` | Vertically integrated liquid water path | RRTMGP |
| `IceWaterPath` | Vertically integrated ice water path | RRTMGP |
| `RainWaterPath` | Vertically integrated rain water path | RRTMGP |
| `RimeWaterPath` | Vertically integrated rime water path | RRTMGP |
| `VapWaterPath` | Vertically integrated water vapour path | RRTMGP |
| `PotentialTemperature` | Potential temperature | Diagnostics |
| `LiqPotentialTemperature` | Liquid-water potential temperature | Diagnostics |
| `DryStaticEnergy` | Dry static energy | Diagnostics |
| `RelativeHumidity` | Relative humidity | Diagnostics |
| `SeaLevelPressure` | Sea-level pressure | Diagnostics |
| `surf_radiative_T` | Surface radiative temperature | Coupler |
| `T_2m` | 2-m air temperature | Coupler |
| `qv_2m` | 2-m water vapour mixing ratio | Coupler |
| `wind_speed_10m` | 10-m wind speed | Coupler |
| `U_at_10m_above_surface` | 10-m zonal wind | Coupler |
| `V_at_10m_above_surface` | 10-m meridional wind | Coupler |

Output frequency: **5 min averages** (`scream_new_output_avg_5min.yaml`).

| Variable | Description | Source |
|----------|-------------|--------|
| `z_mid` | Height at layer midpoints | Dynamics |
| `p_mid` | Pressure at layer midpoints | Dynamics |
| `ps` | Surface pressure | HOMME |
| `eddy_diff_mom` | Eddy diffusivity for momentum | SHOC |
| `sgs_buoy_flux` | Sub-grid buoyancy flux | SHOC |
| `tke` | Turbulent kinetic energy | SHOC |
| `inv_qc_relvar` | Inverse cloud liquid relative variance | SHOC |
| `pbl_height` | Planetary boundary layer height | SHOC |
| `micro_liq_ice_exchange` | Microphysics liquid–ice exchange rate | P3 |
| `micro_vap_ice_exchange` | Microphysics vapour–ice exchange rate | P3 |
| `micro_vap_liq_exchange` | Microphysics vapour–liquid exchange rate | P3 |
| `precip_liq_surf_mass_flux` | Surface liquid precipitation mass flux | P3 |
| `precip_ice_surf_mass_flux` | Surface ice precipitation mass flux | P3 |
| `precip_total_surf_mass_flux` | Total surface precipitation mass flux | P3 |
| `rad_heating_pdel` | Radiative heating rate × pressure thickness | RRTMGP |
| `sfc_flux_lw_dn` | Downwelling longwave flux at surface | RRTMGP |
| `sfc_flux_sw_net` | Net shortwave flux at surface | RRTMGP |
| `ShortwaveCloudForcing` | Shortwave cloud radiative effect | RRTMGP |
| `LongwaveCloudForcing` | Longwave cloud radiative effect | RRTMGP |
| `ZonalVapFlux` | Zonal column water vapour flux | RRTMGP |
| `MeridionalVapFlux` | Meridional column water vapour flux | RRTMGP |
| `SW_flux_up_at_model_top` | Upwelling SW flux at model top | RRTMGP |
| `SW_flux_dn_at_model_top` | Downwelling SW flux at model top | RRTMGP |
| `LW_flux_up_at_model_top` | Upwelling LW flux at model top | RRTMGP |
| `SW_flux_dn_at_model_bot` | Downwelling SW flux at model bottom | RRTMGP |
| `SW_flux_up_at_model_bot` | Upwelling SW flux at model bottom | RRTMGP |
| `LW_flux_dn_at_model_bot` | Downwelling LW flux at model bottom | RRTMGP |
| `LW_flux_up_at_model_bot` | Upwelling LW flux at model bottom | RRTMGP |
| `SW_clrsky_flux_up_at_model_top` | Clear-sky upwelling SW flux at model top | RRTMGP |
| `LW_clrsky_flux_up_at_model_top` | Clear-sky upwelling LW flux at model top | RRTMGP |
| `SW_clrsky_flux_dn_at_model_bot` | Clear-sky downwelling SW flux at model bottom | RRTMGP |
| `SW_clrsky_flux_up_at_model_bot` | Clear-sky upwelling SW flux at model bottom | RRTMGP |
| `LW_clrsky_flux_dn_at_model_bot` | Clear-sky downwelling LW flux at model bottom | RRTMGP |
| `LW_clrsky_flux_up_at_model_bot` | Clear-sky upwelling LW flux at model bottom | RRTMGP |
| `surface_upward_latent_heat_flux` | Surface upward latent heat flux | Diagnostics |
| `surf_mom_flux` | Surface momentum flux | Coupler |
| `surf_sens_flux` | Surface sensible heat flux | Coupler |
| `surf_evap` | Surface evaporation | Coupler |
| `shoc_T_mid_tend` | SHOC temperature tendency | Process rates |
| `p3_T_mid_tend` | P3 temperature tendency | Process rates |
| `rrtmgp_T_mid_tend` | RRTMGP temperature tendency | Process rates |
| `shoc_qv_tend` | SHOC water vapour tendency | Process rates |
| `p3_qv_tend` | P3 water vapour tendency | Process rates |
| `homme_T_mid_tend` | HOMME temperature tendency | Process rates |
| `homme_qv_tend` | HOMME water vapour tendency | Process rates |
| `PotentialTemperature_at_700hPa` | Potential temperature at 700 hPa | Diagnostics |
| `PotentialTemperature_at_1000hPa` | Potential temperature at 1000 hPa | Diagnostics |
| `omega_at_500hPa` | Vertical pressure velocity at 500 hPa | Diagnostics |
| `RelativeHumidity_at_700hPa` | Relative humidity at 700 hPa | Diagnostics |
| `SeaLevelPressure` | Sea-level pressure | Diagnostics |

---


## Post-Processing

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

### Derived diagnostics — cold pool (`python_DP-SCREAM/calc_cp_DPSCREAM.py`)

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


### Archive 
screen and tmux

If you find screen a bit clunky, you might want to try tmux. It does the exact same thing but handles window resizing better and has a status bar at the bottom so you always know you are inside a virtual session.

```bash
tmux new -s hpss_transfer  #start a new session named hpss_transfer
Ctrl+b, then d  #detach from the session
tmux attach -t hpss_transfer #reattach to the session
```

HPSS Archive directory: ` /home/projects/m1867/RCE/DP-SCREAM/${casename}`

#### Previous simulation

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

## Configuration

Model output variables and frequency are controlled by YAML files in
`run_scripts/yaml_files/`. See `run_scripts/RCE_configuration.md` for details.

---

## Contributing

1. Fork the repository and create a feature branch.
2. Follow existing code style (PEP 8 for Python, ShellCheck-clean for bash).
3. Open a pull request with a clear description of the changes.

---

## Contact

| Name | Institution | Email |
|------|-------------|-------|
| TODO | TODO | TODO |
