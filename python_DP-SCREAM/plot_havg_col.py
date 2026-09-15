#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plot vertical profiles of time-mean and variance from horizontal average outputs.
Reads multiple daily output files processed by calc_havg_col_DPSCREAM.py.

Usage (interactive):
    module load python
    conda activate dpscream_analysis
    Run cell by cell in VSCode or Jupyter.
"""
# %%
import os
import sys
import glob
import numpy as np
import xarray as xr
import pandas as pd
import matplotlib.pyplot as plt
import cftime

sys.path.append("/global/common/software/m1867/python/ksa_env")

from ks_pkg.plot_settings import init_style
init_style()

# %%
# ---------------------------------------------------------------------------
# User configuration
# ---------------------------------------------------------------------------
case_list  = ["RCE09_dx3km_gpu","RCE10_dx3km_gpu"] #
# varname    = "T_mid"
# stats_type = "INSTANT" #"AVERAGE"
varname    = "rrtmgp_T_mid_tend"
stats_type = "AVERAGE" #"AVERAGE"

frequency  = "nhours_x1"

# Date range to load (inclusive, YYYY-MM-DD)
ts_start = "2000-02-15"
ts_end   = "2000-02-28"

# Output directory for saving plots
out_dir = "/pscratch/sd/w/wcmca1/DP-SCREAM/plots/tests"
os.makedirs(out_dir, exist_ok=True)

# %%
# ---------------------------------------------------------------------------
# Process each case
# ---------------------------------------------------------------------------
start_date = np.datetime64(ts_start, 'D')
end_date   = np.datetime64(ts_end,   'D')
date_range = np.arange(start_date, end_date + np.timedelta64(1, 'D'), dtype='datetime64[D]')
date_strs  = {str(d) for d in date_range}

results = {}

for icase in case_list:
    print(f"\n{'='*50}")
    print(f"Processing Case: {icase}")
    print(f"{'='*50}")
    
    in_dir = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/havg"
    file_prefix = f"{icase}.{varname}.havg.{stats_type}.{frequency}."
    
    infiles = sorted([
        f for f in glob.glob(os.path.join(in_dir, f"{file_prefix}*.nc"))
        if os.path.basename(f)[len(file_prefix):len(file_prefix) + 10] in date_strs
    ])
    
    if len(infiles) == 0:
        print(f"  WARNING: No input files found for {icase}. Skipping...")
        continue
        
    print(f"  Found {len(infiles)} files.")
    
    ds_list = []
    for f in infiles:
        with xr.open_dataset(f) as ds_i:
            ds_list.append(ds_i.load())
            
    ds = xr.concat(ds_list, dim="time", data_vars="minimal", coords="minimal", compat="override")
    
    if len(ds['time'].values) > 0 and isinstance(ds['time'].values[0], cftime.datetime):
        _t_pd = pd.DatetimeIndex([
            pd.Timestamp(t.year, t.month, t.day, t.hour, t.minute, t.second)
            for t in ds['time'].values
        ])
        ds = ds.assign_coords(time=_t_pd)

    da = ds[varname]
    units = da.attrs.get("units", "unknown")
    var_data = da.values
    
    hvar_name = f"{varname}_var"
    if hvar_name in ds:
        hvar_data = ds[hvar_name].values
        hvar_units = ds[hvar_name].attrs.get("units", f"({units})^2")
    else:
        hvar_data = None
        hvar_units = None

    time_mean_of_havg = np.nanmean(var_data, axis=0)
    time_var_of_havg  = np.nanvar(var_data, axis=0)
    time_mean_of_hvar = np.nanmean(hvar_data, axis=0) if hvar_data is not None else None
    
    P0 = 100000.0
    if 'lev' in ds.dims:
        hyam = ds['hyam'].values
        hybm = ds['hybm'].values
        ps_data = ds['ps'].values
        ps_mean = np.nanmean(ps_data)
        p_mean = hyam * P0 + hybm * ps_mean
    elif 'ilev' in ds.dims:
        hyai = ds['hyai'].values
        hybi = ds['hybi'].values
        ps_data = ds['ps'].values
        ps_mean = np.nanmean(ps_data)
        p_mean = hyai * P0 + hybi * ps_mean
    else:
        raise ValueError(f"Neither 'lev' nor 'ilev' found.")

    p_mean_hPa = p_mean / 100.0
    
    results[icase] = {
        'time_mean_of_havg': time_mean_of_havg,
        'time_var_of_havg': time_var_of_havg,
        'time_mean_of_hvar': time_mean_of_hvar,
        'p_mean_hPa': p_mean_hPa,
        'units': units,
        'hvar_units': hvar_units
    }
    ds.close()

# %%
# ---------------------------------------------------------------------------
# Plot Vertical Profiles
# ---------------------------------------------------------------------------
print("\nPlotting vertical profiles ...")
save_fig = False

fig, axes = plt.subplots(1, 2, figsize=(14, 7), sharey=True)
ax1 = axes[0]
ax2 = axes[1]

colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
var_units = None
hvar_units_str = None

for idx, (icase, data) in enumerate(results.items()):
    color = colors[idx % len(colors)]
    
    if var_units is None:
        var_units = data['units']
    if hvar_units_str is None:
        hvar_units_str = data['hvar_units'] if data['hvar_units'] else f"({var_units})^2"

    # 1. Time-mean of spatial mean
    _=ax1.plot(data['time_mean_of_havg'], data['p_mean_hPa'], 
               color=color, linewidth=2.5, label=icase)
               
    # 2. Variances
    _=ax2.plot(data['time_var_of_havg'], data['p_mean_hPa'], 
               color=color, linewidth=2.0, linestyle="-", 
               label=f"{icase} (Temporal)")
               
    if data['time_mean_of_hvar'] is not None:
        _=ax2.plot(data['time_mean_of_hvar'], data['p_mean_hPa'], 
                   color=color, linewidth=2.0, linestyle="--", 
                   label=f"{icase} (Spatial)")

if len(results) > 0:
    first_p = list(results.values())[0]['p_mean_hPa']
    _=ax1.set_ylim(np.nanmax(first_p), max(1.0, np.nanmin(first_p))) # set min pressure to 1.0 hPa for log scale
    _=ax1.set_yscale('log')

_=ax1.set_ylabel("Pressure (hPa)", fontsize=12)
_=ax1.set_xlabel(f"{varname} [{var_units}]", fontsize=12)
_=ax1.set_title("Time-Mean of Horizontal Mean", fontsize=13)
_=ax1.grid(True, linestyle='--', alpha=0.7)
_=ax1.legend(fontsize=10, loc='best')

_=ax2.set_xlabel(f"Variance [{hvar_units_str}]", fontsize=12)
_=ax2.set_title("Variances\n(Solid: Temporal Var of Mean, Dashed: Mean of Spatial Var)", fontsize=13)
_=ax2.grid(True, linestyle='--', alpha=0.7)
_=ax2.legend(fontsize=9, loc='best')

_=plt.suptitle(f"{varname} Profiles\nPeriod: {ts_start} to {ts_end}", fontsize=14, y=1.02)
_=plt.tight_layout()

# Save plot
cases_str = "_".join(list(results.keys())[:3])
if len(results) > 3:
    cases_str += "_etc"
out_plot_name = os.path.join(out_dir, f"compare_{cases_str}.{varname}.havg_profile.{ts_start}_to_{ts_end}.png")

if(save_fig):
    _=plt.savefig(out_plot_name, dpi=150, bbox_inches='tight')
    print(f"Saved plot to: {out_plot_name}")

try:
    plt.show()
except Exception:
    pass
plt.close(fig)

# %%
# ---------------------------------------------------------------------------
# Plot Difference Profiles
# ---------------------------------------------------------------------------
if len(results) == 2:
    print("\nPlotting difference profiles ...")
    cases = list(results.keys())
    case1, case2 = cases[0], cases[1]
    
    diff_mean = results[case2]['time_mean_of_havg'] - results[case1]['time_mean_of_havg']
    diff_temp_var = results[case2]['time_var_of_havg'] - results[case1]['time_var_of_havg']
    
    p_mean = results[case1]['p_mean_hPa']

    print(f"\n{'='*50}")
    print(f"Statistics for Differences ({case2} - {case1})")
    print(f"{'='*50}")
    mean_diff = np.nanmean(diff_mean)
    rms_diff = np.sqrt(np.nanmean(diff_mean**2))
    max_abs_diff = np.nanmax(np.abs(diff_mean))
    print(f"Mean Difference:    {mean_diff:.6e} {var_units}")
    print(f"RMS Difference:     {rms_diff:.6e} {var_units}")
    print(f"Max Abs Difference: {max_abs_diff:.6e} {var_units}")
    
    mean_diff_var = np.nanmean(diff_temp_var)
    max_abs_diff_var = np.nanmax(np.abs(diff_temp_var))
    print(f"Mean Temp. Var Difference: {mean_diff_var:.6e} {hvar_units_str}")
    print(f"Max Abs Temp. Var Diff:    {max_abs_diff_var:.6e} {hvar_units_str}")
    print(f"{'='*50}\n")
    
    fig_diff, axes_diff = plt.subplots(1, 2, figsize=(14, 7), sharey=True)
    ax1_d = axes_diff[0]
    ax2_d = axes_diff[1]
    
    # 1. Difference of Time-Mean
    _=ax1_d.plot(diff_mean, p_mean, color='black', linewidth=2.5, label=f"{case2} - {case1}")
    
    # 2. Difference of Variances
    _=ax2_d.plot(diff_temp_var, p_mean, color='black', linewidth=2.0, linestyle="-", label="Temporal Var Diff")
    
    if results[case1]['time_mean_of_hvar'] is not None and results[case2]['time_mean_of_hvar'] is not None:
        diff_spat_var = results[case2]['time_mean_of_hvar'] - results[case1]['time_mean_of_hvar']
        _=ax2_d.plot(diff_spat_var, p_mean, color='black', linewidth=2.0, linestyle="--", label="Spatial Var Diff")

    _=ax1_d.set_ylim(np.nanmax(p_mean), max(1.0, np.nanmin(p_mean)))
    _=ax1_d.set_yscale('log')
    
    _=ax1_d.axvline(0, color='gray', linestyle=':', linewidth=1)
    _=ax2_d.axvline(0, color='gray', linestyle=':', linewidth=1)
    
    _=ax1_d.set_ylabel("Pressure (hPa)", fontsize=12)
    _=ax1_d.set_xlabel(f"{varname} Difference [{var_units}]", fontsize=12)
    _=ax1_d.set_title(f"Difference in Time-Mean of Horizontal Mean", fontsize=13)
    _=ax1_d.grid(True, linestyle='--', alpha=0.7)
    _=ax1_d.legend(fontsize=10, loc='best')

    _=ax2_d.set_xlabel(f"Variance Difference [{hvar_units_str}]", fontsize=12)
    _=ax2_d.set_title(f"Difference in Variances", fontsize=13)
    _=ax2_d.grid(True, linestyle='--', alpha=0.7)
    _=ax2_d.legend(fontsize=9, loc='best')

    _=plt.suptitle(f"{varname} Differences ({case2} - {case1})\nPeriod: {ts_start} to {ts_end}", fontsize=14, y=1.02)
    _=plt.tight_layout()

    out_diff_name = os.path.join(out_dir, f"compare_{cases_str}.{varname}.havg_diff.{ts_start}_to_{ts_end}.png")
    
    if(save_fig):
        _=plt.savefig(out_diff_name, dpi=150, bbox_inches='tight')
        print(f"Saved difference plot to: {out_diff_name}")

    try:
        plt.show()
    except Exception:
        pass
    fig_diff.clf()
    plt.close(fig_diff)

# %%
