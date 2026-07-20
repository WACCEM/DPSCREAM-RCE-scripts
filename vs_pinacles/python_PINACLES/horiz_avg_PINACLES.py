#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
horiz_avg_PINACLES.py

Reads PINACLES 2D output files (.h5) from simlinks/fields2d and
computes the horizontal domain average (arithmetic mean over x and y)
and variance for a requested variable, yielding a pure time series.

Usage:
  module load python
  conda activate dpscream_analysis
  python horiz_avg_PINACLES.py
"""

# %%

import os
import glob
import re
import numpy as np
import xarray as xr
import h5py
# %%

# =============================================================================
# User configuration
# =============================================================================
icase   = "RCE01_dx1km_600x600km"

# Variable to process. 
# Available 2D variables include: imse, LWP, IWP, RAINNC, RAINNCV, T2, qv2,
# lhf, shf, slp, u10, v10, windspeed10, windspeed_sfc, ref, pseudo-albedo,
# cp_base, cp_depth, cp_intensity, surface_lw_down, surface_lw_up,
# surface_sw_down, surface_sw_up, toa_lw_down, toa_lw_up, toa_sw_down,
# toa_sw_up, visibility, and height-level fields (e.g., T_100.0, qv_500.0, ...)
varname = "imse"

in_dir  = f"/pscratch/sd/w/wcmca1/PINACLES/rce/{icase}/simlinks/fields2d"
out_dir = f"/pscratch/sd/w/wcmca1/PINACLES/rce/{icase}/havg"

# File minute pattern for specifying frequency.
# Use "00m" for hourly data (only read files on the hour).
# Use "*m" to read all available frequencies (e.g., every 10 minutes).
minute_pattern = "00m"

# Day range to process (inclusive, 0-based integer day numbers matching the
# leading digits in filenames, e.g. 00d-HHh-... → day 0).
day_start = 0
day_end   = 44   # adjust to the last available simulation day

# %%

# =============================================================================
# End user configuration
# =============================================================================

def parse_hour(filename):
    """Return the integer hour from a filename like '01d-03h-00m-00s-000ms.h5'."""
    m = re.match(r'^\d+d-(\d+)h-', os.path.basename(filename))
    return int(m.group(1)) if m else None


# %%

os.makedirs(out_dir, exist_ok=True)

print(f"\n{'='*60}")
print(f"Processing variable : {varname}")
print(f"Input dir : {in_dir}")
print(f"Output dir: {out_dir}")
print(f"Day range : {day_start} – {day_end}")

all_files = sorted(glob.glob(os.path.join(in_dir, f"*-{minute_pattern}-*.h5")))
if not all_files:
    raise FileNotFoundError(f"No .h5 files found in {in_dir}")

# Find valid files within the day range
infiles = []
for fpath in all_files:
    basename = os.path.basename(fpath)
    m = re.match(r'^(\d+)d-', basename)
    if m:
        iday = int(m.group(1))
        if day_start <= iday <= day_end:
            infiles.append(fpath)

print(f"\nFound {len(infiles)} input file(s) in day range.")

if not infiles:
    raise ValueError("No files found within the specified day range.")


# %%

invarname = varname

# Read attributes from the first file
with h5py.File(infiles[0], 'r') as f0:
    if invarname not in f0:
        if varname == "toa_lw_up" and "LW_UP_TOA" in f0:
            invarname = "LW_UP_TOA"
            print("Variable 'toa_lw_up' not found in input. Reading 'LW_UP_TOA' instead.")
        else:
            raise KeyError(
                f"Variable '{invarname}' not found in {infiles[0]}. "
                f"Available keys: {list(f0.keys())}"
            )
    var_attrs = dict(f0[invarname].attrs)

# Remove HDF5-internal attributes that do not transfer cleanly to NetCDF
for _key in ('DIMENSION_LIST', 'CLASS', 'NAME', 'REFERENCE_LIST'):
    var_attrs.pop(_key, None)

time_list = []
havg_list = []
hvar_list = []

print("  Computing horizontal domain average ...")
for i, fpath in enumerate(infiles):
    if i > 0 and i % 100 == 0:
        print(f"    Processing file {i}/{len(infiles)}: {os.path.basename(fpath)}")
        
    with h5py.File(fpath, 'r') as hf:
        t = hf['time'][...]      # shape (1,)  — seconds since sim start
        v = hf[invarname][...]     # shape (1, ny, nx) or (ny, nx) depending on field
        
        # Squeeze the time dimension if it exists
        if v.ndim == 3 and v.shape[0] == 1:
            v_2d = v[0, ...]
        else:
            v_2d = v
            
        time_list.append(float(t[0]))
        havg_list.append(np.nanmean(v_2d))
        hvar_list.append(np.nanvar(v_2d))

time_arr = np.array(time_list) / 3600.0   # Convert seconds to hours
havg_arr = np.array(havg_list, dtype=np.float32)
hvar_arr = np.array(hvar_list, dtype=np.float32)

havg_attrs = dict(var_attrs)
havg_attrs['description'] = 'Horizontal domain average over x and y'

hvar_attrs = dict(var_attrs)
hvar_attrs['description'] = 'Horizontal domain variance over x and y'
if 'units' in hvar_attrs and hvar_attrs['units']:
    hvar_attrs['units'] = f"({hvar_attrs['units']})^2"

ds_havg = xr.Dataset(
    {
        varname: xr.DataArray(
            havg_arr, 
            dims=['time'], 
            coords={'time': time_arr},
            attrs=havg_attrs
        ),
        f"{varname}_var": xr.DataArray(
            hvar_arr, 
            dims=['time'], 
            coords={'time': time_arr},
            attrs=hvar_attrs
        )
    },
    coords={
        'time': xr.DataArray(
            time_arr,
            dims=['time'],
            attrs={
                'units': 'hours since 2000-01-01 00:00:00.000000',
                'calendar': 'noleap',
                'long_name': 'time',
            }
        )
    },
    attrs={
        'case': icase,
        'variable': varname,
        'processing': 'horizontal domain average (mean over x and y) and variance',
        'source_dir': in_dir,
    }
)

out_tag = f"day{day_start:02d}_to_{day_end:02d}"
havg_out = os.path.join(
    out_dir,
    f"{icase}.{varname}.havg.{out_tag}.nc"
)
ds_havg.to_netcdf(havg_out, encoding={'time': {'_FillValue': None}})
print(f"  Saved domain-average: {havg_out}")

print(f"\n{'='*60}")
print("Done.")

# %%
