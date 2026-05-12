#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_cont.py

Reads remapped DP-SCREAM output files (one file per day, hourly snapshots)
produced by regrid_DPSCREAM.py, concatenates them in time over a specified
date range, and creates contour/colour-mesh plots on the X-Y Cartesian plane.

Three plotting sections are provided:
  1) Time-mean plot  (contourf or pcolormesh, saved as PDF if savefig=True)
  2) Single snapshot (contourf or pcolormesh, saved as PDF if savefig=True)
  3) Animated movie  (saved as MP4 if savefig=True)

Usage:
  module load python
  conda activate dpscream_analysis
  python plot_cont.py

Required conda packages (dpscream_analysis environment):
  conda install -c conda-forge matplotlib ffmpeg cmocean
"""
# %%

import os
import glob
import sys
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
# Non-interactive backend for batch/login nodes; keep GUI backend for IPython
_interactive = hasattr(sys, 'ps1') or 'ipykernel' in sys.modules
if not _interactive:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.ticker import AutoMinorLocator
import matplotlib.animation as manimation
import cmocean
import shutil
import subprocess

# ---------------------------------------------------------------------------
# Locate a working ffmpeg binary that can encode h264.
# Priority: (1) conda-env bin dir next to sys.executable,
#           (2) PATH via shutil.which,
#           (3) /usr/bin/ffmpeg (system)
# The conda-forge ffmpeg 2.8.6 stub is broken (missing libx264.so);
# if no working h264-capable binary is found the animation section will
# automatically fall back to PillowWriter (saves a .gif instead of .mp4).
#
# To install a working ffmpeg in the conda env:
#   pip install imageio imageio-ffmpeg
# ---------------------------------------------------------------------------
# %%

def _find_working_ffmpeg():
    """Return path to a ffmpeg binary that can encode h264, or None."""
    candidates = []
    # imageio-ffmpeg bundles a complete, working ffmpeg binary; try it first.
    try:
        import imageio_ffmpeg
        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except ImportError:
        pass
    candidates += [
        os.path.join(os.path.dirname(sys.executable), "ffmpeg"),  # conda env
        shutil.which("ffmpeg"),                                     # PATH
        "/usr/bin/ffmpeg",                                          # system
    ]
    for path in candidates:
        if not path or not os.path.isfile(path):
            continue
        try:
            # Quick smoke-test: can the binary run at all?
            result = subprocess.run(
                [path, "-encoders"],
                capture_output=True, timeout=10)
            if result.returncode == 0 and b"libx264" in result.stdout:
                return path
        except Exception:
            continue
    return None

_ffmpeg = _find_working_ffmpeg()
if _ffmpeg:
    matplotlib.rcParams["animation.ffmpeg_path"] = _ffmpeg
    print(f"ffmpeg (h264-capable) : {_ffmpeg}")
else:
    print("WARNING: no h264-capable ffmpeg found; animation will be saved as GIF.")
    print("  To fix: conda install -c conda-forge ffmpeg")

# %%
# ---------------------------------------------------------------------------
# User configuration
# ---------------------------------------------------------------------------
icase      = "scream_cpu_dpxx_RCE_dx1km" #"RCE01_dx1km_gpu_branch"
varname    = "imse"

# File naming parameters (must match regrid_DPSCREAM.py output convention)
stats_type = "INSTANT"
frequency  = "nhours_x1"
dstgrid    = "PINACLES_YX_dx1km_600x600km"

# Input directory containing the remapped daily files
in_dir = (f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/remapped")

# Date range to load (inclusive, YYYY-MM-DD)
iyear = 2000
ts_start = f"{iyear}-01-05"
ts_end   = f"{iyear}-01-25"

# For 3-D variables (time, lev, lat, lon): choose which level index to plot.
# Ignored for 2-D variables.
lev_idx = 0   # 0-based level index

# Plot method: "contourf" for smooth contouring, "pcolormesh" for pixel view
# contourf is better for smooth fields; pcolormesh is faster for noisy data
plot_method = "pcolormesh"   # "contourf" or "pcolormesh"

# Number of contour levels (used only for contourf)
n_levels = 20

# Colormap – use a cmocean perceptually-uniform map.
# Good choices: cmocean.cm.thermal (temperature/energy), cmocean.cm.haline
# (moisture), cmocean.cm.rain (precipitation), cmocean.cm.balance (anomalies).
cmap = cmocean.cm.thermal

# Reference date for day counting in titles and animation frame selection.
# Fixed to the simulation start so that day numbers are absolute simulation days
# (e.g. day 46 = Feb 15 in a noleap year starting Jan 1).
t0_date = pd.Timestamp("2000-01-01")

# %%
# ---------------------------------------------------------------------------
# Save flags and output paths
# ---------------------------------------------------------------------------
out_dir  = f"/pscratch/sd/w/wcmca1/DP-SCREAM/plots"
dpi = 150   # figure resolution for raster saves

# ---------------------------------------------------------------------------
# End user configuration
# ---------------------------------------------------------------------------

# %%
#variable setting
vfactor = 1.0
vshift = 0.0

if(varname == "imse"):
    vfactor = 1e-9
    vshift = 0.0

# %%

# ---------------------------------------------------------------------------
# Build file list for the requested date range
# ---------------------------------------------------------------------------
start_date = np.datetime64(ts_start, 'D')
end_date   = np.datetime64(ts_end,   'D')
date_range = np.arange(start_date,
                       end_date + np.timedelta64(1, 'D'),
                       dtype='datetime64[D]')
date_strs  = {str(d) for d in date_range}

file_prefix = f"{icase}.{varname}.{stats_type}.{frequency}.{dstgrid}."
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

# %%
# ---------------------------------------------------------------------------
# Load and concatenate files along the time dimension
# ---------------------------------------------------------------------------
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
    raise KeyError(f"Variable '{varname}' not found in input files.")

print(f"  time range : {str(ds['time'].values[0])}  "
      f"to  {str(ds['time'].values[-1])}")
print(f"  n timesteps: {ds.dims['time']}")
print(f"  dims       : {ds[varname].dims}")

# Eagerly load the full time axis as a pandas DatetimeIndex so it can be
# inspected interactively, e.g.:
#   time_index[snap_tidx]      → Timestamp of a chosen snapshot
#   time_index                 → full list of all time steps
time_index = pd.DatetimeIndex(ds['time'].values)


def noleap_days_since(t_val, t0):
    """Elapsed fractional days from t0 to t_val under noleap calendar.

    Gregorian arithmetic counts Feb 29 as a real day; noleap does not.
    This function subtracts one day for every Feb 29 that falls strictly
    between t0 and t_val so the result matches the model's internal day
    counter, which uses a 365-day year.
    """
    total_sec = (t_val - t0).total_seconds()
    t_lo, t_hi = (t0, t_val) if total_sec >= 0 else (t_val, t0)
    leap_days = sum(
        1 for y in range(t_lo.year, t_hi.year + 1)
        if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))  # Gregorian leap year
        and t_lo < pd.Timestamp(y, 2, 29) <= t_hi
    )
    correction = leap_days if total_sec >= 0 else -leap_days
    return total_sec / 86400.0 - correction

# %%
# ---------------------------------------------------------------------------
# Extract coordinate arrays (X, Y in km for labelling)
# ---------------------------------------------------------------------------
# The regridded files store 'x' and 'y' as auxiliary coordinate variables in
# metres (x = west-east, y = south-north).  'lat' and 'lon' index dimensions.
# Coordinates are time-invariant; read from time index 0 to avoid loading
# the full time axis into memory.
_ds0 = ds.isel(time=0)
if 'x' in _ds0 and 'y' in _ds0:
    x_km = _ds0['x'].values / 1e3   # metres → km
    y_km = _ds0['y'].values / 1e3
elif 'lon' in _ds0 and 'lat' in _ds0:
    # Fall back to raw index coordinates if metric coords absent
    x_km = _ds0['lon'].values
    y_km = _ds0['lat'].values
else:
    raise ValueError("Could not find spatial coordinate variables in dataset.")

# %%

# Build 2-D grids for pcolormesh / contourf
X_km, Y_km = np.meshgrid(x_km, y_km)   # shapes (ny, nx)

# %%
# ---------------------------------------------------------------------------
# Helper: extract 2-D spatial slice from DataArray at a given time index
# ---------------------------------------------------------------------------

def get_2d_slice(da, tidx, lev_index=None):
    """Return a scaled 2-D (ny, nx) numpy array from a DataArray.

    Parameters
    ----------
    da         : xr.DataArray  – (time, [lev,] lat, lon)
    tidx       : int           – time index
    lev_index  : int or None   – level index (for 3-D fields only)

    Scaling by the module-level vfactor and vshift is applied here so
    callers always receive plot-ready values.
    """
    arr = da.isel(time=tidx)
    if 'lev' in arr.dims:
        if lev_index is None:
            raise ValueError("lev_index must be specified for 3-D variables.")
        arr = arr.isel(lev=lev_index)
    return arr.values.astype(float) * vfactor + vshift


def get_2d_timemean(da, lev_index=None):
    """Return the scaled time-mean 2-D (ny, nx) numpy array.

    Parameters
    ----------
    da         : xr.DataArray  – (time, [lev,] lat, lon)
    lev_index  : int or None   – level index (for 3-D fields only)

    Scaling by the module-level vfactor and vshift is applied here so
    callers always receive plot-ready values.
    """
    arr = da.mean(dim='time')
    if 'lev' in arr.dims:
        if lev_index is None:
            raise ValueError("lev_index must be specified for 3-D variables.")
        arr = arr.isel(lev=lev_index)
    return arr.values.astype(float) * vfactor + vshift


# %%
# ---------------------------------------------------------------------------
# Helper: create a filled contour / pcolormesh panel
# ---------------------------------------------------------------------------

def plot_2d_field(ax, field_2d, X, Y, method, n_lev, cmap_name,
                  vmin=None, vmax=None):
    """Plot a 2-D field on the given axes using contourf or pcolormesh.

    Parameters
    ----------
    ax        : matplotlib Axes
    field_2d  : (ny, nx) ndarray
    X, Y      : (ny, nx) coordinate meshes (km)
    method    : "contourf" or "pcolormesh"
    n_lev     : int – number of contour levels
    cmap_name : str – matplotlib colormap name
    vmin/vmax : optional colour limits

    Returns
    -------
    im : the mappable object (for colorbar)
    """
    if vmin is None:
        vmin = np.nanpercentile(field_2d, 2)
    if vmax is None:
        vmax = np.nanpercentile(field_2d, 98)

    if method == "contourf":
        levels = np.linspace(vmin, vmax, n_lev + 1)
        im = ax.contourf(X, Y, field_2d, levels=levels,
                         cmap=cmap_name, extend="both")
    else:  # pcolormesh
        im = ax.pcolormesh(X, Y, field_2d,
                           cmap=cmap_name, vmin=vmin, vmax=vmax,
                           shading="auto")

    ax.set_aspect("equal")
    ax.set_xlabel("X [km]", fontsize=10)
    ax.set_ylabel("Y [km]", fontsize=10)
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    return im


# %%
# ---------------------------------------------------------------------------
# Retrieve variable metadata once
# ---------------------------------------------------------------------------
da       = ds[varname]
units    = da.attrs.get("units", "")
lev_vals = ds['lev'].values if 'lev' in ds else None
is_3d    = 'lev' in da.dims

lev_label = ""
if is_3d and lev_vals is not None:
    lev_label = f"  lev={lev_vals[lev_idx]:.1f}"
elif is_3d:
    lev_label = f"  lev_idx={lev_idx}"

date_range_label = f"{ts_start} to {ts_end}"

os.makedirs(out_dir, exist_ok=True)

# %%
# ===========================================================================
# Section 1 – Time-mean plot
# ===========================================================================
savefig_mean  = False   # Section 1: save time-mean figure as PDF
out_mean  = os.path.join(out_dir, f"{icase}.{varname}.time_mean.pdf")

print("\n--- Section 1: time-mean plot ---")

field_mean = get_2d_timemean(da, lev_index=lev_idx if is_3d else None)


fig1, ax1 = plt.subplots(figsize=(7, 6), constrained_layout=True)

im1 = plot_2d_field(ax1, field_mean, X_km, Y_km,
                    method=plot_method, n_lev=n_levels, cmap_name=cmap)

cb1 = fig1.colorbar(im1, ax=ax1, shrink=0.85, pad=0.02)
cb1.set_label(f"{varname} [{units} x {vfactor}]", fontsize=10)

ax1.set_title(
    f"Time-mean {varname}{lev_label}\n"
    f"{icase}  |  {date_range_label}",
    fontsize=11, fontweight="bold")

if savefig_mean:
    fig1.savefig(out_mean, dpi=dpi, bbox_inches="tight")
    print(f"  Saved: {out_mean}")

plt.show()
if not _interactive:
    plt.close(fig1)
# Free the large data array; the rendered figure stays displayed.
del im1, ax1, cb1

# %%
# ===========================================================================
# Section 2 – Single snapshot
# ===========================================================================
# snapshot index (0-based index into the concatenated time axis)
# ---------------------------------------------------------------------------
print(f"\n--- Section 2: snapshot at time index ---")
print(f"  select time index to plot, from 0 to {ds.sizes['time'] - 1}")
print(f"  corresponding timestamp: {pd.Timestamp(ds['time'].values[0])} to {pd.Timestamp(ds['time'].values[-1])}")
snap_tidx = 360   # which time step to plot as snapshot
plottime = pd.Timestamp(ds['time'].values[snap_tidx])
savefig_snap  = False   # Section 2: save snapshot figure as PDF

out_snap  = os.path.join(out_dir, f"{icase}.{varname}.snap_t{snap_tidx:05d}.pdf")


field_snap = get_2d_slice(da, snap_tidx, lev_index=lev_idx if is_3d else None)

# Human-readable time label for this snapshot
t_val  = pd.Timestamp(ds['time'].values[snap_tidx])
t_label = t_val.strftime("%Y-%m-%d %H:%M UTC")
t_day   = noleap_days_since(t_val, t0_date)

fig2, ax2 = plt.subplots(figsize=(7, 6), constrained_layout=True)

# Use the time-mean colour limits so the snapshot is comparable to Section 1
vmin_snap = np.nanpercentile(field_mean, 2)
vmax_snap = np.nanpercentile(field_mean, 98)

im2 = plot_2d_field(ax2, field_snap, X_km, Y_km,
                    method=plot_method, n_lev=n_levels, cmap_name=cmap,
                    vmin=vmin_snap, vmax=vmax_snap)

cb2 = fig2.colorbar(im2, ax=ax2, shrink=0.85, pad=0.02)
cb2.set_label(f"{varname} [{units} x {vfactor}]", fontsize=10)

ax2.set_title(
    f"{varname}{lev_label}  |  {t_label}  (day {t_day:.2f})\n"
    f"{icase}",
    fontsize=11, fontweight="bold")

if savefig_snap:
    fig2.savefig(out_snap, dpi=dpi, bbox_inches="tight")
    print(f"  Saved: {out_snap}")

plt.show()
if not _interactive:
    plt.close(fig2)
# Free snapshot array and axes handles.
del field_snap, im2, ax2, cb2

# %%
# ===========================================================================
# Section 3 – Animation
# ===========================================================================
savefig_anim  = True   # Section 3: save animation as MP4

# Frame range: plot frames from anim_t_start to anim_t_end (0-based, inclusive)
# Set anim_t_end = None to animate through all time steps
print(f"  select time index to plot, from 0 to {ds.sizes['time'] - 1}")
print(f"  corresponding timestamp: {pd.Timestamp(ds['time'].values[0])} to {pd.Timestamp(ds['time'].values[-1])}")

plot_st_day  = 10   # simulation day since t0_date (2000-01-01); day 46 = Feb 15
plot_st_hour = 12
plot_st_time = np.datetime64(t0_date + pd.Timedelta(days=plot_st_day, hours=plot_st_hour))
anim_t_start = np.searchsorted(ds['time'].values, plot_st_time)

plot_ed_day  = 25   # simulation day since t0_date (2000-01-01); day 76 = Mar 17
plot_ed_hour = 12
plot_ed_time = np.datetime64(t0_date + pd.Timedelta(days=plot_ed_day, hours=plot_ed_hour))
anim_t_end = np.searchsorted(ds['time'].values, plot_ed_time)

#anim_t_start = 0
#anim_t_end   = 23 #None   # e.g. 23 for first day only
_st_label = pd.Timestamp(plot_st_time).strftime("%m%d_%H")
_ed_label = pd.Timestamp(plot_ed_time).strftime("%m%d_%H")
date_range_label_anim = f"{_st_label}-{_ed_label}"

out_anim  = os.path.join(out_dir, f"{icase}.{varname}.{date_range_label_anim}.animation.mp4")

# Frames per second in the output movie
anim_fps = 2

# %%

def _update(frame_idx):
    """Update the plot for one animation frame."""
    field = get_2d_slice(da, frame_idx,
                         lev_index=lev_idx if is_3d else None)
    t_val  = pd.Timestamp(ds['time'].values[frame_idx])
    t_day  = noleap_days_since(t_val, t0_date)

    if plot_method == "contourf":
        # contourf cannot be updated in place – clear and redraw
        for coll in ax3.collections:
            coll.remove()
        im = ax3.contourf(X_km, Y_km, field, levels=levels_anim,
                          cmap=cmap, extend="both")
    else:
        im3.set_array(field.ravel())
        im = im3

    title3.set_text(
        f"{varname}{lev_label}  |  "
        f"{t_val.strftime('%Y-%m-%d %H:%M UTC')}  (day {t_day:.2f})\n"
        f"{icase}")
    return (im, title3)

# %%
print("\n--- Section 3: animation ---")

n_times = ds.dims['time']
t_start = anim_t_start
t_end   = (n_times - 1) if anim_t_end is None else min(anim_t_end, n_times - 1)
frame_indices = list(range(t_start, t_end + 1))
print(f"  t0_date      : {t0_date}")
print(f"  plot_st_time : {pd.Timestamp(plot_st_time)}  (t_start index = {t_start})")
print(f"  plot_ed_time : {pd.Timestamp(plot_ed_time)}  (t_end   index = {t_end})")
print(f"  dataset range: {pd.Timestamp(ds['time'].values[0])} – {pd.Timestamp(ds['time'].values[-1])}")
if len(frame_indices) == 0:
    raise ValueError(
        f"No frames selected: plot_st_time={pd.Timestamp(plot_st_time)} is after "
        f"plot_ed_time or outside the loaded dataset.  "
        f"Check plot_st_day/plot_ed_day and make sure t0_date={t0_date} "
        f"is correct (re-run the configuration cell if needed).")
print(f"  Animating frames {t_start} – {t_end} "
      f"({len(frame_indices)} frames at {anim_fps} fps)")

# Determine global colour limits over the animated period so they stay fixed
# across all frames (avoids colour scale jumping).
#
# Memory note (NERSC Perlmutter login node):
#   One 600×600 float64 frame = 2.75 MB.  Loading all N frames at once
#   consumes N × 2.75 MB; the practical safe limit on a shared login node
#   is ~2 GB → ~730 frames before risking OOM.
#   The strided approach below samples every clim_stride-th frame so the
#   colour-limit array stays small regardless of animation length.
#   The actual animation save streams one frame at a time via _update()
#   and is already memory-safe for any number of frames.
clim_stride = max(1, len(frame_indices) // 200)   # sample ≤200 frames
sample_indices = frame_indices[::clim_stride]
print(f"  Computing colour limits from {len(sample_indices)} sample frames "
      f"(stride={clim_stride}) ...")
sample_data = da.isel(time=sample_indices)
if is_3d:
    sample_data = sample_data.isel(lev=lev_idx)
sample_arr = sample_data.values.astype(np.float32) * vfactor + vshift
vmin_anim = float(np.nanpercentile(sample_arr, 2))
vmax_anim = float(np.nanpercentile(sample_arr, 98))
del sample_arr, sample_data   # free immediately

# --- Set up figure ---
fig3, ax3 = plt.subplots(figsize=(7, 6), constrained_layout=True)

# Draw first frame
field_0 = get_2d_slice(da, frame_indices[0],
                       lev_index=lev_idx if is_3d else None)
if plot_method == "contourf":
    levels_anim = np.linspace(vmin_anim, vmax_anim, n_levels + 1)
    im3 = ax3.contourf(X_km, Y_km, field_0, levels=levels_anim,
                       cmap=cmap, extend="both")
else:
    im3 = ax3.pcolormesh(X_km, Y_km, field_0,
                         cmap=cmap, vmin=vmin_anim, vmax=vmax_anim,
                         shading="auto")

ax3.set_aspect("equal")
ax3.set_xlabel("X [km]", fontsize=10)
ax3.set_ylabel("Y [km]", fontsize=10)
ax3.xaxis.set_minor_locator(AutoMinorLocator())
ax3.yaxis.set_minor_locator(AutoMinorLocator())

cb3 = fig3.colorbar(im3, ax=ax3, shrink=0.85, pad=0.02)
cb3.set_label(f"{varname} [{units} x {vfactor}]", fontsize=10)

t0_val    = pd.Timestamp(ds['time'].values[frame_indices[0]])
title3    = ax3.set_title(
    f"{varname}{lev_label}  |  {t0_val.strftime('%Y-%m-%d %H:%M UTC')}\n"
    f"{icase}",
    fontsize=11, fontweight="bold")

anim = manimation.FuncAnimation(
    fig3, _update,
    frames=frame_indices,
    interval=1000 // anim_fps,
    blit=False)

if savefig_anim:
    if _ffmpeg:  # working h264-capable ffmpeg available
        writer = manimation.FFMpegWriter(
            fps=anim_fps, codec="h264",
            extra_args=["-pix_fmt", "yuv420p"])   # broad MP4 compatibility
        anim.save(out_anim, writer=writer, dpi=dpi)
        print(f"  Saved MP4 : {out_anim}")
    else:        # fall back to GIF (no external binary required)
        out_gif = out_anim.replace(".mp4", ".gif")
        writer_gif = manimation.PillowWriter(fps=anim_fps)
        anim.save(out_gif, writer=writer_gif, dpi=dpi)
        print(f"  Saved GIF : {out_gif}")
        print("  Install imageio-ffmpeg to get MP4: pip install imageio imageio-ffmpeg")

plt.show()
if not _interactive:
    plt.close(fig3)
# Free animation object and axes handles (the rendered frames stay displayed).
del anim, im3, ax3, cb3

# %%
# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
ds.close()
print("\nDone.")

# %%
