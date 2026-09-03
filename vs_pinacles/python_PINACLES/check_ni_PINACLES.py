#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calculate and plot time-dimension statistics of variable column stats (max, min, etc.)
from PINACLES output to verify RCEMIP protocol customizations.

Usage (after activating the dpscream_analysis conda environment):
    module load python
    conda activate dpscream_analysis
    python check_ni_PINACLES.py
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

icase = "RCE03_150x150_1km"
varname = "qnc_1900.0_m3"

in_dir = f"/pscratch/sd/w/wcmca1/PINACLES/{icase}/cat_raw"

# Simulation days to load (inclusive)
day_start = 30
day_end   = 30

stat_type = "max" # options: "min", "max", "mean", "raw"; 
#"raw" requires to plot an instant value for the specified time

out_dir = "" # Leave empty to save in the same directory as in_dir
outfile = None # Set to None to auto-generate based on case and varname

# ---------------------------------------------------------------------------
# End user configuration
# ---------------------------------------------------------------------------
# %%
# Build file list for the requested date range

file_prefix = f"{icase}.{varname}.day"
infiles = []
for d in range(day_start, day_end + 1):
    fpath = os.path.join(in_dir, f"{file_prefix}{d:02d}.nc")
    if os.path.exists(fpath):
        infiles.append(fpath)

print(f"Case      : {icase}")
print(f"Variable  : {varname}")
print(f"Period    : Day {day_start}  to  Day {day_end}")
print(f"\nFound {len(infiles)} input file(s):")
for fp in infiles:
    print(f"  {fp}")

if len(infiles) == 0:
    raise FileNotFoundError(
        f"No input files found in '{in_dir}' matching prefix '{file_prefix}'"
        f" for the requested days {day_start} to {day_end}.")

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
tind = 0 #time index for plot; when stat_type = 'raw'

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

if "x" not in stat_data.dims or "y" not in stat_data.dims:
    raise ValueError(f"Resulting data does not have 'x' and 'y' dimensions. Dimensions found: {stat_data.dims}")

# Print max over space to easily verify the max_total_ni limit
overall_max = float(stat_data.max(skipna=True).values)
print(f"Overall spatial maximum of the {stat_type} {varname}: {overall_max:.2f}")

# Get coordinates
x_values = ds['x'].values
y_values = ds['y'].values

# Get units if available
units = data.attrs.get("units", "")
unit_str = f" [{units}]" if units else ""

# %%
#plot setting
marker_size = 4
if stat_type == "raw":
    marker_size = 15

# %%
# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
print("Generating 2D map plot...")
savefig = False

fig = plt.figure(figsize=(10, 8))

# For PINACLES 2D Cartesian grid, use pcolormesh
X, Y = np.meshgrid(x_values, y_values)
pc = plt.pcolormesh(X, Y, stat_data.values, shading='auto', cmap='viridis')

# Add a colorbar
cbar = plt.colorbar(pc)
cbar.set_label(f"{varname} ({stat_type} over time){unit_str}", fontsize=12)

# Optional: Set colormap limits
if "nc" in varname or "ni" in varname:
    pc.set_clim(vmin=0)

plt.xlabel('x coordinate [m]', fontsize=12)
plt.ylabel('y coordinate [m]', fontsize=12)
plt.ticklabel_format(style='sci', axis='both', scilimits=(0,0))

title_var = varname.replace('_', ' ')
plt.title(f"Time {stat_type.capitalize()} of {title_var}\n({icase} | Day {day_start} to {day_end})", fontsize=14)

plt.tight_layout()

# Determine output filename
if outfile is None:
    if not out_dir:
        out_dir = in_dir
        if not out_dir:
            out_dir = "."
            
    date_range_str = f"day{day_start}_to_{day_end}"
    final_outfile = os.path.join(out_dir, f"{icase}.{varname}.{date_range_str}_time_{stat_type}.png")
else:
    if not out_dir:
        out_dir = "."
    final_outfile = os.path.join(out_dir, outfile)

if savefig:
    os.makedirs(out_dir, exist_ok=True)
    fig.savefig(final_outfile, dpi=300)
    print(f"2D map plot saved successfully to: {final_outfile}")

plt.show()

if not _interactive:
    plt.close(fig)


# %%

print("Generating 1D scatter plot...")
fig2 = plt.figure(figsize=(12, 6))

flat_data = stat_data.values.flatten()
ncol_values = np.arange(len(flat_data))

plt.scatter(ncol_values, flat_data, s=marker_size, alpha=0.6, color='b', marker='o')

plt.xlabel('Flattened Grid Index', fontsize=12)
plt.ylabel(f"{varname} ({stat_type} over time){unit_str}", fontsize=12)
plt.ticklabel_format(style='sci', axis='y', scilimits=(0,0))

plt.title(f"Time {stat_type.capitalize()} of {title_var} across Flattened Grid\n({icase} | Day {day_start} to {day_end})", fontsize=14)
plt.grid(True, linestyle='--', alpha=0.7)

# Optional: Set y-axis lower limit to 0 if we know values should be positive
if "nc" in varname or "ni" in varname:
    plt.ylim(bottom=0)

plt.tight_layout()

# Determine output filename for the scatter plot
if outfile is None:
    final_outfile2 = os.path.join(out_dir, f"{icase}.{varname}.{date_range_str}_time_{stat_type}_scatter.png")
else:
    name, ext = os.path.splitext(outfile)
    if not out_dir:
        out_dir = "."
    final_outfile2 = os.path.join(out_dir, f"{name}_scatter{ext}")

if savefig:
    fig2.savefig(final_outfile2, dpi=300)
    print(f"Scatter plot saved successfully to: {final_outfile2}")

plt.show()

if not _interactive:
    plt.close(fig2)

ds.close()

# %%
