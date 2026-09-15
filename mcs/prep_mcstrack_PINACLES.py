#!/usr/bin/env python
# prep_mcstrack.py
#
# Process sub-daily PINACLES output files for MCS tracking software.
# Combines 'rain_rate', 'toa_lw_up', and 'ref' into single-time NetCDF files.
# Calculates rain_rate from accumulated RAINNC.
# Sets up spatial coordinate variables x, y (meters) and lat, lon (degrees).
#
# Usage:
#   module load python
#   conda activate pinacles_share
#   python prep_mcstrack.py
#
# Environment: pinacles_share (/global/common/software/m1867/python/pinacles_share)
# or dpscream_analysis
# %%
import os
import glob
import re
import datetime
import numpy as np
import xarray as xr
import h5py
# %%
# =============================================================================
# CONFIGURATION
# =============================================================================

icase   = "RCE00_dx1km_600x600km"

in_dir  = (
    f"/pscratch/sd/w/wcmca1/PINACLES/"
    f"{icase}/simlinks/fields2d"
)
out_dir = f"/pscratch/sd/w/wcmca1/PINACLES/{icase}/mcstrack"

# File minute pattern for specifying frequency.
# Use "*m" to read all available frequencies (e.g., hourly).
minute_pattern = "*m"

# Day range to process
day_start = 0
day_end   = 59

# Base time for filename and coordinates (assuming idealized runs start at 2000-01-01)
base_time = datetime.datetime(2000, 1, 1, 0, 0, 0)

# Earth radius in meters (for translating Cartesian x,y to lat,lon)
Re = 6371229.0

# %%
# helpfer function
# =============================================================================
def parse_hour(filename):
    m = re.match(r'^\d+d-(\d+)h-', os.path.basename(filename))
    return int(m.group(1)) if m else None


# %%
# Setup
os.makedirs(out_dir, exist_ok=True)

print(f"Input dir : {in_dir}")
print(f"Output dir: {out_dir}")
print(f"Day range : {day_start} – {day_end}")

all_matching_pattern = os.path.join(in_dir, f"*-*-{minute_pattern}-*.h5")
all_matching_files = sorted(glob.glob(all_matching_pattern))

if not all_matching_files:
    raise FileNotFoundError(f"No .h5 files found in {in_dir} matching {minute_pattern}")


# %%
# Read coords from the first available file
with h5py.File(all_matching_files[0], 'r') as f0:
    x_vals = f0['X'][...]
    y_vals = f0['Y'][...]
    
    # Read attributes for standard variables if available
    attr_cache = {}
    for invar, outvar in [("RAINNC", "rain_rate"), ("LW_UP_TOA", "toa_lw_up"), ("ref", "ref")]:
        if invar in f0:
            attr_cache[outvar] = dict(f0[invar].attrs)
        elif outvar in f0:
            attr_cache[outvar] = dict(f0[outvar].attrs)
        else:
            attr_cache[outvar] = {}


# %%

# Clean HDF5-internal attributes that do not transfer cleanly to NetCDF
for outvar, attrs in attr_cache.items():
    for _key in ('DIMENSION_LIST', 'CLASS', 'NAME', 'REFERENCE_LIST'):
        attrs.pop(_key, None)

# Update specific variable attributes
if "rain_rate" in attr_cache:
    attr_cache["rain_rate"]["units"] = "mm/h"
    attr_cache["rain_rate"]["long_name"] = "hourly precipitation rate"
if "toa_lw_up" in attr_cache:
    attr_cache["toa_lw_up"]["units"] = "W/m2"
    attr_cache["toa_lw_up"]["long_name"] = "Upward longwave flux at TOA"

# Prepare lat/lon arrays (domain center assumed at 0 N, 0 E)
# 1D coordinates since the grid is regular in x and y.
lat_vals = np.degrees(y_vals / Re)
lon_vals = np.degrees(x_vals / Re)


# %%

# State for rain rate calculation
prev_file_cache = {"fpath": None, "t": None, "rainnc": None}

for iday in range(day_start, day_end + 1):
    day_files = sorted(glob.glob(os.path.join(in_dir, f"{iday:02d}d-*-{minute_pattern}-*.h5")))

    if not day_files:
        continue
    
    print(f"\n{'='*55}")
    print(f"Day {iday:02d}: processing {len(day_files)} file(s)")

    for fpath in day_files:
        with h5py.File(fpath, 'r') as hf:
            t_sec = float(hf['time'][...][0])
            
            # Calculate date for the filename
            dt_obj = base_time + datetime.timedelta(seconds=t_sec)
            
            # --- read variables ---
            # 1. rain_rate
            if "RAINNC" in hf:
                rainnc_current = hf["RAINNC"][...]
                
                idx = all_matching_files.index(fpath)
                if idx == 0:
                    rain_rate = np.zeros_like(rainnc_current)
                else:
                    prev_fpath = all_matching_files[idx - 1]
                    if prev_file_cache["fpath"] == prev_fpath:
                        prev_t = prev_file_cache["t"]
                        prev_rainnc = prev_file_cache["rainnc"]
                    else:
                        with h5py.File(prev_fpath, 'r') as hf_prev:
                            prev_t = float(hf_prev['time'][...][0])
                            prev_rainnc = hf_prev["RAINNC"][...]
                            
                    dt_hours = (t_sec - prev_t) / 3600.0
                    if dt_hours > 0:
                        rain_rate = (rainnc_current - prev_rainnc) / dt_hours
                    else:
                        rain_rate = np.zeros_like(rainnc_current)
                
                prev_file_cache["fpath"] = fpath
                prev_file_cache["t"] = t_sec
                prev_file_cache["rainnc"] = rainnc_current
            else:
                rain_rate = np.zeros((1, len(y_vals), len(x_vals)))
            
            # 2. toa_lw_up
            if "LW_UP_TOA" in hf:
                toa_lw_up = hf["LW_UP_TOA"][...]
            elif "toa_lw_up" in hf:
                toa_lw_up = hf["toa_lw_up"][...]
            else:
                toa_lw_up = np.zeros((1, len(y_vals), len(x_vals)))

            # 3. ref
            if "ref" in hf:
                ref = hf["ref"][...]
            elif "REFL_10CM" in hf:
                ref = hf["REFL_10CM"][...]
            else:
                ref = np.zeros((1, len(y_vals), len(x_vals)))

        # Build Xarray Dataset
        t_hours = t_sec / 3600.0
        time_arr = np.array([t_hours])
        
        # Ensure arrays have correct dimensions (1, y, x) for UNLIMITED time dim
        if rain_rate.ndim == 2: rain_rate = np.expand_dims(rain_rate, axis=0)
        if toa_lw_up.ndim == 2: toa_lw_up = np.expand_dims(toa_lw_up, axis=0)
        if ref.ndim == 2: ref = np.expand_dims(ref, axis=0)

        ds = xr.Dataset(
            {
                "rain_rate": xr.DataArray(
                    rain_rate, dims=['time', 'y', 'x'], attrs=attr_cache.get("rain_rate", {})
                ),
                "toa_lw_up": xr.DataArray(
                    toa_lw_up, dims=['time', 'y', 'x'], attrs=attr_cache.get("toa_lw_up", {})
                ),
                "ref": xr.DataArray(
                    ref, dims=['time', 'y', 'x'], attrs=attr_cache.get("ref", {})
                )
            },
            coords={
                'time': xr.DataArray(
                    time_arr, dims=['time'],
                    attrs={
                        'units': 'hours since 2000-01-01 00:00:00.000000',
                        'calendar': 'noleap',
                        'long_name': 'time'
                    }
                ),
                'x': xr.DataArray(
                    x_vals, dims=['x'], attrs={'units': 'm', 'long_name': 'x coordinate'}
                ),
                'y': xr.DataArray(
                    y_vals, dims=['y'], attrs={'units': 'm', 'long_name': 'y coordinate'}
                ),
                'lat': xr.DataArray(
                    lat_vals, dims=['y'], attrs={'units': 'degrees_north', 'long_name': 'latitude', 'standard_name': 'latitude'}
                ),
                'lon': xr.DataArray(
                    lon_vals, dims=['x'], attrs={'units': 'degrees_east', 'long_name': 'longitude', 'standard_name': 'longitude'}
                )
            },
            attrs={
                'case': icase,
                'description': 'Single time-sample PINACLES 2D fields for MCS tracking',
                'rain_rate_note': 'The variable rain_rate at time t represents the accumulated rain between the previous output time (t-1) and current output time (t).',
                'source_dir': in_dir,
            }
        )
        
        # Filename incorporates year, month, day, hour, and minute
        # Example format: icase.mcstrack.YYYY-MM-DD_HHMM.nc
        fname = f"{icase}.mcstrack.{dt_obj.strftime('%Y-%m-%d_%H%M')}.nc"
        out_file = os.path.join(out_dir, fname)
        
        ds.to_netcdf(
            out_file, 
            mode='w', 
            unlimited_dims=['time'],
            encoding={
                'time': {'_FillValue': None},
                'x': {'_FillValue': None},
                'y': {'_FillValue': None},
                'lat': {'_FillValue': None},
                'lon': {'_FillValue': None},
                'rain_rate': {'dtype': 'float32'},
                'toa_lw_up': {'dtype': 'float32'},
                'ref': {'dtype': 'float32'},
            }
        )
        print(f"  Written : {out_file}")
        ds.close()

print("\nDone.")

# %%
