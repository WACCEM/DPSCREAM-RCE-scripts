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

# %%

# ---------------------------------------------------------------------------
# User configuration
# ---------------------------------------------------------------------------
varname = "VapWaterPath"

# List of simulation cases to overlay.  Each entry is a dict with:
#   label    – legend label
#   filepath – path to the .havg.*.nc file
#   color    – line colour (matplotlib colour string or hex)
cases = [
    {
        "label"   : "scream_cpu_dpxx_RCE_dx1km  (5-min)",
        "filepath": ("/pscratch/sd/w/wcmca1/DP-SCREAM"
                     "/scream_cpu_dpxx_RCE_dx1km/havg"
                     f"/scream_cpu_dpxx_RCE_dx1km.{varname}"
                     ".havg.INSTANT.2000-01-01_to_2000-02-16.nc"),
        "color"   : "steelblue",
    },
    {
        "label"   : "RCE01_dx1km_gpu_branch  (1-hr)",
        "filepath": ("/pscratch/sd/w/wcmca1/DP-SCREAM"
                     "/RCE01_dx1km_gpu_branch/havg"
                     f"/RCE01_dx1km_gpu_branch.{varname}"
                     ".havg.INSTANT.2000-02-17_to_2000-04-30.nc"),
        "color"   : "darkorange",
    },
    {
        "label"   : "RCE01_dx3km_gpu  (1-hr)",
        "filepath": ("/pscratch/sd/w/wcmca1/DP-SCREAM"
                     "/RCE01_dx3km_gpu/havg"
                     f"/RCE01_dx3km_gpu.{varname}"
                     ".havg.INSTANT.2000-01-01_to_2000-05-31.nc"),
        "color"   : "red",
    }
]

# Optional: resample / smooth the time series before plotting.
# Set to None to plot every time point.  Examples: "1D", "6H", "1H"
resample_freq = "1D"

# Reference date for the x-axis: day 0.  Expressed as a pandas Timestamp.
t0_date = pd.Timestamp("2000-01-01")

# Output figure
out_dir  = "/pscratch/sd/w/wcmca1/DP-SCREAM/plots"
out_file = os.path.join(out_dir, f"horiz_stats_{varname}.png")
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
    fp = c["filepath"]
    if not os.path.isfile(fp):
        raise FileNotFoundError(f"Input file not found: {fp}")
    ds = xr.open_dataset(fp, use_cftime=True)
    if varname not in ds:
        raise KeyError(f"Variable '{varname}' not found in {fp}")
    datasets.append(ds)
    print(f"Loaded : {fp}")
    print(f"  time range : {ds['time'].values[0]}  to  {ds['time'].values[-1]}")
    print(f"  n timesteps: {ds.dims['time']}")

mean_var = varname
var_var  = f"{varname}_var"

# Retrieve units from first file (assumed consistent across cases)
units     = datasets[0][mean_var].attrs.get("units", "")
var_units = datasets[0][var_var].attrs.get("units", f"({units})^2") \
            if var_var in datasets[0] else f"({units})^2"
# %%

# ---------------------------------------------------------------------------
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
savefig = False
# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                         constrained_layout=True)
ax_mean, ax_var = axes

for c, ds in zip(cases, datasets):
    s_mean = to_pandas_series(ds, mean_var, resample_freq)
    x_days = to_days(s_mean.index, t0_date)
    _=ax_mean.plot(x_days, s_mean.values,
                 color=c["color"], linewidth=1.2, label=c["label"])

    if var_var in ds:
        s_var = to_pandas_series(ds, var_var, resample_freq)
        x_days = to_days(s_var.index, t0_date)
        _=ax_var.plot(x_days, s_var.values,
                    color=c["color"], linewidth=1.2, label=c["label"])

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
