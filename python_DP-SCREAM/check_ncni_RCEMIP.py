#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calculate and plot time-dimension statistics of variable column stats (max, min, etc.)
from DP-SCREAM output to verify RCEMIP protocol customizations.

Usage (after activating the dpscream_analysis conda environment):
    module load python
    conda activate dpscream_analysis
    python check_ncni_RCEMIP.py
"""
# %%

import os
import glob
import sys
import numpy as np
import pandas as pd
import xarray as xr

import matplotlib
# Use the non-interactive Agg backend only when running as a plain script
# (batch/login node).  In interactive sessions (IPython, Jupyter) the
# default inline/GUI backend is kept so plt.show() renders the figure.
_interactive = hasattr(sys, 'ps1') or 'ipykernel' in sys.modules
if not _interactive:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt

# %%
# User configuration
# ---------------------------------------------------------------------------

icase = "RCE09_dx3km_gpu"
varname = "nc_m3_level_79"
stats_type = "INSTANT"
frequency = "nhours_x1"

in_dir = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/cat_raw"

# Date range to load (inclusive, YYYY-MM-DD)
ts_start = "2000-02-01"
ts_end   = "2000-02-01"

stat_type = "raw" # options: "min", "max", "mean", "raw"; 
#"raw"" requires to plot an instant value for the specified time

out_dir = "" # Leave empty to save in the same directory as in_dir
outfile = None # Set to None to auto-generate based on case and varname

# ---------------------------------------------------------------------------
# End user configuration
# ---------------------------------------------------------------------------
# %%
# Build file list for the requested date range
start_date = np.datetime64(ts_start, 'D')
end_date   = np.datetime64(ts_end,   'D')
date_range = np.arange(start_date,
                       end_date + np.timedelta64(1, 'D'),
                       dtype='datetime64[D]')
date_strs  = {str(d) for d in date_range}

file_prefix = f"{icase}.{varname}.{stats_type}.{frequency}."
infiles = sorted([
    f for f in glob.glob(os.path.join(in_dir, f"{file_prefix}*.nc"))
    if os.path.basename(f)[len(file_prefix):len(file_prefix) + 10] in date_strs
])

print(f"Case      : {icase}")
print(f"Variable  : {varname}")
print(f"Period    : {ts_start}  to  {ts_end}")
print(f"\nFound {len(infiles)} input file(s):")
for fp in infiles:
    print(f"  {fp}")

if len(infiles) == 0:
    raise FileNotFoundError(
        f"No input files found in '{in_dir}' matching prefix '{file_prefix}'"
        f" for the requested date range.")

print("\nLoading and concatenating files ...")
try:
    _time_coder = xr.coders.CFDatetimeCoder(use_cftime=False)
    ds = xr.open_mfdataset(infiles, combine="by_coords", decode_times=_time_coder)
    # Trigger time decoding to detect calendar errors early
    _ = ds['time'].values[0]
except ValueError:
    # Non-standard calendar (e.g. noleap): decode with cftime first, then
    # convert to standard numpy datetime64 by treating the dates as Gregorian
    # (safe for RCE simulations – no leap-day ambiguity in the time series).
    print("  Non-standard calendar detected; decoding with cftime and "
          "converting to datetime64 ...")
    _time_coder = xr.coders.CFDatetimeCoder(use_cftime=True)
    ds = xr.open_mfdataset(infiles, combine="by_coords", decode_times=_time_coder)
    _t_pd = pd.DatetimeIndex([
        pd.Timestamp(t.year, t.month, t.day, t.hour, t.minute, t.second)
        for t in ds['time'].values
    ])
    ds = ds.assign_coords(time=_t_pd)

if varname not in ds:
    raise ValueError(f"Variable '{varname}' not found in the dataset. Available variables: {list(ds.data_vars)}")

# %%
# Extract the variable data
data = ds[varname]
tind = 0 #time index for plot; when stat_type = None


# %%

if "time" not in data.dims:
    raise ValueError(f"Variable '{varname}' does not have a 'time' dimension. Dimensions found: {data.dims}")
    
print(f"Calculating {stat_type} along the 'time' dimension...")
if stat_type == "mean":
    stat_data = data.mean(dim="time", skipna=True)
elif stat_type == "max":
    stat_data = data.max(dim="time", skipna=True)
elif stat_type == "min":
    stat_data = data.min(dim="time", skipna=True)
elif stat_type == "raw":
    stat_data = data.isel(time=tind)
else:
    raise ValueError(f"Unknown stat_type: {stat_type}")    

if "ncol" not in stat_data.dims:
    raise ValueError(f"Resulting data does not have an 'ncol' dimension. Dimensions found: {stat_data.dims}")

# For x-axis
if 'ncol' in ds.coords:
    ncol_values = ds['ncol'].values
else:
    ncol_values = np.arange(ds.sizes['ncol'])

# Get units if available
units = data.attrs.get("units", "")
unit_str = f" [{units}]" if units else ""

# %%
# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
print("Generating plot...")
savefig = True

fig = plt.figure(figsize=(12, 6))

# Use scatter plot since ncol is unstructured and points aren't logically connected as a line
plt.scatter(ncol_values, stat_data.values, s=4, alpha=0.6, color='b', marker='o')

plt.xlabel('Model Grid Column (ncol)', fontsize=12)
plt.ylabel(f"{varname} ({stat_type} over time){unit_str}", fontsize=12)
plt.ticklabel_format(style='sci', axis='y', scilimits=(0,0))

title_var = varname.replace('_', ' ')
plt.title(f"Time {stat_type.capitalize()} of {title_var} across Atmospheric Columns\n({icase} | {ts_start} to {ts_end})", fontsize=14)
plt.grid(True, linestyle='--', alpha=0.7)

# Optional: Set y-axis lower limit to 0 if we know values should be positive
if "nc" in varname or "ni" in varname:
    plt.ylim(bottom=0)

plt.tight_layout()

# Determine output filename
if outfile is None:
    if not out_dir:
        out_dir = in_dir
        if not out_dir:
            out_dir = "."
            
    date_range_str = f"{ts_start}_to_{ts_end}"
    final_outfile = os.path.join(out_dir, f"{icase}.{varname}.{date_range_str}_time_{stat_type}.png")
else:
    if not out_dir:
        out_dir = "."
    final_outfile = os.path.join(out_dir, outfile)

if savefig:
    os.makedirs(out_dir, exist_ok=True)
    fig.savefig(final_outfile, dpi=300)
    print(f"Plot saved successfully to: {final_outfile}")

plt.show()

if not _interactive:
    plt.close(fig)

ds.close()

# %%
