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
import matplotlib.pyplot as plt
import bottleneck as bn

# %%
# ==============================================================================
# USER CONFIGURATION
# ==============================================================================

case_info = {
    # "dx1km_L150km_RCE01_gpu": {
    #     "model": "DP-SCREAM",
    #     "date_range": "2000-01-01_to_2000-04-30",
    #     "desc": "RCEMIP IC",
    # },
    # "dx1km_L150km_RCE02_gpu": {
    #     "model": "DP-SCREAM",
    #     "date_range": "2000-01-01_to_2000-04-30",
    #     "desc": "DP default IC",
    # },
    "RCE02_dx1km_gpu": {
        "model": "DP-SCREAM",
        "date_range": "2000-01-01_to_2000-03-15",
        "desc": "DP EQ IC",
    },
    "dx1km_L600km_RCE03_gpu": {
        "model": "DP-SCREAM",
        "date_range": "2000-01-01_to_2000-03-01",
        "desc": "DP default IC",
    },
    # "RCE03_150x150_1km": {
    #     "model": "PINACLES",
    #     "date_range": "2000-01-01_to_2000-04-10",
    #     "desc": "DP EQ IC"
    # },
    # "RCE05_dx1km_150x150km": {
    #     "model": "PINACLES",
    #     "date_range": "2000-01-01_to_2000-02-25",
    #     "desc": "PINACLES EQ IC"
    # },
    # "RCE06_dx1km_150x150km": {
    #     "model": "PINACLES",
    #     "date_range": "2000-01-01_to_2000-02-24",
    #     "desc": "RCEMIP IC"
    # },
    "RCE00_dx1km_600x600km": {
        "model": "PINACLES",
        "date_range": "2000-01-01_to_2000-03-01",
        "desc": "RCEMIP IC"
    },
    "RCE01_dx1km_600x600km": {
        "model": "PINACLES",
        "date_range": "2000-01-01_to_2000-02-14",
        "desc": "PINACLES EQ IC"
    },
}

case_list = list(case_info.keys())


# Number of OLR snapshots to plot per case
N_SNAPSHOTS = 5

# %%
# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_case_info(case_name):
    """
    Returns the simulation type, OLR variable name, input NetCDF file path, 
    and output Pickle file path for a given case.
    """
    if case_name not in case_info:
        raise KeyError(f"Case {case_name} not found in case_info dictionary.")
        
    info = case_info[case_name]
    sim_type = info["model"]
    date_range = info.get("date_range", "*")

    if sim_type == "DP-SCREAM":
        olr_var = "LW_flux_up_at_model_top"
    elif sim_type == "PINACLES":
        olr_var = "toa_lw_up"
    else:
        raise ValueError(f"Unknown sim type '{sim_type}' for case: {case_name}")

    in_dir = f'/pscratch/sd/w/wcmca1/{sim_type}/{case_name}/org_ind'
    
    # Locate NetCDF file
    nc_file = f'{in_dir}/{case_name}_{olr_var}_{date_range}.nc'
    if '*' in nc_file:
        matches = glob.glob(nc_file)
        if matches:
            nc_file = matches[0]

    # Expected Pickle file path
    pkl_file = f'/global/cfs/cdirs/m1867/RCE/org_ind/df_{sim_type}_{case_name}_periodic_hourly.pkl'
    
    return sim_type, olr_var, nc_file, pkl_file

# %%
# 1. PLOT OLR SNAPSHOTS
# --------------------------------------------------------------------------
print(f"Comparing cases: {', '.join(case_list)}\n")
print("Generating OLR snapshot plots...")
# Set to True to save the plots to PDF files
SAVE_PLOTS = False

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

# %%
# 2. PLOT TIME SERIES OF ORGANIZATION INDEX
# --------------------------------------------------------------------------
# The organization index to plot in the time series comparison
# Typical options: 'Iorg', 'SCAI', 'MCAI', 'COP', 'ROME', 'Lorg'
TARGET_INDEX = 'ROME'
print(f"\nGenerating time series plot for {TARGET_INDEX}...")
SAVE_PLOTS = False

fig_ts, ax_ts = plt.subplots(1, 1, figsize=(14, 5))

# Distinct colors and linestyles for different cases
colors = ['k', 'orange', 'r', 'b', 'g', 'purple', 'magenta']

for i, case_name in enumerate(case_list):
    sim_type, _, _, pkl_file = get_case_info(case_name)
    
    if os.path.exists(pkl_file):
        print(f"  Loading organization indices for {case_name} from {pkl_file}")
        try:
            df_indices = pd.read_pickle(pkl_file)
            
            if TARGET_INDEX in df_indices.columns:
                _=ax_ts.plot(
                    df_indices['time'], 
                    bn.move_mean(df_indices[TARGET_INDEX], window=6, min_count=1), 
                    color=colors[i % len(colors)], 
                    label=f"{case_info[case_name]['model']} {case_info[case_name]['desc']}", 
                    alpha=0.8, 
                    linewidth=3
                )
            else:
                print(f"  [WARNING] Index '{TARGET_INDEX}' not found in {pkl_file}")
        except Exception as e:
            print(f"  [ERROR] Failed to read {pkl_file}: {e}")
    else:
        print(f"  [WARNING] Pickle file not found for {case_name}:\n    {pkl_file}")

_=ax_ts.set_xlabel('Time', fontsize=11)
_=ax_ts.set_ylabel(TARGET_INDEX, fontsize=11)
_=ax_ts.yaxis.label.set_color('k')

# Set appropriate y-limits depending on the index
if TARGET_INDEX == 'Iorg':
    _=ax_ts.set_ylim(0, 1)
elif TARGET_INDEX in ['SCAI', 'MCAI']:
    _=ax_ts.set_ylim(-7, 0)

_=ax_ts.legend(loc='best', frameon=False, fontsize=10)
_=ax_ts.grid(True, alpha=0.3)
_=plt.title(f'Organization Index Time Series Comparison: {TARGET_INDEX}', fontsize=12)
_=plt.tight_layout()

if SAVE_PLOTS:
    out_name = f'{TARGET_INDEX}_timeseries_comparison.png'
    plt.savefig(out_name, bbox_inches='tight', dpi=150)
    print(f"✓ Saved time series plot to {out_name}")

try:
    plt.show()
except Exception:
    pass

# %%
