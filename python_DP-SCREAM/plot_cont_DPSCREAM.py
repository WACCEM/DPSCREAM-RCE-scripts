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
import colormaps as cmaps
import shutil
import subprocess
sys.path.append("/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM")

from ks_pkg.plot_settings import init_style
init_style()

from rce_tools.plotting import _find_working_ffmpeg, get_2d_slice, get_2d_timemean, noleap_days_since, plot_2d_field
from rce_tools.rce_utils import days_since_jan1_to_month_day

_ffmpeg = _find_working_ffmpeg()
if _ffmpeg:
    matplotlib.rcParams["animation.ffmpeg_path"] = _ffmpeg
    print(f"ffmpeg (h264-capable) : {_ffmpeg}")
else:
    print("WARNING: no h264-capable ffmpeg found; animation will be saved as GIF.")
    print("  To fix: conda install -c conda-forge ffmpeg")

def _update(frame_idx):
    """Update the plot for one animation frame."""
    field = get_2d_slice(da, frame_idx,
                         lev_index=lev_idx if is_3d else None,
                         vfactor=vfactor, vshift=vshift)
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
# ---------------------------------------------------------------------------
# User configuration
# ---------------------------------------------------------------------------
icase      = "dx1km_L150km_RCE01_gpu" #"RCE01_dx1km_gpu_branch"
varname    = "LW_flux_up_at_model_top"
crange_name = None
# File naming parameters (must match regrid_DPSCREAM.py output convention)
frequency  = "nhours_x1"
dstgrid    = "PINACLES_YX_dx1km_150x150km"
#history file stats type; will be set and overwritten below for know variables
stats_type = "INSTANT"
#stats_type = "AVERAGE"

# Input directory containing the remapped daily files
in_dir = (f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/remapped")

# Date range to load (inclusive, YYYY-MM-DD)
iyear = 2000

# Option 1: Specify directly
# ts_start = f"{iyear}-03-05"
# ts_end   = f"{iyear}-03-15"
# ts_start = f"{iyear}-01-01"
# ts_end   = f"{iyear}-01-10"
# ts_start = f"{iyear}-04-01"
# ts_end   = f"{iyear}-04-10"

# Option 2: Specify by number of days since Jan 1st (0 = Jan 1st)
#e.g., 
#start_day = 90  # April 1st in noleap
#end_day   = 99  # April 10th in noleap

start_day = 100  # 
end_day   = 110  #
m_start, d_start = days_since_jan1_to_month_day(start_day, iyear, calendar="noleap")
m_end, d_end     = days_since_jan1_to_month_day(end_day, iyear, calendar="noleap")
ts_start = f"{iyear}-{m_start:02d}-{d_start:02d}"
ts_end   = f"{iyear}-{m_end:02d}-{d_end:02d}"

# For 3-D variables (time, lev, lat, lon): choose which level index to plot.
# Ignored for 2-D variables.
lev_idx = 0   # 0-based level index

# Plot method: "contourf" for smooth contouring, "pcolormesh" for pixel view
# contourf is better for smooth fields; pcolormesh is faster for noisy data
plot_method = "pcolormesh"   # "contourf" or "pcolormesh"

# Number of contour levels (used only for contourf)
n_levels = 20

# Reference date for day counting in titles and animation frame selection.
# Fixed to the simulation start so that day numbers are absolute simulation days
# (e.g. day 46 = Feb 15 in a noleap year starting Jan 1).
t0_date = pd.Timestamp("2000-01-01")

# ---------------------------------------------------------------------------
# Save flags and output paths
# ---------------------------------------------------------------------------
out_dir  = f"/pscratch/sd/w/wcmca1/DP-SCREAM/plots"
dpi = 150   # figure resolution for raster saves

#variable setting
vfactor = 1.0
vshift = 0.0

instant_list = ["diag_equiv_reflectivity_max", "imse"] #state
average_list = ["precip_total_surf_mass_flux"]  #flux and tendencies, possibly except for those used feature tracking
if(varname in instant_list):
    stats_type = "INSTANT"
elif(varname in average_list):
    stats_type = "AVERAGE"

# Colormap – use a cmocean perceptually-uniform map.
# Good choices: cmocean.cm.thermal (temperature/energy), cmocean.cm.haline
# (moisture), cmocean.cm.rain (precipitation), cmocean.cm.balance (anomalies).
cmap = cmaps.thermal

if(varname == "imse"):
    vfactor = 1e-9
    vshift = 0.0
elif(varname == "LW_flux_up_at_model_top"):
    import matplotlib.colors as mcolors
    # Use a power-law mapping (power > 1) to keep the colormap whitish/light-gray 
    # for a larger portion of the lower values, transitioning to dark gray/black at the high end.
    p = 2.0 #this exponent 2.0 seems to reproduce the colorbar in Fig. 2 of Wing et al., 2020
    colors = cmaps.gray_r(np.linspace(0.0, 1.0, 256) ** p)
    cmap = mcolors.LinearSegmentedColormap.from_list('gray_r_shifted', colors)
elif(varname == "diag_equiv_reflectivity_max"):
    #cmap = cmaps.radar_1
    cmap = cmaps.NMCRef
elif(varname == "precip_total_surf_mass_flux"):
    cmap = cmaps.precip2_17lev



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

# Build 2-D grids for pcolormesh / contourf
X_km, Y_km = np.meshgrid(x_km, y_km)   # shapes (ny, nx)

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

field_mean = get_2d_timemean(da, lev_index=lev_idx if is_3d else None,
                             vfactor=vfactor, vshift=vshift)


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

try:
    plt.show()
except Exception:
    pass
fig1.clf()
plt.close(fig1)
# Free the large data array; the rendered figure stays displayed.
del im1, ax1, cb1

# %%
# ===========================================================================
# Section 2 – Single snapshot
# ===========================================================================
# snapshot index (0-based index into the concatenated time axis)
# ---------------------------------------------------------------------------
doplot=True
savefig_snap  = True   # Section 2: save snapshot figure as PDF

if(doplot):
    print(f"\n--- Section 2: snapshot at time index ---")
    print(f"  select time index to plot, from 0 to {ds.sizes['time'] - 1}")
    print(f"  corresponding timestamp: {pd.Timestamp(ds['time'].values[0])} to {pd.Timestamp(ds['time'].values[-1])}")

    plot_doy  = 100   # simulation day since t0_date (2000-01-01); day 46 = Feb 15
    plot_mon, plot_day = days_since_jan1_to_month_day(plot_doy, iyear, calendar="noleap")
    plot_hour = 12

    plot_time = pd.Timestamp(year=iyear, month=plot_mon, day=plot_day, hour=plot_hour).to_datetime64()
    snap_tidxs = np.where(ds['time'].values == plot_time)[0]
    
    if snap_tidxs.size == 0:
        raise ValueError(f"Time {pd.Timestamp(plot_time)} not found in dataset.")
    snap_tidx = snap_tidxs[0]


    out_snap  = os.path.join(out_dir, f"{icase}.{varname}.snap_doy{plot_doy:03d}-{plot_hour:02d}.pdf")

    field_snap = get_2d_slice(da, snap_tidx, lev_index=lev_idx if is_3d else None,
                              vfactor=vfactor, vshift=vshift)

    # Human-readable time label for this snapshot
    t_val  = pd.Timestamp(ds['time'].values[snap_tidx])
    t_label = t_val.strftime("%Y-%m-%d %H:%M UTC")
    t_day   = noleap_days_since(t_val, t0_date)

    fig2, ax2 = plt.subplots(figsize=(7, 6), constrained_layout=True)

    # Use the time-mean colour limits so the snapshot is comparable to Section 1
    vmin_snap = np.nanpercentile(field_mean, 2)
    vmax_snap = np.nanpercentile(field_mean, 98)
    if(varname == "LW_flux_up_at_model_top"):
        vmin_snap = 0
        vmax_snap = 270

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

    try:
        plt.show()
    except Exception:
        pass
    fig2.clf()
    plt.close(fig2)
    # Free snapshot array and axes handles.
    del field_snap, im2, ax2, cb2

# %%
# Section 3 – Animation
# ===========================================================================

savefig_anim  = True   # Section 3: save animation as MP4

# Frame range: plot frames from anim_t_start to anim_t_end (0-based, inclusive)
# Set anim_t_end = None to animate through all time steps
print(f"  select time index to plot, from 0 to {ds.sizes['time'] - 1}")
print(f"  corresponding timestamp: {pd.Timestamp(ds['time'].values[0])} to {pd.Timestamp(ds['time'].values[-1])}")

plot_st_hour = 13
plot_st_day  = -1  # simulation day since t0_date (2000-01-01); day 46 = Feb 15
#set to -1 to start from the start_date (ts_start) specified at the beginning of the script
if(plot_st_day > -1):
    plot_st_time = np.datetime64(t0_date + pd.Timedelta(days=plot_st_day, hours=plot_st_hour))
else:
    plot_st_time = ds['time'].values[0]

plot_ed_hour = 12
plot_ed_day  = -1   # simulation day since t0_date (2000-01-01); day 76 = Mar 17
if(plot_ed_day > -1):
    plot_ed_time = np.datetime64(t0_date + pd.Timedelta(days=plot_ed_day, hours=plot_ed_hour))
else:
    plot_ed_time = ds['time'].values[-1]

anim_t_start = np.searchsorted(ds['time'].values, plot_st_time)
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

# %%
#change the min and max for certain cases
if(varname == "imse"):
    if(crange_name == "01"):
        #for the beginning period
        vmin_anim = 3.45
        vmax_anim = 3.60
    elif(crange_name == "02"):
        #for the equilibrium period
        vmin_anim = 3.60
        vmax_anim = 3.65
if(varname == "nc_m3_5000m"):
    vmin_anim = 0
    vmax_anim = 1.2e8

if(varname == "ni_m3_5000m"):
    vmin_anim = 0
    vmax_anim = 10000

if(varname == "precip_total_surf_mass_flux"):
    vmin_anim = 0
    if plot_ed_time < np.datetime64('2000-01-11T00:00:00'):
        vmax_anim = 20.0  # or whatever limit you prefer
    elif plot_st_time > np.datetime64('2000-03-01T00:00:00'):
        vmax_anim = 40.0

print(f"  colour limits for animation: vmin={vmin_anim:.3g}, vmax={vmax_anim:.3g}")
# %%

# --- Set up figure ---
fig3, ax3 = plt.subplots(figsize=(7, 6), constrained_layout=True)

# Draw first frame
field_0 = get_2d_slice(da, frame_indices[0],
                       lev_index=lev_idx if is_3d else None,
                       vfactor=vfactor, vshift=vshift)
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


try:
    plt.show()
except Exception:
    pass
fig3.clf()
plt.close(fig3)

# Free animation object and axes handles (the rendered frames stay displayed).
del anim, im3, ax3, cb3

# %%
# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
ds.close()
del ds

del da

print("\nDone.")

# %%
