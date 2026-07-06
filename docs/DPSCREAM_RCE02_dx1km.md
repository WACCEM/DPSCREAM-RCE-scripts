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

## Output Variables

Model outputs are controlled by two YAML files located in `run_scripts/yaml_files/`. Both streams output every **1 hour**.

Additionally, some variables have been remapped from the native unstructured grid to the Cartesian grid used by the "PINACLES" model for analysis. This Cartesian grid features a 1-km grid spacing ()"PINACLES_YX_dx1km" grid). These remapped files are saved under the `remapped/` subdirectory. The regridding process was performed by the script `python_DP-SCREAM/regrid_DPSCREAM.py`.

### Raw history files

Directory: `/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE02_dx1km_gpu/run`

#### 1-Hourly Average Fields

File Prefix:*`${CASE}.hist`

Averaging Type: Average

Source: `scream_test9_output_avg_1hour.yaml`


| Variable | Description | Source | Units |
|----------|-------------|--------|-------|
| `z_mid` | Height at layer midpoints | Dynamics | `m` |
| `p_mid` | Pressure at layer midpoints | Dynamics | `Pa` |
| `ps` | Surface pressure | HOMME | `Pa` |
| `SeaLevelPressure` | Sea-level pressure | Diagnostics | `Pa` |
| `pbl_height` | Planetary boundary layer height | SHOC | `m` |
| `eddy_diff_mom` | Eddy diffusivity for momentum | SHOC | `(m^2)/s` |
| `sgs_buoy_flux` | Sub-grid buoyancy flux | SHOC | `K*(m/s)` |
| `tke` | Turbulent kinetic energy | SHOC | `(m^2)/(s^2)` |
| `inv_qc_relvar` | Inverse cloud liquid relative variance | SHOC | `(kg/kg)^2` |
| `micro_liq_ice_exchange` | Microphysics liquid-ice exchange | P3 | `kg/kg` |
| `micro_vap_ice_exchange` | Microphysics vapor-ice exchange | P3 | `kg/kg` |
| `micro_vap_liq_exchange` | Microphysics vapor-liquid exchange | P3 | `kg/kg` |
| `precip_liq_surf_mass_flux` | Precipitation liquid surface mass flux | P3 | `m/s` |
| `precip_ice_surf_mass_flux` | Precipitation ice surface mass flux | P3 | `m/s` |
| `precip_total_surf_mass_flux`| Precipitation total surface mass flux | P3 | `m/s` |
| `rad_heating_pdel` | Radiative heating | RRTMGP | `(Pa*K)/s` |
| `sfc_flux_lw_dn` | Surface longwave downward flux | RRTMGP | `W/m2` |
| `sfc_flux_sw_net` | Surface shortwave net flux | RRTMGP | `W/m2` |
| `ShortwaveCloudForcing` | Shortwave cloud forcing | RRTMGP | `W/m2` |
| `LongwaveCloudForcing` | Longwave cloud forcing | RRTMGP | `W/m2` |
| `SW_flux_up_at_model_top` | Upward SW flux at model top | RRTMGP | `W/m2` |
| `SW_flux_dn_at_model_top` | Downward SW flux at model top | RRTMGP | `W/m2` |
| `LW_flux_up_at_model_top` | Upward LW flux at model top | RRTMGP | `W/m2` |
| `SW_flux_dn_at_model_bot` | Downward SW flux at model bottom | RRTMGP | `W/m2` |
| `SW_flux_up_at_model_bot` | Upward SW flux at model bottom | RRTMGP | `W/m2` |
| `LW_flux_dn_at_model_bot` | Downward LW flux at model bottom | RRTMGP | `W/m2` |
| `LW_flux_up_at_model_bot` | Upward LW flux at model bottom | RRTMGP | `W/m2` |
| `*_clrsky_*` | Clear-sky equivalents of the above fluxes | RRTMGP | `W/m2` |
| `ZonalVapFlux` | Zonal vapor flux | Diagnostics | `(kg/m)/s` |
| `MeridionalVapFlux` | Meridional vapor flux | Diagnostics | `(kg/m)/s` |
| `surface_upward_latent_heat_flux` | Surface upward latent heat flux | Coupler | `W/m2` |
| `surf_mom_flux` | Surface momentum flux | Coupler | `N/(m^2)` |
| `surf_sens_flux` | Surface sensible heat flux | Coupler | `W/(m^2)` |
| `surf_evap` | Surface evaporation | Coupler | `(kg/(m^2))/s` |
| `shoc_T_mid_tend` | Temperature tendency from SHOC | SHOC | `K/s` |
| `p3_T_mid_tend` | Temperature tendency from P3 | P3 | `K/s` |
| `rrtmgp_T_mid_tend` | Temperature tendency from RRTMGP | RRTMGP | `K/s` |
| `homme_T_mid_tend` | Temperature tendency from HOMME | HOMME | `K/s` |
| `shoc_qv_tend` | Water vapor tendency from SHOC | SHOC | `(kg/kg)/s` |
| `p3_qv_tend` | Water vapor tendency from P3 | P3 | `(kg/kg)/s` |
| `homme_qv_tend` | Water vapor tendency from HOMME | HOMME | `(kg/kg)/s` |
| `PotentialTemperature_at_700hPa` | Potential temperature at 700 hPa | Diagnostics | `K` |
| `PotentialTemperature_at_1000hPa`| Potential temperature at 1000 hPa | Diagnostics | `K` |
| `omega_at_500hPa` | Vertical pressure velocity at 500 hPa | Diagnostics | `Pa/s` |
| `RelativeHumidity_at_700hPa` | Relative humidity at 700 hPa | Diagnostics | `1` |

#### 1-Hourly Instantaneous Fields

File Prefix: `${CASE}.hist`

Averaging Type: Instantaneous

Source: `scream_test9_output_inst_1hour.yaml`

*(Note: skips $t_0$ output)*

| Variable | Description | Source | Units |
|----------|-------------|--------|-------|
| `z_mid` | Height at layer midpoints | Dynamics | `m` |
| `p_mid` | Pressure at layer midpoints | Dynamics | `Pa` |
| `ps` | Surface pressure | HOMME | `Pa` |
| `SeaLevelPressure` | Sea-level pressure | Diagnostics | `Pa` |
| `omega` | Vertical pressure velocity | HOMME | `Pa/s` |
| `U` | Zonal wind | SHOC / HOMME | `m/s` |
| `V` | Meridional wind | SHOC / HOMME | `m/s` |
| `T_mid` | Air temperature at layer midpoints | SHOC / P3 / RRTMGP / HOMME | `K` |
| `pbl_height` | Planetary boundary layer height | SHOC | `m` |
| `eddy_diff_mom` | Eddy diffusivity for momentum | SHOC | `(m^2)/s` |
| `sgs_buoy_flux` | Sub-grid buoyancy flux | SHOC | `K*(m/s)` |
| `tke` | Turbulent kinetic energy | SHOC | `(m^2)/(s^2)` |
| `inv_qc_relvar` | Inverse cloud liquid relative variance | SHOC | `(kg/kg)^2` |
| `cldfrac_liq` | Liquid cloud fraction | SHOC | `1` |
| `cldfrac_ice` | Ice cloud fraction | CLD | `1` |
| `cldfrac_tot_for_analysis` | Total cloud fraction (for analysis) | CLD | `1` |
| `qc` | Cloud liquid water mixing ratio | SHOC / P3 | `kg/kg` |
| `qv` | Water vapour mixing ratio | SHOC / P3 | `kg/kg` |
| `nc` | Cloud droplet number concentration | P3 | `1/kg` |
| `ni` | Cloud ice number concentration | P3 | `1/kg` |
| `nr` | Rain drop number concentration | P3 | `1/kg` |
| `qi` | Cloud ice mixing ratio | P3 | `kg/kg` |
| `qm` | Ice rime mass mixing ratio | P3 | `kg/kg` |
| `qr` | Rain mixing ratio | P3 | `kg/kg` |
| `bm` | Ice rime volume mixing ratio | P3 | `1/kg` |
| `diag_equiv_reflectivity` | Equivalent radar reflectivity | Diagnostics / P3 | `1` |
| `LiqWaterPath` | Vertically integrated liquid water path | RRTMGP | `kg/(m^2)` |
| `IceWaterPath` | Vertically integrated ice water path | RRTMGP | `kg/(m^2)` |
| `RainWaterPath` | Vertically integrated rain water path | RRTMGP | `kg/(m^2)` |
| `RimeWaterPath` | Vertically integrated rime water path | RRTMGP | `kg/(m^2)` |
| `VapWaterPath` | Vertically integrated water vapour path | RRTMGP | `kg/(m^2)` |
| `PotentialTemperature` | Potential temperature | Diagnostics | `K` |
| `LiqPotentialTemperature` | Liquid-water potential temperature | Diagnostics | `K` |
| `DryStaticEnergy` | Dry static energy | Diagnostics | `(m^2)/(s^2)` |
| `RelativeHumidity` | Relative humidity | Diagnostics | `1` |
| `surf_radiative_T` | Surface radiative temperature | Coupler | `K` |
| `T_2m` | 2-m air temperature | Coupler | `K` |
| `qv_2m` | 2-m water vapour mixing ratio | Coupler | `kg/kg` |
| `wind_speed_10m` | 10-m wind speed | Coupler | `m/s` |

### Processed and Regridded variables for MCS tracking and spatial anlyses

File Name Format: `${CASE}.${variable name}.[INSTANT/AVERAGE].${frequency}.${Destination grid}.YYYY-MM-DD.nc`

DIrectory: `/pscratch/sd/w/wcmca1/DP-SCREAM/RCE02_dx1km_gpu/remapped`

Grid: The PINACLES 600x 600 km Cartesian grid with 1-km dx

| Variable | Description | Units |
|----------|-------------|--------|
| `precip_total_surf_mass_flux`| Precipitation total surface mass flux | mm/hour |
| `LW_flux_up_at_model_top` | Upward LW flux at model top | W/m2 |
| `diag_equiv_reflectivity_max` | Vertical maximum of diag_equiv_reflectivity | - |
| `imse` | Vertically Integrated Moist Static Energy | J/m2 |
