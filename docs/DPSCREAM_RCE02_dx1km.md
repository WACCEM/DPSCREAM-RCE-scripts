# DP-SCREAM Simulation Case Summary: RCE02_dx1km_gpu

## Overview
This document summarizes the configuration, output variables, and characteristics of the `RCE02_dx1km_gpu` simulation case.

*   **Model:** SCREAMv1 in doubly periodic mode (DP-EAMxx)
*   **Case Type:** Radiative Convective Equilibrium (RCEMIP1 configuration; Wing et al., 2018)
*   **Run Script:** `run_scripts/run_RCE02_dx1km_gpu.sh`
*   **Model Execution Directory:** `/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE02_dx1km_gpu`
*   **Post-Processed History Files:** `/pscratch/sd/w/wcmca1/DP-SCREAM/RCE02_dx1km_gpu` (Contains `cat_raw`, `havg`, and `remapped` directories)

## Computational Configuration
*   **Machine:** pm-gpu (NERSC Perlmutter GPU)
*   **Compiler:** gnugpu
*   **Processors:** 64 processes
*   **Walltime:** 03:30:00
*   **Source Code:** `/global/cfs/cdirs/wcm_code/ksa/E3SM/code_tests/8426cb31c7_clone`
*   **Simulation Length per Job:** 5 days

## Physical Configuration
*   **Sea Surface Temperature (SST):** 300 K (Constant)
*   **Initial Conditions (IOP):** `RCE09_dx3km_gpu_equilibrium_300K_profile.nc`
*   **Domain Size:** 600 km $\times$ 600 km
*   **Grid Elements:** 200 $\times$ 200 (`num_ne_x`, `num_ne_y`)
*   **Horizontal Resolution:**
    *   Grid Element Size: 3 km (600 km / 200 elements)
    *   Dynamics Grid Spacing: 1 km (3 $\times$ 3 GLL nodes per element)
    *   Physics Grid Spacing: 1.5 km (2 $\times$ 2 pg2 nodes per element)
*   **Vertical Levels:** 128
*   **Time Steps:**
    *   Model / Physics Time Step: 30 seconds
    *   Dynamics Time Step: 2.5 seconds
*   **Second-Order Viscosity (near model top):** 3000.0 m²/s (`nu_top_dyn`)
*   **Surface Flux Scheme:** UofA surface flux scheme (`ocn_surface_flux_scheme = 2`)
*   **Interactive SW Radiation:** Enabled (`solar_angle = -1`)

## Aerosol and Microphysics (RCEMIP Compliance)
The simulation is configured to mirror SCREAM's `noAero` compsets to ensure RCEMIP aerosol compliance:
*   **Ozone Profile:** Uses RCEMIP ozone profile (`O3_RCEMIP.nc`).
*   **Aerosol Climatology:** SPA (Simple Prescribed Aerosol) is removed from the `mac_aero_mic` process list.
*   **Aerosol Optical Properties:** Disabled in RRTMGP radiative transfer (`do_aerosol_rad=false`).
*   **Prognostic Cloud Number ($N_c$):** Disabled in P3 (`do_prescribed_ccn=false`, `do_predict_nc=false`); uses the fallback compile-time constant $N_{CCNST}$.
*   **In-Cloud Ice Number:** Capped at the RCEMIP-recommended value of 1.0 $\times$ 10$^5$ m⁻³ (`max_total_ni=1.0e5`).

## Output Variables and Structure

Model outputs are controlled by two YAML files located in `run_scripts/yaml_files/`. Both streams output every **1 hour**.

Additionally, some variables have been remapped from the native unstructured grid to the Cartesian grid used by the "PINACLES" model for analysis. This Cartesian grid features a 1-km grid spacing ("PINACLES_YX_dx1km" grid). These remapped files are saved under the `remapped/` subdirectory. The regridding process was performed by the script `python_DP-SCREAM/regrid_DPSCREAM.py`.

### Raw output files

Directory: `/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE02_dx1km_gpu/run`

#### 1-Hourly Average Fields

File Prefix:*`${CASE}.hist`

Averaging Type: Average

Source: `scream_test9_output_avg_1hour.yaml`


| Variable | Description | Source | Units | Dimensions |
|----------|-------------|--------|-------|------------|
| `z_mid` | Height at layer midpoints | Dynamics | `m` | `(time, ncol, lev)` |
| `p_mid` | Pressure at layer midpoints | Dynamics | `Pa` | `(time, ncol, lev)` |
| `ps` | Surface pressure | HOMME | `Pa` | `(time, ncol)` |
| `SeaLevelPressure` | Sea-level pressure | Diagnostics | `Pa` | `(time, ncol)` |
| `pbl_height` | Planetary boundary layer height | SHOC | `m` | `(time, ncol)` |
| `eddy_diff_mom` | Eddy diffusivity for momentum | SHOC | `(m^2)/s` | `(time, ncol, lev)` |
| `sgs_buoy_flux` | Sub-grid buoyancy flux | SHOC | `K*(m/s)` | `(time, ncol, lev)` |
| `tke` | Turbulent kinetic energy | SHOC | `(m^2)/(s^2)` | `(time, ncol, lev)` |
| `inv_qc_relvar` | Inverse cloud liquid relative variance | SHOC | `(kg/kg)^2` | `(time, ncol, lev)` |
| `micro_liq_ice_exchange` | Microphysics liquid-ice exchange | P3 | `kg/kg` | `(time, ncol, lev)` |
| `micro_vap_ice_exchange` | Microphysics vapor-ice exchange | P3 | `kg/kg` | `(time, ncol, lev)` |
| `micro_vap_liq_exchange` | Microphysics vapor-liquid exchange | P3 | `kg/kg` | `(time, ncol, lev)` |
| `precip_liq_surf_mass_flux` | Precipitation liquid surface mass flux | P3 | `m/s` | `(time, ncol)` |
| `precip_ice_surf_mass_flux` | Precipitation ice surface mass flux | P3 | `m/s` | `(time, ncol)` |
| `precip_total_surf_mass_flux`| Precipitation total surface mass flux | P3 | `m/s` | `(time, ncol)` |
| `rad_heating_pdel` | Radiative heating | RRTMGP | `(Pa*K)/s` | `(time, ncol, lev)` |
| `sfc_flux_lw_dn` | Surface longwave downward flux | RRTMGP | `W/m2` | `(time, ncol)` |
| `sfc_flux_sw_net` | Surface shortwave net flux | RRTMGP | `W/m2` | `(time, ncol)` |
| `ShortwaveCloudForcing` | Shortwave cloud forcing | RRTMGP | `W/m2` | `(time, ncol)` |
| `LongwaveCloudForcing` | Longwave cloud forcing | RRTMGP | `W/m2` | `(time, ncol)` |
| `SW_flux_up_at_model_top` | Upward SW flux at model top | RRTMGP | `W/m2` | `(time, ncol)` |
| `SW_flux_dn_at_model_top` | Downward SW flux at model top | RRTMGP | `W/m2` | `(time, ncol)` |
| `LW_flux_up_at_model_top` | Upward LW flux at model top | RRTMGP | `W/m2` | `(time, ncol)` |
| `SW_flux_dn_at_model_bot` | Downward SW flux at model bottom | RRTMGP | `W/m2` | `(time, ncol)` |
| `SW_flux_up_at_model_bot` | Upward SW flux at model bottom | RRTMGP | `W/m2` | `(time, ncol)` |
| `LW_flux_dn_at_model_bot` | Downward LW flux at model bottom | RRTMGP | `W/m2` | `(time, ncol)` |
| `LW_flux_up_at_model_bot` | Upward LW flux at model bottom | RRTMGP | `W/m2` | `(time, ncol)` |
| `*_clrsky_*` | Clear-sky equivalents of the above fluxes | RRTMGP | `W/m2` | `(time, ncol)` |
| `ZonalVapFlux` | Zonal vapor flux | Diagnostics | `(kg/m)/s` | `(time, ncol)` |
| `MeridionalVapFlux` | Meridional vapor flux | Diagnostics | `(kg/m)/s` | `(time, ncol)` |
| `surface_upward_latent_heat_flux` | Surface upward latent heat flux | Coupler | `W/m2` | `(time, ncol)` |
| `surf_mom_flux` | Surface momentum flux | Coupler | `N/(m^2)` | `(time, ncol, dim2)` |
| `surf_sens_flux` | Surface sensible heat flux | Coupler | `W/(m^2)` | `(time, ncol)` |
| `surf_evap` | Surface evaporation | Coupler | `(kg/(m^2))/s` | `(time, ncol)` |
| `shoc_T_mid_tend` | Temperature tendency from SHOC | SHOC | `K/s` | `(time, ncol, lev)` |
| `p3_T_mid_tend` | Temperature tendency from P3 | P3 | `K/s` | `(time, ncol, lev)` |
| `rrtmgp_T_mid_tend` | Temperature tendency from RRTMGP | RRTMGP | `K/s` | `(time, ncol, lev)` |
| `homme_T_mid_tend` | Temperature tendency from HOMME | HOMME | `K/s` | `(time, ncol, lev)` |
| `shoc_qv_tend` | Water vapor tendency from SHOC | SHOC | `(kg/kg)/s` | `(time, ncol, lev)` |
| `p3_qv_tend` | Water vapor tendency from P3 | P3 | `(kg/kg)/s` | `(time, ncol, lev)` |
| `homme_qv_tend` | Water vapor tendency from HOMME | HOMME | `(kg/kg)/s` | `(time, ncol, lev)` |
| `PotentialTemperature_at_700hPa` | Potential temperature at 700 hPa | Diagnostics | `K` | `(time, ncol)` |
| `PotentialTemperature_at_1000hPa`| Potential temperature at 1000 hPa | Diagnostics | `K` | `(time, ncol)` |
| `omega_at_500hPa` | Vertical pressure velocity at 500 hPa | Diagnostics | `Pa/s` | `(time, ncol)` |
| `RelativeHumidity_at_700hPa` | Relative humidity at 700 hPa | Diagnostics | `1` | `(time, ncol)` |

#### 1-Hourly Instantaneous Fields

File Prefix: `${CASE}.hist`

Averaging Type: Instantaneous

Source: `scream_test9_output_inst_1hour.yaml`

*(Note: skips $t_0$ output)*

| Variable | Description | Source | Units | Dimensions |
|----------|-------------|--------|-------|------------|
| `z_mid` | Height at layer midpoints | Dynamics | `m` | `(time, ncol, lev)` |
| `p_mid` | Pressure at layer midpoints | Dynamics | `Pa` | `(time, ncol, lev)` |
| `ps` | Surface pressure | HOMME | `Pa` | `(time, ncol)` |
| `SeaLevelPressure` | Sea-level pressure | Diagnostics | `Pa` | `(time, ncol)` |
| `omega` | Vertical pressure velocity | HOMME | `Pa/s` | `(time, ncol, lev)` |
| `U` | Zonal wind | SHOC / HOMME | `m/s` | `(time, ncol, lev)` |
| `V` | Meridional wind | SHOC / HOMME | `m/s` | `(time, ncol, lev)` |
| `T_mid` | Air temperature at layer midpoints | SHOC / P3 / RRTMGP / HOMME | `K` | `(time, ncol, lev)` |
| `pbl_height` | Planetary boundary layer height | SHOC | `m` | `(time, ncol)` |
| `eddy_diff_mom` | Eddy diffusivity for momentum | SHOC | `(m^2)/s` | `(time, ncol, lev)` |
| `sgs_buoy_flux` | Sub-grid buoyancy flux | SHOC | `K*(m/s)` | `(time, ncol, lev)` |
| `tke` | Turbulent kinetic energy | SHOC | `(m^2)/(s^2)` | `(time, ncol, lev)` |
| `inv_qc_relvar` | Inverse cloud liquid relative variance | SHOC | `(kg/kg)^2` | `(time, ncol, lev)` |
| `cldfrac_liq` | Liquid cloud fraction | SHOC | `1` | `(time, ncol, lev)` |
| `cldfrac_ice` | Ice cloud fraction | CLD | `1` | `(time, ncol, lev)` |
| `cldfrac_tot_for_analysis` | Total cloud fraction (for analysis) | CLD | `1` | `(time, ncol, lev)` |
| `qc` | Cloud liquid water mixing ratio | SHOC / P3 | `kg/kg` | `(time, ncol, lev)` |
| `qv` | Water vapour mixing ratio | SHOC / P3 | `kg/kg` | `(time, ncol, lev)` |
| `nc` | Cloud droplet number concentration | P3 | `1/kg` | `(time, ncol, lev)` |
| `ni` | Cloud ice number concentration | P3 | `1/kg` | `(time, ncol, lev)` |
| `nr` | Rain drop number concentration | P3 | `1/kg` | `(time, ncol, lev)` |
| `qi` | Cloud ice mixing ratio | P3 | `kg/kg` | `(time, ncol, lev)` |
| `qm` | Ice rime mass mixing ratio | P3 | `kg/kg` | `(time, ncol, lev)` |
| `qr` | Rain mixing ratio | P3 | `kg/kg` | `(time, ncol, lev)` |
| `bm` | Ice rime volume mixing ratio | P3 | `1/kg` | `(time, ncol, lev)` |
| `diag_equiv_reflectivity` | Equivalent radar reflectivity | Diagnostics / P3 | `1` | `(time, ncol, lev)` |
| `LiqWaterPath` | Vertically integrated liquid water path | RRTMGP | `kg/(m^2)` | `(time, ncol)` |
| `IceWaterPath` | Vertically integrated ice water path | RRTMGP | `kg/(m^2)` | `(time, ncol)` |
| `RainWaterPath` | Vertically integrated rain water path | RRTMGP | `kg/(m^2)` | `(time, ncol)` |
| `RimeWaterPath` | Vertically integrated rime water path | RRTMGP | `kg/(m^2)` | `(time, ncol)` |
| `VapWaterPath` | Vertically integrated water vapour path | RRTMGP | `kg/(m^2)` | `(time, ncol)` |
| `PotentialTemperature` | Potential temperature | Diagnostics | `K` | `(time, ncol, lev)` |
| `LiqPotentialTemperature` | Liquid-water potential temperature | Diagnostics | `K` | `(time, ncol, lev)` |
| `DryStaticEnergy` | Dry static energy | Diagnostics | `(m^2)/(s^2)` | `(time, ncol, lev)` |
| `RelativeHumidity` | Relative humidity | Diagnostics | `1` | `(time, ncol, lev)` |
| `surf_radiative_T` | Surface radiative temperature | Coupler | `K` | `(time, ncol)` |
| `T_2m` | 2-m air temperature | Coupler | `K` | `(time, ncol)` |
| `qv_2m` | 2-m water vapour mixing ratio | Coupler | `kg/kg` | `(time, ncol)` |
| `wind_speed_10m` | 10-m wind speed | Coupler | `m/s` | `(time, ncol)` |

### Processed output variables

*(Note: These variables are processed and regridded for MCS tracking and spatial analyses)*

File Name Format: `${CASE}.${variable name}.[INSTANT/AVERAGE].${frequency}.${Destination grid}.YYYY-MM-DD.nc`

Directory: `/pscratch/sd/w/wcmca1/DP-SCREAM/RCE02_dx1km_gpu/remapped`

Grid: The PINACLES 600x 600 km Cartesian grid with 1-km dx

| Variable | Description | Units |
|----------|-------------|--------|
| `precip_total_surf_mass_flux`| Precipitation total surface mass flux | mm/hour |
| `LW_flux_up_at_model_top` | Upward LW flux at model top | W/m2 |
| `diag_equiv_reflectivity_max` | Vertical maximum of diag_equiv_reflectivity | - |
| `imse` | Vertically Integrated Moist Static Energy | J/m2 |

#### Data for MCS Tracking Analysis

To facilitate MCS tracking, the remapped variables described above are further processed by the script `mcs/prep_mcstrack_dpscream.py`. This script extracts individual hourly time slices, combines variables, and standardizes their names and spatial dimensions (`y`, `x`) to match the PINACLES output format.

Directory: `/pscratch/sd/w/wcmca1/DP-SCREAM/RCE02_dx1km_gpu/mcstrack`

File Name Format: `${CASE}.mcstrack.YYYY-MM-DD_HHMM.nc`

| Unified Variable | Original DP-SCREAM Variable | Units |
|------------------|-----------------------------|-------|
| `rain_rate`      | `precip_total_surf_mass_flux`| mm/h  |
| `toa_lw_up`      | `LW_flux_up_at_model_top`   | W/m2  |
| `ref`            | `diag_equiv_reflectivity_max`| -     |

* unlike the standard convention, the OLR output from this simulation is hourly average. Subsequent simulations witll write instantanous OLR output.
* the x- and y-coordinate units are meters, not lat/lon degrees.