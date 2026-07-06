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
sys.path.append("/global/common/software/m1867/python/ksa_env")

from ks_pkg.plot_settings import init_style
init_style()

# %%
# Helper: convert to pandas time index and optionally resample
# ---------------------------------------------------------------------------

def to_pandas_series(ds, field, freq):
    """Return a pandas Series with a DatetimeIndex, optionally resampled.

    Uses xarray's resample (cftime-aware) before converting to a standard
    pandas DatetimeIndex so that matplotlib date formatters work correctly
    even when the file uses a non-standard calendar (e.g. noleap).
    """
    da = ds[field]
    if freq is not None:
        da = da.resample(time=freq).mean()
    # Convert cftime (or numpy datetime64) time values to pandas Timestamps
    times = pd.DatetimeIndex([
        pd.Timestamp(t.year, t.month, t.day, t.hour, t.minute, t.second)
        for t in da['time'].values
    ])
    return pd.Series(da.values, index=times)


def to_days(datetime_index, t0):
    """Convert a pandas DatetimeIndex to fractional noleap days since t0.

    Subtracts one day for every Feb 29 (Gregorian leap day) between t0 and
    each timestamp so the axis matches the model's 365-day calendar.
    """
    def _noleap(t_val):
        total_sec = (t_val - t0).total_seconds()
        t_lo, t_hi = (t0, t_val) if total_sec >= 0 else (t_val, t0)
        leap_days = sum(
            1 for y in range(t_lo.year, t_hi.year + 1)
            if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
            and t_lo < pd.Timestamp(y, 2, 29) <= t_hi
        )
        correction = leap_days if total_sec >= 0 else -leap_days
        return total_sec / 86400.0 - correction
    return np.array([_noleap(t) for t in datetime_index])

# %%

# ---------------------------------------------------------------------------
# User configuration
# ---------------------------------------------------------------------------
#DP-SCREAM variable setting
varname = "LW_flux_up_at_model_top" # "SW_flux_dn_at_model_top" # "imse" #"VapWaterPath"
stats_type = "AVERAGE" # AVERAGE, INSTANT

varname_PINACLES = "toa_lw_up" #when PINACLES simulations are also plotted

# List of simulation cases to overlay.  Each entry is a dict with:
#   label    – legend label
#   filepath – path to the .havg.*.nc file
#   color    – line colour (matplotlib colour string or hex)
cases = [
    # {
    #     "label"   : "scream_cpu_dpxx_RCE_dx1km  (5-min)",
    #     "filepath": ("/pscratch/sd/w/wcmca1/DP-SCREAM"
    #                  "/scream_cpu_dpxx_RCE_dx1km/havg"
    #                  f"/scream_cpu_dpxx_RCE_dx1km.{varname}"
    #                  f".havg.{stats_type}.2000-01-01_to_2000-02-16.nc"),
    #     "color"   : "steelblue",
    #     "lwide"  : 1.5,
    # },
    # {
    #     "label"   : "RCE01_dx1km_gpu_branch  (1-hr)",
    #     "filepath": ("/pscratch/sd/w/wcmca1/DP-SCREAM"
    #                  "/RCE01_dx1km_gpu_branch/havg"
    #                  f"/RCE01_dx1km_gpu_branch.{varname}"
    #                  f".havg.{stats_type}.2000-02-17_to_2000-04-30.nc"),
    #     "color"   : "darkorange",
    #     "lwide"  : 1.5,
    # },
    # {
    #     "label"   : "v302_dx3km_gpu  (1-hr)",
    #     "filepath": ("/pscratch/sd/w/wcmca1/DP-SCREAM"
    #                  "/RCE01_dx3km_gpu/havg"
    #                  f"/RCE01_dx3km_gpu.{varname}"
    #                  f".havg.{stats_type}.2000-01-01_to_2000-05-31.nc"),
    #     "color"   : "red",
    #     "lwide"  : 2.0,
    # },
    # {
    #     "label"   : "RCEMIP_PINACLES_dx3km_150x150km  (1-hr)",
    #     "varname" : "VWP",
    #     "filepath": ("/pscratch/sd/w/wcmca1/PINACLES/rce/RCE03_150x150_1km/havg"
    #                  "/RCE03_150x150_1km.{vname}"
    #                  ".havg.day00_to_60.nc"),
    #     "color"   : "orange",
    #     "lwide"  : 3.0,
    # },
    # {
    #     "label"   : "v310_dx3km_gpu  (1-hr)",
    #     "filepath": ("/pscratch/sd/w/wcmca1/DP-SCREAM"
    #                  "/RCE02_dx3km_gpu/havg"
    #                  f"/RCE02_dx3km_gpu.{varname}"
    #                  f".havg.{stats_type}.2000-01-01_to_2000-05-15.nc"),
    #     "color"   : "blueviolet",
    #     "lwide"  : 2.0,
    # },
    # {
    #     "label"   : "RCEMIP_DPSCREAMv310_dx3km_600x600km  (1-hr)",
    #     "filepath": ("/pscratch/sd/w/wcmca1/DP-SCREAM"
    #                  "/RCE09_dx3km_gpu/havg"
    #                  f"/RCE09_dx3km_gpu.{varname}"
    #                  f".havg.{stats_type}.2000-01-01_to_2000-04-15.nc"),
    #     "color"   : "gray",
    #     "lwide"  : 2.0,
    # },
    {
        "label"   : "RCEMIP_DPSCREAMv310_dx1km_600x600km v2",
        "filepath": ("/pscratch/sd/w/wcmca1/DP-SCREAM"
                     "/RCE02_dx1km_gpu/havg"
                     f"/RCE02_dx1km_gpu.{varname}"
                     f".havg.{stats_type}.2000-01-01_to_2000-03-15.nc"),
        "color"   : "Blue",
        "lwide"  : 3.0,
    },
    {
        "label"   : "PINACLES_dx1km_600x600km v0",
        "varname" : varname_PINACLES,
        "filepath": ("/pscratch/sd/w/wcmca1/PINACLES/rce/RCE00_dx1km_600x600km/havg"
                     "/RCE00_dx1km_600x600km.{vname}"
                     ".havg.day00_to_59.nc"),
        "color"   : "lightgreen",
        "lwide"  : 3.0,
    },
    {
        "label"   : "RCEMIP_PINACLES_dx1km_600x600km  (1-hr)",
        "varname" : varname_PINACLES,
        "filepath": ("/pscratch/sd/w/wcmca1/PINACLES/rce/RCE01_dx1km_600x600km/havg"
                     "/RCE01_dx1km_600x600km.{vname}"
                     ".havg.day00_to_44.nc"),
        "color"   : "green",
        "lwide"  : 3.0,
    }
]

# Optional: resample / smooth the time series before plotting.
# Set to None to plot every time point.  Examples: "1D", "6H", "1H"
resample_freq = "1D"

# Reference date for the x-axis: day 0.  Expressed as a pandas Timestamp.
t0_date = pd.Timestamp("2000-01-01")

# Output figure
out_dir  = "/pscratch/sd/w/wcmca1/DP-SCREAM/plots"
out_file = os.path.join(out_dir, f"horiz_stats_{varname}.pdf")
dpi      = 150

# ---------------------------------------------------------------------------
# End user configuration
# ---------------------------------------------------------------------------
# %%

os.makedirs(out_dir, exist_ok=True)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
datasets = []
for c in cases:
    vname = c.get("varname", varname)
    fp = c["filepath"].format(vname=vname)
    if not os.path.isfile(fp):
        raise FileNotFoundError(f"Input file not found: {fp}")
    ds = xr.open_dataset(fp, use_cftime=True)
    if vname not in ds:
        raise KeyError(f"Variable '{vname}' not found in {fp}")
    datasets.append(ds)
    print(f"Loaded : {fp}")
    print(f"  time range : {ds['time'].values[0]}  to  {ds['time'].values[-1]}")
    print(f"  n timesteps: {ds.dims['time']}")

first_vname = cases[0].get("varname", varname)
mean_var_0 = first_vname
var_var_0  = f"{first_vname}_var"

# Retrieve units from first file (assumed consistent across cases)
units     = datasets[0][mean_var_0].attrs.get("units", "")
var_units = datasets[0][var_var_0].attrs.get("units", f"({units})^2") \
            if var_var_0 in datasets[0] else f"({units})^2"


# %%
savefig = False
# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                         constrained_layout=True)
ax_mean, ax_var = axes

for c, ds in zip(cases, datasets):
    vname = c.get("varname", varname)
    mean_var = vname
    var_var  = f"{vname}_var"

    s_mean = to_pandas_series(ds, mean_var, resample_freq)
    x_days = to_days(s_mean.index, t0_date)
    _=ax_mean.plot(x_days, s_mean.values,
                 color=c["color"], linewidth=c.get("lwide", 1.2), label=c["label"])

    if var_var in ds:
        s_var = to_pandas_series(ds, var_var, resample_freq)
        x_days = to_days(s_var.index, t0_date)
        _=ax_var.plot(x_days, s_var.values,
                    color=c["color"], linewidth=c.get("lwide", 1.2), label=c["label"])

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
_=ax_var.xaxis.set_minor_locator(AutoMinorLocator())
_=ax_var.set_xlabel(f"Days since {t0_date.strftime('%Y-%m-%d')}", fontsize=11)

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
if not _interactive:
    plt.close(fig)

# %%

for ds in datasets:
    ds.close()

# %%
