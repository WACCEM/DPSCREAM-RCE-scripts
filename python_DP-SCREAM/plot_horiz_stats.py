#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_horiz_stats.py

Reads horizontal-average/variance files produced by horiz_avg_DPSCREAM.py
from two or more DP-SCREAM simulations and produces a multi-panel time-series
plot showing the domain-mean and domain-variance for a chosen variable.

Usage (after activating the dpscream_analysis conda environment):
  module load python
  conda activate dpscream_analysis
  python plot_horiz_stats.py
"""
# %%

import os
import numpy as np
import pandas as pd
import xarray as xr
import sys
import matplotlib
# Use the non-interactive Agg backend only when running as a plain script
# (batch/login node).  In interactive sessions (IPython, Jupyter) the
# default inline/GUI backend is kept so plt.show() renders the figure.
_interactive = hasattr(sys, 'ps1') or 'ipykernel' in sys.modules
if not _interactive:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import AutoMinorLocator

from ks_pkg.plot_settings import init_style
init_style()

sys.path.append("/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM")
from rce_tools.plotting import case_info, add_dual_time_axes, get_horiz_stats_file, to_pandas_series

# %%

# ---------------------------------------------------------------------------
# User configuration
# ---------------------------------------------------------------------------
#DP-SCREAM variable setting
varname = "imse" #"LW_flux_up_at_model_top" # "SW_flux_dn_at_model_top" # "imse" #"VapWaterPath"
stats_type = "INSTANT" # AVERAGE, INSTANT

varname_PINACLES = "imse" # "toa_lw_up"  #"imse" #when PINACLES simulations are also plotted

# List of simulation cases to overlay
case_list = ["RCE02_dx1km_gpu", "RCE00_dx1km_600x600km", "RCE01_dx1km_600x600km"]
base_date = "2000-01-01"

# Output figure
out_dir  = "/pscratch/sd/w/wcmca1/DP-SCREAM/plots"
out_file = os.path.join(out_dir, f"horiz_stats_{varname}.pdf")

# ---------------------------------------------------------------------------
# End user configuration
# ---------------------------------------------------------------------------
# %%

os.makedirs(out_dir, exist_ok=True)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
datasets = []
for case_name in case_list:
    c_info = case_info[case_name]
    vname = varname_PINACLES if c_info["model"] == "PINACLES" else varname
    
    fp = get_horiz_stats_file(case_name, vname, stats_type)
    if not fp or not os.path.isfile(fp):
        raise FileNotFoundError(f"Input file not found for case {case_name}")
        
    ds = xr.open_dataset(fp, use_cftime=True)
    if vname not in ds:
        raise KeyError(f"Variable '{vname}' not found in {fp}")
        
    datasets.append(ds)
    print(f"Loaded : {fp}")
    print(f"  time range : {ds['time'].values[0]}  to  {ds['time'].values[-1]}")
    print(f"  n timesteps: {ds.dims['time']}")

first_vname = varname_PINACLES if case_info[case_list[0]]["model"] == "PINACLES" else varname
mean_var_0 = first_vname
var_var_0  = f"{first_vname}_var"

# Retrieve units from first file (assumed consistent across cases)
units     = datasets[0][mean_var_0].attrs.get("units", "")
var_units = datasets[0][var_var_0].attrs.get("units", f"({units})^2") \
            if var_var_0 in datasets[0] else f"({units})^2"


# %%
savefig = False
lwide = 3.0
# Optional: resample / smooth the time series before plotting.
# Set to None to plot every time point.  Examples: "1D", "6h", "1h"
resample_freq = "1D"

# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True,
                         constrained_layout=True)
ax_mean, ax_var = axes

avg_last_10_mean_list = []
avg_last_10_var_list = []
case_labels = []

for case_name, ds in zip(case_list, datasets):
    c_info = case_info[case_name]
    vname = varname_PINACLES if c_info["model"] == "PINACLES" else varname
    label = f"{c_info['model']} {c_info['desc']}"
    color = c_info["color"]
    
    
    mean_var = vname
    var_var  = f"{vname}_var"

    s_mean = to_pandas_series(ds, mean_var, resample_freq)
    _=ax_mean.plot(s_mean.index, s_mean.values,
                 color=color, linewidth=lwide, label=label)
    
    avg_last_10 = s_mean.tail(10).mean()
    print(f"Case {label}: average of last 10 time samples of s_mean = {avg_last_10:.2e}")
    avg_last_10_mean_list.append(avg_last_10)
    case_labels.append(label)

    if var_var in ds:
        s_var = to_pandas_series(ds, var_var, resample_freq)
        _=ax_var.plot(s_var.index, s_var.values,
                    color=color, linewidth=lwide, label=label)
        
        avg_last_10_var = s_var.tail(10).mean()
        print(f"Case {label}: average of last 10 time samples of s_var = {avg_last_10_var:.2e}")
        avg_last_10_var_list.append(avg_last_10_var)
    else:
        avg_last_10_var_list.append(None)

# --- Formatting ---
resample_label = f" ({resample_freq} mean)" if resample_freq else ""

_=ax_mean.set_ylabel(f"{varname} [{units}]", fontsize=11)
_=ax_mean.set_title(f"Domain-mean {varname}{resample_label}", fontsize=12)
_=ax_mean.legend(fontsize=9, loc="best")
_=ax_mean.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
_=ax_mean.yaxis.set_minor_locator(AutoMinorLocator())

_=ax_var.set_ylabel(f"{varname}_var [{var_units}]", fontsize=11)
_=ax_var.set_title(f"Domain-variance {varname}{resample_label}", fontsize=12)
_=ax_var.legend(fontsize=9, loc="best")
_=ax_var.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
_=ax_var.yaxis.set_minor_locator(AutoMinorLocator())

# x-axis: days since t0
add_dual_time_axes(ax_var, base_date=base_date)

fig.suptitle(f"DP-SCREAM  –  horizontal statistics: {varname}", fontsize=13,
             fontweight="bold")

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
if savefig:
    fig.savefig(out_file, dpi=dpi, bbox_inches="tight")
    print(f"\nFigure saved: {out_file}")

plt.show()

#if not (hasattr(sys, 'ps1') or 'ipykernel' in sys.modules):
fig.clf()
plt.close(fig)

# %%
# ---------------------------------------------------------------------------
# Bar graphs for time-average quantities
# ---------------------------------------------------------------------------
ymin0, ymax0=None,None
ymin1, ymax1=None,None

if(varname == "imse"):
    ymin0 = 3.3e9
    ymax0 = 3.5e9
elif(varname == "LW_flux_up_at_model_top"):
    ymin0 = 200
    ymax0 = 300
    ymin1 = 1000
    ymax1 = 2000

fig_bar, axes_bar = plt.subplots(2, 1, figsize=(12, 12), constrained_layout=True)

x_pos = range(len(case_labels))
colors = [case_info[case_name]["color"] for case_name in case_list]

bars0 = axes_bar[0].bar(x_pos, avg_last_10_mean_list, color=colors)
for i, rect in enumerate(bars0):
    height = rect.get_height()
    _=axes_bar[0].text(rect.get_x() + rect.get_width()/2., height,
                       f'{avg_last_10_mean_list[i]:.2e}',
                       ha='center', va='bottom', fontsize=10)
_=axes_bar[0].set_xticks(x_pos)
#_=axes_bar[0].set_xticklabels(case_labels, rotation=45, ha='right')
_=axes_bar[0].set_ylabel(f"{varname} [{units}]", fontsize=11)
_=axes_bar[0].set_title(f"Time-mean of last 10 samples: {varname}", fontsize=12)
_=axes_bar[0].grid(True, linestyle="--", linewidth=0.5, alpha=0.6, axis='y')
_=axes_bar[0].set_ylim(ymin0, ymax0)
var_plot_values = [v if v is not None else 0 for v in avg_last_10_var_list]
bars1 = axes_bar[1].bar(x_pos, var_plot_values, color=colors)
for i, rect in enumerate(bars1):
    height = rect.get_height()
    if avg_last_10_var_list[i] is not None:
        _=axes_bar[1].text(rect.get_x() + rect.get_width()/2., height,
                           f'{var_plot_values[i]:.2e}',
                           ha='center', va='bottom', fontsize=10)
_=axes_bar[1].set_xticks(x_pos)
_=axes_bar[1].set_xticklabels(case_labels, rotation=45, ha='right')
_=axes_bar[1].set_ylabel(f"{varname}_var [{var_units}]", fontsize=11)
_=axes_bar[1].set_title(f"Time-mean of last 10 samples: {varname}_var", fontsize=12)
_=axes_bar[1].grid(True, linestyle="--", linewidth=0.5, alpha=0.6, axis='y')
_=axes_bar[1].set_ylim(ymin1, ymax1)

if savefig:
    bar_out_file = out_file.replace('.pdf', '_bars.pdf')
    fig_bar.savefig(bar_out_file, dpi=dpi, bbox_inches="tight")
    print(f"\nBar graph saved: {bar_out_file}")

plt.show()

fig_bar.clf()
plt.close(fig_bar)

# %%

for ds in datasets:
    ds.close()

# %%
