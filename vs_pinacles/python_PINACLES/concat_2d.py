#!/usr/bin/env python
# concat_2d.py
#
# Concatenate a selected 2D field variable from hourly PINACLES output files
# into daily NetCDF files (24 time samples per day).
#
# Usage:
#   module load python
#   conda activate pinacles_share
#   python concat_2d.py
#
# Environment: pinacles_share (/global/common/software/m1867/python/pinacles_share)
# or dpscream_analysis
# %%
import os
import glob
import re
import numpy as np
import xarray as xr
import h5py

# %%
# =============================================================================
# CONFIGURATION
# =============================================================================

icase   = "RCE06_dx1km_150x150km"

in_dir  = (
    f"/pscratch/sd/w/wcmca1/PINACLES/"
    f"{icase}/simlinks/fields2d"
)
out_dir = f"/pscratch/sd/w/wcmca1/PINACLES/{icase}/cat_raw"

# Variable to extract from each hourly file.
# Available 2D variables include: imse, LWP, IWP, RAINNC, RAINNCV, T2, qv2,
# lhf, shf, slp, u10, v10, windspeed10, windspeed_sfc, ref, pseudo-albedo,
# cp_base, cp_depth, cp_intensity, surface_lw_down, surface_lw_up,
# surface_sw_down, surface_sw_up, toa_lw_down, toa_lw_up, toa_sw_down,
# toa_sw_up, visibility, and height-level fields (e.g., T_100.0, qv_500.0, ...)
#varname = "qni1_9900.0_m3"
varname = "toa_lw_up" #"rain_rate" #"toa_lw_up" 

# File minute pattern for specifying frequency.
# Use "00m" for hourly data (only read files on the hour).
# Use "*m" to read all available frequencies (e.g., every 10 minutes).
minute_pattern = "00m"

# Day range to process (inclusive, 0-based integer day numbers matching the
# leading digits in filenames, e.g. 00d-HHh-... → day 0).
day_start = 0
day_end   = 55   # adjust to the last available simulation day

# =============================================================================


# %%

def parse_hour(filename):
    """Return the integer hour from a filename like '01d-03h-00m-00s-000ms.h5'."""
    m = re.match(r'^\d+d-(\d+)h-', os.path.basename(filename))
    return int(m.group(1)) if m else None


# %%

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
os.makedirs(out_dir, exist_ok=True)

print(f"Variable  : {varname}")
print(f"Input dir : {in_dir}")
print(f"Output dir: {out_dir}")
print(f"Day range : {day_start} – {day_end}")

# Determine if unit conversion is needed
is_m3_conversion = False
invarname = varname
z_level_str = ""
if varname == "rain_rate":
    invarname = "RAINNC"
elif varname.endswith('_m3') and (varname.startswith('qnc_') or varname.startswith('qni1_')):
    is_m3_conversion = True
    invarname = varname[:-3]
    if varname.startswith('qnc_'):
        z_level_str = invarname[4:]
    elif varname.startswith('qni1_'):
        z_level_str = invarname[5:]

# Read X and Y coordinates once from the first available file
all_files = sorted(glob.glob(os.path.join(in_dir, "*.h5")))
if not all_files:
    raise FileNotFoundError(f"No .h5 files found in {in_dir}")

with h5py.File(all_files[0], 'r') as f0:
    if invarname not in f0:
        if varname == "toa_lw_up" and "LW_UP_TOA" in f0:
            invarname = "LW_UP_TOA"
            print("Variable 'toa_lw_up' not found in input. Reading 'LW_UP_TOA' instead.")
        else:
            raise KeyError(
                f"Variable '{invarname}' not found in {all_files[0]}. "
                f"Available keys: {list(f0.keys())}"
            )
    x_vals   = f0['X'][...]          # shape (nx,)
    y_vals   = f0['Y'][...]          # shape (ny,)
    var_attrs = dict(f0[invarname].attrs)

if is_m3_conversion:
    var_attrs['units'] = '1/m3'
if varname == "rain_rate":
    var_attrs['units'] = 'mm/h'
    var_attrs['long_name'] = 'hourly precipitation rate'

# Remove HDF5-internal attributes that do not transfer cleanly to NetCDF
for _key in ('DIMENSION_LIST', 'CLASS', 'NAME', 'REFERENCE_LIST'):
    var_attrs.pop(_key, None)


# %%

# ---------------------------------------------------------------------------
# Main loop: one output file per simulation day
# ---------------------------------------------------------------------------
# Create a list of all matching files to find previous files for rate calculations
all_matching_pattern = os.path.join(in_dir, f"*-*-{minute_pattern}-*.h5")
all_matching_files = sorted(glob.glob(all_matching_pattern))

prev_file_cache = {"fpath": None, "t": None, "v": None}

for iday in range(day_start, day_end + 1):
    day_files = sorted(glob.glob(os.path.join(in_dir, f"{iday:02d}d-*-{minute_pattern}-*.h5")))

    print(f"\n{'='*55}")
    print(f"Day {iday:02d}: found {len(day_files)} file(s)")

    if not day_files:
        print(f"  No files found for day {iday:02d}, skipping.")
        continue

    time_list = []
    var_list  = []

    for fpath in day_files:
        hour = parse_hour(fpath)
        with h5py.File(fpath, 'r') as hf:
            t = hf['time'][...]      # shape (1,)  — seconds since sim start
            
            if varname == "rain_rate":
                v_current = hf[invarname][...]
                
                idx = all_matching_files.index(fpath)
                if idx == 0:
                    v = np.zeros_like(v_current)
                else:
                    prev_fpath = all_matching_files[idx - 1]
                    if prev_file_cache["fpath"] == prev_fpath:
                        prev_t = prev_file_cache["t"]
                        prev_v = prev_file_cache["v"]
                    else:
                        with h5py.File(prev_fpath, 'r') as hf_prev:
                            prev_t = hf_prev['time'][...]
                            prev_v = hf_prev[invarname][...]
                    
                    dt_hours = (t[0] - prev_t[0]) / 3600.0
                    if dt_hours > 0:
                        v = (v_current - prev_v) / dt_hours
                    else:
                        v = np.zeros_like(v_current)
                        
                prev_file_cache["fpath"] = fpath
                prev_file_cache["t"] = t
                prev_file_cache["v"] = v_current
            else:
                v = hf[invarname][...]     # shape (1, ny, nx)
            
            if is_m3_conversion:
                T_field = hf[f'T_{z_level_str}'][...]
                p_field = hf[f'p_hydrostatic_{z_level_str}'][...]
                rho = p_field / (287.042 * T_field)
                v = v * rho
        time_list.append(float(t[0]))
        var_list.append(v[0, ...])   # shape (ny, nx)
        #print(f"  Hour {hour:02d}: time={t[0]:.0f} s, {varname} shape={v.shape}")

    time_arr = np.array(time_list) / 3600.0   # Convert seconds to hours
    var_arr  = np.stack(var_list, axis=0)     # (nhours, ny, nx)

    ds = xr.Dataset(
        {
            varname: xr.DataArray(
                var_arr,
                dims=['time', 'y', 'x'],
                attrs=var_attrs,
            )
        },
        coords={
            'time': xr.DataArray(
                time_arr,
                dims=['time'],
                attrs={
                    'units': 'hours since 2000-01-01 00:00:00.000000',
                    'calendar': 'noleap',
                    'long_name': 'time',
                }
            ),
            'x': xr.DataArray(
                x_vals,
                dims=['x'],
                attrs={'units': 'm', 'long_name': 'x coordinate'},
            ),
            'y': xr.DataArray(
                y_vals,
                dims=['y'],
                attrs={'units': 'm', 'long_name': 'y coordinate'},
            ),
        },
        attrs={
            'case':        icase,
            'variable':    varname,
            'day':         iday,
            'description': (
                f'Daily concatenation of PINACLES 2D field output '
                f'({varname}), simulation day {iday:02d}'
            ),
            'rain_rate_note': 'The variable rain_rate at time t represents the accumulated rain between the previous output time (t-1) and current output time (t).',
            'source_dir':  in_dir,
        },
    )

    out_file = os.path.join(out_dir, f"{icase}.{varname}.day{iday:02d}.nc")
    ds.to_netcdf(
        out_file, 
        mode='w', 
        unlimited_dims=['time'],
        encoding={
            'time': {'_FillValue': None},
            'x': {'_FillValue': None},
            'y': {'_FillValue': None},
            varname: {'dtype': 'float32'}
        }
    )
    print(f"  Written : {out_file}")
    ds.close()

print("\nDone.")

# %%
