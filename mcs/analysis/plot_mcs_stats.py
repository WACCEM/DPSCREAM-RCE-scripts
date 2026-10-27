# %% [markdown]
# # Plot MCS Statistics
# 
# This script compares MCS track statistics (duration) and life-cycle 
# composites (total rain) between DP-SCREAM and PINACLES simulations.
#
# **Environment Setup:**
# ```bash
# module load python
# conda activate dpscream_analysis
# python plot_mcs_stats.py
# ```

# %%
import xarray as xr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from pathlib import Path
import sys

sys.path.append("/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM")
from rce_tools.plotting import case_info, figdir_root, add_dual_time_axes

# Scientific matplotlib best practices
mpl.rcParams['figure.figsize'] = (10, 6)
mpl.rcParams['font.size'] = 14
mpl.rcParams['axes.labelsize'] = 14
mpl.rcParams['axes.titlesize'] = 16
mpl.rcParams['xtick.labelsize'] = 12
mpl.rcParams['ytick.labelsize'] = 12
mpl.rcParams['legend.fontsize'] = 12
mpl.rcParams['figure.dpi'] = 100
mpl.rcParams['savefig.dpi'] = 300
mpl.rcParams['savefig.format'] = 'pdf'

# %%

case_list = ["dx1km_L600km_RCE03_gpu","RCE00_dx1km_600x600km", "RCE01_dx1km_600x600km"]
track_period = ["20000101.0000_20000315.0000","20000101.0000_20000229.0000","20000101.0000_20000315.0000"]
#"RCE02_dx1km_gpu"
#"20000101.0000_20000315.0000",

data_root = "/pscratch/sd/w/wcmca1"

# Load datasets dynamically
datasets = {}
time_res = {}

for case_name, period in zip(case_list, track_period):
    c_info = case_info[case_name]
    model_name = c_info["model"]
    
    filepath = f"{data_root}/{model_name}/{case_name}/mcstrack/stats/mcs_tracks_final_{period}.nc"
    print(f"Loading {case_name} data from {filepath}...")
    ds = xr.open_dataset(filepath)
    datasets[case_name] = ds
    
    # Extract time resolution to convert duration to hours
    time_res[case_name] = ds.attrs.get("time_resolution_hour", 1.0)

# %%
# General plot settings

figdir = f'{figdir_root}/mcs_stats'

# %%
savefig = False

# ------------------------------------------------------------------------
# Plot MCS Duration Histogram
# ------------------------------------------------------------------------
# 1D track-level variables (dims: [tracks], not time-dependent) in mcs_tracks_final_*.nc:
#   - "track_duration"          : Duration of each track (number of time steps; multiply by time_res for hours)
#   - "mcs_duration"            : Duration of MCS stage (number of time steps; multiply by time_res for hours)
#   - "pf_lifetime"             : MCS lifetime when a significant PF is present [hour]


plotvar = "pf_lifetime"
print(f"Plotting {plotvar} Histogram...")

fig, ax = plt.subplots(figsize=(12, 6))

bins = np.arange(0, 48, 2)

val_list = []
label_list = []
color_list = []

for case_name in case_list:
    c_info = case_info[case_name]
    label = f"{c_info['model']} {c_info['desc']}"
    color = c_info["color"]
    
    ds = datasets[case_name]
    da = ds[plotvar]
    
    # Convert time-step counts to hours if plotting track_duration or mcs_duration
    if plotvar in ["track_duration", "mcs_duration"]:
        vals = da.values * time_res[case_name]
        var_units = "hours"
    else:
        vals = da.values
        var_units = da.attrs.get("units", "")
    
    # Filter valid positive/non-NaN values
    vals = vals[np.isfinite(vals) & (vals > 0)]
    
    val_list.append(vals)
    label_list.append(label)
    color_list.append(color)

ax.hist(val_list, bins=bins, alpha=0.8, label=label_list, density=True, 
        color=color_list, edgecolor='k', rwidth=0.85)

xlabel = f"CCS {plotvar} ({var_units})" if var_units else f"CCS {plotvar}"
ax.set_xlabel(xlabel)
ax.set_ylabel('Probability Density')
ax.set_title(f'Distribution of Cold Cloud System (CCS) {plotvar}')
ax.legend()
ax.grid(True, linestyle='--', alpha=0.6)

if savefig:
    out_fig1 = f"{plotvar}_hist.pdf"
    fig.savefig((figdir + "/" + out_fig1), bbox_inches='tight')
    print(f"Saved {out_fig1}")

plt.show();

# %%
savefig = False
plotvar ="pf_npf"  #"total_rain"

# ------------------------------------------------------------------------
# Plot time series variable over cloud lifecycle relative time
# ------------------------------------------------------------------------
print(f"Plotting {plotvar} Time-Series Composite...")

fig, ax = plt.subplots(figsize=(14, 5))

# Plot up to a reasonable max time for typical MCS lifecycle
max_hours = 24
for case_name in case_list:
    c_info = case_info[case_name]
    label = f"{c_info['model']} {c_info['desc']}"
    color = c_info["color"]
    
    ds = datasets[case_name]
    
    # The 'times' dimension represents relative time since initiation.
    var_data = ds[plotvar]
    var_units = var_data.attrs.get("units", "")
    var_long_name = var_data.attrs.get("long_name", plotvar)
    
    # Compute mean, sample variance, and sample count over tracks (ignoring NaNs)
    mean_var = var_data.mean(dim="tracks", skipna=True).values
    var_stat = var_data.var(dim="tracks", skipna=True, ddof=1).values
    n_samples = var_data.count(dim="tracks").values

    # Calculate 95% confidence interval: 1.96 * sqrt(variance / n_samples)
    sem = np.where(n_samples > 1, np.sqrt(var_stat / n_samples), np.nan)
    ci95 = 1.96 * sem
    
    # Create relative time arrays starting at 0
    time_hours = np.arange(len(mean_var)) * time_res[case_name]
    
    ax.plot(time_hours, mean_var, label=label, color=color, linewidth=2)
    ax.fill_between(time_hours, mean_var - ci95, mean_var + ci95, color=color, alpha=0.2)

ax.set_xlim(0, max_hours)
ax.set_xlabel('Relative Time since Initiation (hours)')
ylabel = f"{plotvar} ({var_units})" if var_units else plotvar
ax.set_ylabel(ylabel)
ax.set_title(f'Composite Lifecycle of CCS {plotvar}')
ax.legend()
ax.grid(True, linestyle='--', alpha=0.6)

if savefig:
    out_fig2 = f"{plotvar}_mean_timeseries.pdf" 
    fig.savefig((figdir + "/"+ out_fig2), bbox_inches='tight')
    print(f"Saved {out_fig2}")

plt.show();

# %%
# Plot time series of the actual simulation time
savefig = False
# Options for plotvar:
#   - Any 2D (tracks, times) variable: "area", "core_area", "cold_area", "total_rain",
#     "total_volrain", "total_heavyvolrain", "rainrate_heavyrain", "rainrate_p95",
#     "pf_npf", "movement_speed", "mintb", etc.
#   - Any 3D (tracks, times, nmaxpf) variable (largest PF at nmaxpf=0 is used, or sum across PFs):
#     "pf_area", "pf_majoraxis", "pf_maxrainrate", "pf_rainrate", "pf_skewness", "pf_eccentricity"
#   - Special derived metrics:
#     "active_mcs_count" : Number of active MCS tracks at each simulation hour
#     "merger_count"     : Total number of cloud mergers occurring at each simulation hour
#     "split_count"      : Total number of cloud splits occurring at each simulation hour
plotvar = "split_count"
agg_method = "mean"      # "mean", "sum", or "max" across active tracks at each hour
resample_freq = "6h"     # e.g., "6h", "1D", or None for raw hourly time series
base_date = "2000-01-01"

print(f"Plotting Simulation-Time Series of {plotvar} ({agg_method})...")

fig, ax = plt.subplots(figsize=(14, 5))

for case_name in case_list:
    c_info = case_info[case_name]
    label = f"{c_info['model']} {c_info['desc']}"
    color = c_info["color"]

    ds = datasets[case_name]

    # Flatten base_time across (tracks, times)
    bt_raw = ds["base_time"].values
    valid_mask = ~np.isnan(bt_raw)
    bt_valid = pd.to_datetime(bt_raw[valid_mask].ravel(), unit="s")

    if plotvar == "active_mcs_count":
        # Count number of active tracks at each timestamp
        vals_valid = np.ones(len(bt_valid), dtype=float)
        var_units = "count"
        effective_agg = "sum"
    elif plotvar == "merger_count":
        # Count merging clouds (> 0) per (track, time)
        mc = (ds["merge_cloudnumber"].values > 0).sum(axis=-1)
        vals_valid = mc[valid_mask].ravel().astype(float)
        var_units = "count"
        effective_agg = "sum"
    elif plotvar == "split_count":
        # Count splitting clouds (> 0) per (track, time)
        sc = (ds["split_cloudnumber"].values > 0).sum(axis=-1)
        vals_valid = sc[valid_mask].ravel().astype(float)
        var_units = "count"
        effective_agg = "sum"
    else:
        da = ds[plotvar]
        var_units = da.attrs.get("units", "")
        # If 3D (tracks, times, nmaxpf), select largest PF (index 0)
        if "nmaxpf" in da.dims:
            da = da.isel(nmaxpf=0)
        vals_valid = da.values[valid_mask].ravel().astype(float)
        effective_agg = agg_method

    # Group by simulation timestamp and aggregate across all active tracks
    df_tmp = pd.DataFrame({"time": bt_valid, "val": vals_valid}).dropna(subset=["val"])
    if effective_agg == "sum":
        s_ts = df_tmp.groupby("time")["val"].sum()
    elif effective_agg == "max":
        s_ts = df_tmp.groupby("time")["val"].max()
    else:
        s_ts = df_tmp.groupby("time")["val"].mean()

    if resample_freq:
        s_ts = s_ts.resample(resample_freq).mean()

    ax.plot(s_ts.index, s_ts.values, label=label, color=color, linewidth=2, alpha=0.85)

add_dual_time_axes(ax, base_date=base_date)
ylabel = f"{plotvar} ({effective_agg}, {var_units})" if var_units else f"{plotvar} ({effective_agg})"
ax.set_ylabel(ylabel)
resample_str = f" ({resample_freq} mean)" if resample_freq else ""
ax.set_title(f"Domain Evolution of CCS {plotvar} ({effective_agg}){resample_str}")
ax.legend(loc="best", frameon=False)
ax.grid(True, linestyle="--", alpha=0.6)
plt.tight_layout()

if savefig:
    out_fig3 = f"{plotvar}_{effective_agg}_simtime_timeseries.pdf"
    fig.savefig(f"{figdir}/{out_fig3}", bbox_inches="tight")
    print(f"Saved {out_fig3}")

plt.show();

# %%
print("Analysis complete.")
