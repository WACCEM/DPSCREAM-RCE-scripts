# PINACLES Simulation Case Summary: RCE00_dx1km_600x600km

## Overview

This document describes the configuration and output of the RCE simulation "RCE00_dx1km_600x600km" using the PINACLES model. It starts with the idealized initial condition and show clear convective self-aggregation.

*Note: This simulation was originally referred to as "RCE_600x600_1km", but is now called "RCE00_dx1km_600x600km" to coordinate with additional sensitivity simulations.*
*   **Model:** PINACLES
*   **Case Type:** Radiative Convective Equilibrium (RCE)
*   **Run Scripts:** `sub_test.sh` and `resub_test_mr.sh`
*   **Configuration File:** `RCE_600x600_1km.json`
*   **Script Directory:** `/global/cfs/cdirs/wcm_code/ksa/PINACLES/batch_scripts/pinacles-rce-runscripts/RCE00_dx1km_600x600km`
*   **Model Source Code:** `/global/cfs/cdirs/wcm_code/ksa/PINACLES/PINACLES` (at commit `f3a70bf5e0478149ca358f0d31597f57f9ef3ed8`)
    *   *Note: This commit is prior to the final configuration changes made to more strictly adhere to the RCEMIP protocol (as described from line 641 in `PINACLES_RCE_note.md`). Those changes have not been staged yet.*
*   **Root Simulation Directory:** `/pscratch/sd/k/ksa/simulation/PINACLES/rce/1km/RCE00_dx1km_600x600km`
*   **Post-Processed Data Directory:** `/pscratch/sd/w/wcmca1/PINACLES/RCE00_dx1km_600x600km`

## Computational Configuration
*   **Machine:** NERSC Perlmutter (CPU nodes)
*   **Processors:** 2048 processes (16 nodes)
*   **Walltime:** 03:30:00
*   **Simulation Length per Job:** 2 days (172800 seconds)

## Physical Configuration
*   **Initial Conditions:** `/global/cfs/cdirs/wcm_code/PINACLES/share/data/profile_from_SCREAM_linear.nc`
*   **Domain Size:** 600 km $\times$ 600 km $\times$ 33.0 km
*   **Grid Elements:** 600 $\times$ 600 $\times$ 165 
*   **Horizontal Resolution:** 1 km 
*   **Vertical Levels:** 165
*   **Microphysics:** P3 scheme (`nccnst` = $1.0 \times 10^8$ m⁻³)
*   **Radiation:** Enabled (`rce` type, updated every 300 s)
*   **SGS Model:** Smagorinsky

## Output Variables and Structure

Unlike E3SM/DP-SCREAM which outputs to a single directory, each PINACLES batch job creates a new timestamped subdirectory within the root simulation directory. Inside these job subdirectories, different output types are saved in their respective folders.

For example, the main 2D output fields (`fields2d`) for a specific job can be found at:
`/pscratch/sd/k/ksa/simulation/PINACLES/rce/1km/RCE00_dx1km_600x600km/RCE_600x600_1km_started_2026_05_01-05_23_41_PM/fields2d`. For convenience, the 2D history files from different subdirectories have been organized into a single directory by symbolic links as desribed below.
 
The `fields2d` output is written at a frequency of every 3600 seconds (1 hour) as instantanous values. Output variables include `T`, `qv`, `thetav`, `qc`, `buoyancy`, and `reflectivity` at specified vertical levels.

### Raw output files

The 2D history files from different subdirectories have been organized into the following single directory by symbolic links.

Directory: `/pscratch/sd/w/wcmca1/PINACLES/RCE00_dx1km_600x600km/simlinks/fields2d`

The vertical levels designated as `[level]` in the table below are: 100.0, 500.0, 900.0, 1900.0, 2900.0, 4900.0, 5900.0, 7900.0, and 9900.0 meters.

| Variable | Description | Units |
|----------|-------------|-------|
| `IWP` | ice water path | `kg m^-2` |
| `LWP` | liquid water path | `kg m^-2` |
| `RAINNC` | accumulated precipitation | `mm` |
| `RAINNCV` | accumulated precipitation volume | `mm` |
| `T2` | temperature at 2m | `K` |
| `T_[level]` | Temperature | `K` |
| `buoyancy_[level]` | buoyancy | `m s^{-2}` |
| `cp_base` | Cold pool Base | `m` |
| `cp_depth` | Cold pool Depth | `m` |
| `cp_intensity` | Cold pool Intensity | `m/s` |
| `imse` | Integrated Moist Static Energy | `J m^-2` |
| `lhf` | surface latent heat flux | `W m^-2` |
| `pseudo-albedo` | pseudo albedo | `dimensionless` |
| `qc_[level]` | cloud water mixing ratio | `kg kg^{-1}` |
| `qv2` | humidity at 2m | `kg kg-1` |
| `qv_[level]` | water vapor mixing ratio | `kg kg^{-1}` |
| `ref` | maximum reflectivity | `dBz` |
| `reflectivity_[level]` | radar reflectivity | `dBz` |
| `shf` | surface sensible heat flux | `W m^-2` |
| `slp` | sea level pressure | `Pa` |
| `surface_lw_down` | surface longwave down | `W/m^2` |
| `surface_lw_up` | surface longwave up | `W/m^2` |
| `surface_sw_down` | surface shortwave down | `W/m^2` |
| `surface_sw_up` | surface shortwave up | `W/m^2` |
| `thetav_[level]` | Virtual Potential Temperature | `K` |
| `toa_lw_down` | TOA longwave down | `W/m^2` |
| `toa_lw_up` | TOA longwave up | `W/m^2` |
| `toa_sw_down` | TOA shortwave down | `W/m^2` |
| `toa_sw_up` | TOA shortwave up | `W/m^2` |
| `u10` | u velocity component at 10m | `m s-1` |
| `u_[level]` | u velocity component | `m/s` |
| `v10` | v velocity component at 10m | `m s-1` |
| `v_[level]` | v velocity component | `m/s` |
| `visibility` | visibility | `-` |
| `w_[level]` | w velocity component | `m/s` |
| `windspeed10` | windspeed at 10m | `m^2 s^{-1}` |
| `windspeed_sfc` | surface windspeed | `m s^{-1}` |

### Processed output variables

Directory: `/pscratch/sd/w/wcmca1/PINACLES/RCE00_dx1km_600x600km/cat_raw`

| Variable | Description  | Units |
|----------|------------- |-------|
| `rain_rate`| Hourly precipitation rate | mm/hour |
| `toa_lw_up` | Upward LW flux at the top of the atmosphere | W/m2 |
| `ref` | maximum reflectivity | dBz |
| `imse` | Vertically Integrated Moist Static Energy | J/m2 |