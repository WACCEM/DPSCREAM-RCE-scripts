#!/usr/bin/env python
# prep_mcstrack_dpscream.py
#
# Process sub-daily DP-SCREAM remapped output files for MCS tracking software.
# Combines 'precip_total_surf_mass_flux', 'LW_flux_up_at_model_top', and 
# 'diag_equiv_reflectivity_max' into single-time NetCDF files.
# Renames variables to match PINACLES standard: rain_rate, toa_lw_up, ref.
# Sets up spatial coordinate variables x, y, lat, lon with dimensions (y, x).
#
# Usage:
#   module load python
#   conda activate dpscream_analysis
#   python prep_mcstrack_dpscream.py

# %%
import os
import glob
import re
import datetime
import xarray as xr

# %%
# =============================================================================
# CONFIGURATION
# =============================================================================

icase   = "RCE02_dx1km_gpu"
in_dir  = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/remapped"
out_dir = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/mcstrack"

# Day range to process
day_start = 0
day_end   = 43

# Variables and their file name patterns
var_patterns = {
    "rain_rate": "precip_total_surf_mass_flux",
    "toa_lw_up": "LW_flux_up_at_model_top",
    "ref":       "diag_equiv_reflectivity_max"
}

# Base time for filename and coordinates (assuming idealized runs start at 2000-01-01)
base_time = datetime.datetime(2000, 1, 1, 0, 0, 0)

# %%
# =============================================================================

# Setup
os.makedirs(out_dir, exist_ok=True)

print(f"Input dir : {in_dir}")
print(f"Output dir: {out_dir}")
print(f"Day range : {day_start} – {day_end}")

# Find all dates available by looking at the rain_rate variable
sample_var = var_patterns["rain_rate"]
all_sample_files = sorted(glob.glob(os.path.join(in_dir, f"{icase}.{sample_var}.*.nc")))

if not all_sample_files:
    raise FileNotFoundError(f"No files found in {in_dir} for variable {sample_var}")

# %%
# Regex to extract date YYYY-MM-DD from filename
date_regex = re.compile(r'(\d{4}-\d{2}-\d{2})\.nc$')

# Main loop
for fpath in all_sample_files:
    m = date_regex.search(fpath)
    if not m:
        continue
    date_str = m.group(1)
    
    # Calculate simulation day
    file_dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    iday = (file_dt - base_time).days
    
    if iday < day_start or iday > day_end:
        continue

    print(f"\n{'='*55}")
    print(f"Day {iday:02d} ({date_str}): processing")

    # Load the datasets for this date with decode_times=False 
    # to preserve raw numerical time values (hours since 2000-01-01).
    ds_dict = {}
    valid_time = True
    for out_var, in_var in var_patterns.items():
        pat = os.path.join(in_dir, f"{icase}.{in_var}.*{date_str}.nc")
        files = glob.glob(pat)
        if not files:
            print(f"  Warning: Missing {in_var} file for {date_str}")
            valid_time = False
            break
        ds_dict[out_var] = xr.open_dataset(files[0], decode_times=False)
    
    if not valid_time:
        for ds in ds_dict.values():
            ds.close()
        continue
        
    # Process each time slice in the day's files (usually 24 hourly slices)
    # Extract times from the INSTANT variable ('ref') so the output filename
    # accurately reflects the end of the averaging interval (e.g. 0100.nc instead of 0000.nc)
    times = ds_dict["ref"]['time'].values
    
    for i, t_val in enumerate(times):
        t_hours = float(t_val)
        dt_obj = base_time + datetime.timedelta(hours=t_hours)
        
        # Build dataset for this single time slice
        ds_out = xr.Dataset()
        
        for out_var, in_var in var_patterns.items():
            # Extract the 2D slice for this time
            da = ds_dict[out_var][in_var].isel(time=i)
            # Re-add the time dimension so it has size 1
            da = da.expand_dims('time')
            
            # The remapped DP-SCREAM files use ('lat', 'lon') dimensions,
            # but PINACLES mcstrack script uses ('y', 'x') as primary dimensions.
            # We rename the dimensions to align with the required PINACLES format.
            da = da.rename({'lat': 'y', 'lon': 'x'})
            
            # Drop the original time coordinate to prevent xarray from aligning
            # slightly different time values between AVERAGE and INSTANT variables
            # (e.g., 960 vs 961) which would otherwise result in NaNs.
            if 'time' in da.coords:
                da = da.drop_vars('time')
            
            ds_out[out_var] = da
            
            # Update specific attributes for uniformity
            if out_var == "rain_rate":
                ds_out[out_var].attrs["long_name"] = "hourly precipitation rate"
                ds_out[out_var].attrs["units"] = "mm/h" # precip_total_surf_mass_flux is already mm/hour
            elif out_var == "toa_lw_up":
                ds_out[out_var].attrs["long_name"] = "Upward longwave flux at TOA"
                ds_out[out_var].attrs["units"] = "W/m2"
            elif out_var == "ref":
                ds_out[out_var].attrs["long_name"] = "maximum equivalent reflectivity"
        
        # Assign unified coordinate variables explicitly
        # We rename the 1D coordinate arrays identically to their new dimensions
        ds_out = ds_out.assign_coords({
            'x': ds_dict["rain_rate"]['x'].rename({'lon': 'x'}),
            'y': ds_dict["rain_rate"]['y'].rename({'lat': 'y'}),
            'lat': ds_dict["rain_rate"]['lat'].rename({'lat': 'y'}),
            'lon': ds_dict["rain_rate"]['lon'].rename({'lon': 'x'}),
        })
        
        # Set up the unlimited time coordinate
        ds_out = ds_out.assign_coords({
            'time': xr.DataArray(
                [t_hours],
                dims=['time'],
                attrs={
                    'units': 'hours since 2000-01-01 00:00:00.000000',
                    'calendar': 'noleap',
                    'long_name': 'time'
                }
            )
        })
        
        # Global attributes
        ds_out.attrs = {
            'case': icase,
            'description': 'Single time-sample DP-SCREAM remapped 2D fields for MCS tracking',
            'source_dir': in_dir,
            'rain_rate_note': 'The variable rain_rate is derived from precip_total_surf_mass_flux (an AVERAGE output), representing the average precipitation rate over the previous hour.'
        }
        
        # Filename incorporates year, month, day, hour, and minute
        fname = f"{icase}.mcstrack.{dt_obj.strftime('%Y-%m-%d_%H%M')}.nc"
        out_file = os.path.join(out_dir, fname)
        
        ds_out.to_netcdf(
            out_file,
            mode='w',
            unlimited_dims=['time'],
            encoding={
                'time': {'_FillValue': None},
                'x': {'_FillValue': None},
                'y': {'_FillValue': None},
                'lat': {'_FillValue': None},
                'lon': {'_FillValue': None}
            }
        )
        print(f"  Written : {out_file}")

    # Close the input datasets
    for ds in ds_dict.values():
        ds.close()

print("\nDone.")

# %%
