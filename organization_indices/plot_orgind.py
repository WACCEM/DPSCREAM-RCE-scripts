#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# Script: plot_orgind.py
# 
# Description:
# Plots OLR snapshots and a time series of a specified organization index for 
# multiple simulations from DP-SCREAM and PINACLES.
#
# Usage (interactive):
#     module load python
#     conda activate analysis_2026
#     Run cell by cell in VSCode or Jupyter.
# ==============================================================================

# %%
import os
import glob
import numpy as np
import pandas as pd
import xarray as xr
import sys
import matplotlib
_interactive = hasattr(sys, 'ps1') or 'ipykernel' in sys.modules
if not _interactive:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from ks_pkg.plot_settings import init_style
init_style()

import sys
sys.path.append("/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM")
from rce_tools.plotting import case_info, add_dual_time_axes, get_case_info


# %%
# USER CONFIGURATION
# ==============================================================================
case_list = ["RCE02_dx1km_gpu","RCE00_dx1km_600x600km", "RCE01_dx1km_600x600km" ]

base_date= "2000-01-01"



# %%
date_range = []

for ic, icase in enumerate(case_list):
    if(icase == "RCE02_dx1km_gpu"):
        date_range.append("2000-01-01_to_2000-03-15")
    elif(icase == "RCE00_dx1km_600x600km"):
        date_range.append("2000-01-01_to_2000-03-01")
    elif(icase == "RCE00_dx1km_600x600km"):
        date_range.append("2000-01-01_to_2000-02-14")


# %%
# 1. PLOT TIME SERIES OF ORGANIZATION INDEX
# --------------------------------------------------------------------------
# The organization index to plot in the time series comparison
# Typical options: 'Iorg', 'SCAI', 'MCAI', 'COP', 'ROME', 'Lorg', 'OIDRA'
TARGET_INDEX = 'OIDRA'
print(f"\nGenerating time series plot for {TARGET_INDEX}...")
SAVE_PLOTS = False
lwide = 3.0
# Optional: resample / smooth the time series before plotting.
# Set to None to plot every time point.  Examples: "1D", "6h", "1h"
resample_freq = "6h"

fig_ts, ax_ts = plt.subplots(1, 1, figsize=(14, 5))


for i, case_name in enumerate(case_list):
    sim_type, _, _, pkl_file = get_case_info(case_name)
    
    if os.path.exists(pkl_file):
        print(f"  Loading organization indices for {case_name} from {pkl_file}")
        try:
            df_indices = pd.read_pickle(pkl_file)
            
            if TARGET_INDEX in df_indices.columns:
                s_plot = df_indices.set_index('time')[TARGET_INDEX]
                if resample_freq:
                    s_plot = s_plot.resample(resample_freq).mean()
                    
                _=ax_ts.plot(
                    s_plot.index, 
                    s_plot.values, 
                    color=case_info[case_name]['color'], 
                    label=f"{case_info[case_name]['model']} {case_info[case_name]['desc']}", 
                    alpha=0.8, 
                    linewidth=lwide
                )
            else:
                print(f"  [WARNING] Index '{TARGET_INDEX}' not found in {pkl_file}")
        except Exception as e:
            print(f"  [ERROR] Failed to read {pkl_file}: {e}")
    else:
        print(f"  [WARNING] Pickle file not found for {case_name}:\n    {pkl_file}")

_=add_dual_time_axes(ax_ts, base_date=base_date)
_=ax_ts.set_ylabel(TARGET_INDEX, fontsize=11)
_=ax_ts.yaxis.label.set_color('k')

# Set appropriate y-limits depending on the index
if TARGET_INDEX == 'Iorg':
    _=ax_ts.set_ylim(0, 1)
elif TARGET_INDEX in ['SCAI', 'MCAI']:
    _=ax_ts.set_ylim(-7, 0)

_=ax_ts.legend(loc='best', frameon=False, fontsize=10)
_=ax_ts.grid(True, alpha=0.3)
resample_label = f" ({resample_freq} mean)" if resample_freq else ""
_=plt.title(f'Organization Index Time Series Comparison: {TARGET_INDEX}{resample_label}', fontsize=12)
_=plt.tight_layout()

if SAVE_PLOTS:
    out_name = f'{TARGET_INDEX}_timeseries_comparison.png'
    plt.savefig(out_name, bbox_inches='tight', dpi=150)
    print(f"✓ Saved time series plot to {out_name}")

try:
    plt.show()
except Exception:
    pass

fig_ts.clf()
plt.close(fig_ts)

# %%
# 2. PLOT OLR SNAPSHOTS
# --------------------------------------------------------------------------
print(f"Comparing cases: {', '.join(case_list)}\n")
print("Generating OLR snapshot plots...")
# Set to True to save the plots to PDF files
SAVE_PLOTS = False

# Number of OLR snapshots to plot per case
N_SNAPSHOTS = 5

# Target dates and times to plot (up to 5). The figure will always have 5 subplot panels.
TARGET_DATES = ['2000-01-01 00:00',
    '2000-01-15 00:00',
    '2000-02-01 12:00',
    '2000-02-15 00:00',
]

for case_name in case_list:
    sim_type, olr_var, nc_file, pkl_file = get_case_info(case_name)
    
    fig_olr, axes_olr = plt.subplots(1, N_SNAPSHOTS, 
                                     figsize=(3.5 * N_SNAPSHOTS, 3.5))
    
    # Ensure axes_olr is 1D even if N_SNAPSHOTS == 1
    if N_SNAPSHOTS == 1:
        axes_olr = [axes_olr]
        
    if os.path.exists(nc_file):
        print(f"  Loading OLR data for {case_name} from {nc_file}")
        try:
            ds = xr.open_dataset(nc_file)
            olr_data = ds[olr_var]
            
            # Convert spatial coordinates to kilometers
            if sim_type == "DP-SCREAM":
                # Convert degrees to km (1 degree ≈ 111.32 km)
                olr_data = olr_data.assign_coords(
                    lon=(olr_data.lon - olr_data.lon.min()) * 111.32,
                    lat=(olr_data.lat - olr_data.lat.min()) * 111.32
                )
            elif sim_type == "PINACLES":
                # Convert meters to km
                olr_data = olr_data.assign_coords(
                    x=olr_data.x / 1000,
                    y=olr_data.y / 1000
                )
            
            for j in range(N_SNAPSHOTS):
                ax = axes_olr[j]
                
                if j < len(TARGET_DATES):
                    target_time_str = TARGET_DATES[j]
                    try:
                        # Find nearest time index (robust for cftime calendars)
                        time_strs = [str(t.values) if hasattr(t, 'values') else str(t) for t in olr_data.time.values]
                        time_vals_pd = pd.to_datetime(time_strs)
                        target_pd = pd.to_datetime(target_time_str)
                        idx = np.argmin(np.abs(time_vals_pd - target_pd))
                        
                        snapshot = olr_data.isel(time=idx)
                        
                        _=snapshot.plot(ax=ax, robust=True, cmap='gray_r', 
                                        add_colorbar=True, 
                                        cbar_kwargs={'shrink': 0.6, 'label': ''})
                        
                        time_val = snapshot.time.values
                        time_str = pd.to_datetime(str(time_val)).strftime('%Y-%m-%d %H:%M')
                        
                        _=ax.set_title(f"{time_str}", fontsize=10)
                        _=ax.set_aspect('equal')
                        _=ax.set_xlabel('')
                        _=ax.set_ylabel('')
                    except Exception as e:
                        print(f"  [ERROR] Failed to plot time {target_time_str} for {case_name}: {e}")
                        _=ax.text(0.5, 0.5, f"Error\n{target_time_str}", ha='center', va='center')
                        _=ax.axis('off')
                else:
                    # Turn off axis for unused panels
                    _=ax.axis('off')
                
            ds.close()
        except Exception as e:
            print(f"  [ERROR] Failed to load or plot NetCDF for {case_name}: {e}")
            for j in range(N_SNAPSHOTS):
                _=axes_olr[j].text(0.5, 0.5, f"Error plotting\n{case_name}", ha='center', va='center')
                _=axes_olr[j].axis('off')
    else:
        print(f"  [WARNING] OLR NetCDF file not found for {case_name}:\n    {nc_file}")
        for j in range(N_SNAPSHOTS):
            _=axes_olr[j].text(0.5, 0.5, f"{case_name}\nData missing", ha='center', va='center')
            _=axes_olr[j].axis('off')

    _=plt.suptitle(f"{case_name} , {case_info[case_name]['model']}, {case_info[case_name]['desc']} - OLR Snapshots", fontsize=14, y=0.98)
    _=plt.tight_layout()
    
    if SAVE_PLOTS:
        out_name = f'olr_snapshots_{case_name}.pdf'
        plt.savefig(out_name, bbox_inches='tight', dpi=150)
        print(f"✓ Saved OLR snapshots to {out_name}")
    
    try:
        plt.show()
    except Exception as e:
        print("Note: plt.show() failed, which is expected if no display is attached. Saved plot instead.")
        
    fig_olr.clf()
    plt.close(fig_olr)



# %%
