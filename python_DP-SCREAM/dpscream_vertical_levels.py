#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dpscream_vertical_levels.py

Reads in the variables related to vertical coordinate from the first model output
from the specified eamxx simulation casename (e.g., RCE02_dx3km_gpu).
Plots the relationships between the vertical level index and the physical height 
above the sea level (m) as well as pressure levels (hPa).
Uses the domain average and time average across available records in the input file.

Usage (after activating the dpscream_analysis conda environment):
    module load python
    conda activate dpscream_analysis
    python dpscream_vertical_levels.py
"""
# %%
import os
import glob
import sys
import numpy as np
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

casename = "RCE02_dx3km_gpu"
output_plot = "vertical_levels.png"

# %%
# Find and open dataset
# ---------------------------------------------------------------------------

# Try finding the file
# We use glob to be flexible if there is one or two dots before 'hist'
file_pattern = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{casename}/run/{casename}*hist.INSTANT.nhours_x1.2000-01-01-00000.nc"
files = glob.glob(file_pattern)

if not files:
    raise FileNotFoundError(f"Could not find any files matching {file_pattern}")

# Just take the first one
input_file = sorted(files)[0]
print(f"Reading from: {input_file}")

# Open dataset using xarray
ds = xr.open_dataset(input_file)

# Check if necessary variables exist
if 'z_mid' not in ds.variables or 'p_mid' not in ds.variables:
    raise ValueError("Required variables 'z_mid' or 'p_mid' not found in the dataset.")

# %%
# Process data (averaging)
# ---------------------------------------------------------------------------

z_mid = ds['z_mid']
p_mid = ds['p_mid']

print("Averaging over time and space (ncol)...")
# Average over time and ncol to get domain and time averaged profile
# z_mid is in meters, p_mid is in Pa
if 'time' in z_mid.dims and 'ncol' in z_mid.dims:
    z_mid_avg = z_mid.mean(dim=['time', 'ncol']).values
    p_mid_avg = p_mid.mean(dim=['time', 'ncol']).values
else:
    print("Warning: Dimensions 'time' or 'ncol' not found. Performing full spatial/temporal average.")
    z_mid_avg = z_mid.mean(dim=[d for d in z_mid.dims if d != 'lev']).values
    p_mid_avg = p_mid.mean(dim=[d for d in p_mid.dims if d != 'lev']).values
    
# Convert pressure to hPa
p_mid_hpa = p_mid_avg / 100.0

# Vertical level index (0-based)
lev_index = np.arange(len(z_mid_avg))

# %%
# Plotting
# ---------------------------------------------------------------------------

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

# Left subplot: Height vs Level Index
ax1.plot(lev_index, z_mid_avg / 1000.0, 'b.-', markersize=4)
ax1.set_xlabel('Vertical Level Index')
ax1.set_ylabel('Physical Height above sea level (km)')
ax1.set_title('Height vs Vertical Level')
ax1.grid(True)

# Right subplot: Pressure vs Level Index
ax2.plot(lev_index, p_mid_hpa, 'r.-', markersize=4)
ax2.set_xlabel('Vertical Level Index')
ax2.set_ylabel('Pressure (hPa)')
ax2.set_title('Pressure vs Vertical Level')
ax2.grid(True)
# Invert y-axis for pressure so that lower pressure (higher altitude) is at the top
ax2.invert_yaxis()

plt.suptitle(f'Vertical Level Coordinates for {casename}')
plt.tight_layout()

plt.savefig(output_plot, dpi=300)
print(f"Plot saved to {output_plot}")

# If in interactive mode, this will show the plot inline or in GUI
if _interactive:
    plt.show()

# %%
# Print indices for common pressure levels and heights
# ---------------------------------------------------------------------------

target_heights_m = [100, 500, 1000, 1500, 3000, 5000, 10000]
target_pressures_hpa = [1000, 925, 850, 700, 500, 200, 100]

print("\n--- Common Physical Heights ---")
for h in target_heights_m:
    idx = np.argmin(np.abs(z_mid_avg - h))
    actual_h = z_mid_avg[idx]
    actual_p = p_mid_hpa[idx]
    print(f"Target Height: {h:5d} m | Nearest Index: {idx:3d} | Actual Height: {actual_h:8.1f} m | Actual Pressure: {actual_p:6.1f} hPa")

print("\n--- Common Pressure Levels ---")
for p in target_pressures_hpa:
    idx = np.argmin(np.abs(p_mid_hpa - p))
    actual_p = p_mid_hpa[idx]
    actual_h = z_mid_avg[idx]
    print(f"Target Pressure: {p:4d} hPa | Nearest Index: {idx:3d} | Actual Pressure: {actual_p:6.1f} hPa | Actual Height: {actual_h:8.1f} m")

# %%
