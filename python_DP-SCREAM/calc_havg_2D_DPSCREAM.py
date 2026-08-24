#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
horiz_avg_DPSCREAM.py

Reads concatenated DP-SCREAM output produced by concat_DPSCREAM.py and
computes the horizontal domain average (arithmetic mean over all ncol
columns) for each requested variable, yielding a pure time series
(or time × lev for 3-D fields) with all spatial information collapsed.
For 3D variables, it is recommended not to use this sciript but use 
another script `` to calculate horizontal average and concatenate for each day.
This is particularly the case for running the script on a login node and with
high-frequency history files. 
Output files are written to out_dir:
  {casename}.{varname}.havg.{stats_type}.{out_tag}.nc
"""
# %%

import os
import sys
import glob
import numpy as np
import xarray as xr

try:
    _script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Running interactively: search cwd and the python_DP-SCREAM sub-folder
    _cwd = os.getcwd()
    _script_dir = (
        _cwd if os.path.isfile(os.path.join(_cwd, "check_output_stream.py"))
        else os.path.join(_cwd, "python_DP-SCREAM")
    )
sys.path.insert(0, _script_dir)
from check_output_stream import get_output_stream

# %%
# ---------------------------------------------------------------------------
# User configuration
# ---------------------------------------------------------------------------
icase      = "dx1km_L150km_RCE01_gpu"
stats_type = "AVERAGE" # "INSTANT" or "AVERAGE" #later modified depending on the variable using the get_output_stream function, which checks the variable name against the output stream types to determine which one it belongs to. If the variable is not found in either stream, it will be skipped with a warning.

file_type="raw" # 'raw' for the direct model output, or 'proc' for post-processed files, 
   #this is used to construct the file name pattern for searching the input files to be concatenated

#used for raw files
frequency = "nhours_x1" # e.g. "nmins_x5" (= 5 minutes), "nhours_x1" (= 1 hour), etc., this is used to construct the file name pattern for searching the input files to be concatenated


# Variables to process.  Use ["all"] to process every ncol-based variable
# found in the input file(s). All variables must have the same file_type, stats_type, and frequency as specified above.
#vartodo = ["VapWaterPath"]  #,"LW_flux_up_at_model_top",VapWaterPath
varname = "LW_flux_up_at_model_top" # 

# Input files produced by concat_DPSCREAM.py.
if(file_type == "raw"):
    in_dir = (f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/run")
else:
    in_dir = (f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/cat_raw")
#in_dir = (f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/run")
# Output directory (created if it does not already exist)
out_dir = (f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/havg")

# Date-range timestamps (inclusive, YYYY-MM-DD)
ts_start = "2000-01-01"
ts_end   = "2000-04-30"

# %%

# ---------------------------------------------------------------------------
# End user configuration
# ---------------------------------------------------------------------------

styear  = int(ts_start[:4]);  stmonth = int(ts_start[5:7]);  stday = int(ts_start[8:10])
edyear  = int(ts_end[:4]);    edmonth = int(ts_end[5:7]);    edday = int(ts_end[8:10])

out_tag = f"{ts_start}_to_{ts_end}"

start_date = np.datetime64(f"{styear:04d}-{stmonth:02d}-{stday:02d}")
end_date   = np.datetime64(f"{edyear:04d}-{edmonth:02d}-{edday:02d}")
date_range = np.arange(start_date, end_date + np.timedelta64(1, 'D'),
                       dtype='datetime64[D]')

os.makedirs(out_dir, exist_ok=True)

# %%

# ---------------------------------------------------------------------------
# Helper: classify ncol-based variables
# ---------------------------------------------------------------------------

def find_ncol_vars(ds, vartodo):
    """Return names and '2D'/'3D' labels for ncol-based variables in ds."""
    matching = []
    dimarr   = []
    targets  = list(ds.data_vars) if vartodo == ["all"] else vartodo

    for varname in targets:
        if varname not in ds:
            print(f"  WARNING: variable '{varname}' not found in dataset,"
                  " skipping.")
            continue
        dims = ds[varname].dims
        if 'ncol' in dims and len(dims) == 2:
            matching.append(varname)
            dimarr.append('2D')
        elif 'ncol' in dims and ('lev' in dims or 'ilev' in dims) \
                and len(dims) == 3:
            matching.append(varname)
            dimarr.append('3D')

    return matching, dimarr


# %%

# ---------------------------------------------------------------------------
# Determine variables to process
# ---------------------------------------------------------------------------
# proc_vars, dim_types = find_ncol_vars(ds, vartodo)
# if not proc_vars:
#     raise RuntimeError(
#         "No processable ncol-based variables found in the input dataset.")

#print(f"\nVariables to process ({len(proc_vars)}):")
# for vn, vd in zip(proc_vars, dim_types):
#     print(f"  {vn}  [{vd}]")

# ---------------------------------------------------------------------------
# Compute horizontal domain average for each variable
# ---------------------------------------------------------------------------
file_suffix  = ".nc"

#for varname, vdim in zip(proc_vars, dim_types):
#for varname in vartodo:
print(f"\n{'='*60}")
print(f"Processing variable : {varname}")
#stats_type = get_output_stream(varname)

if stats_type == "NONE":
    print(f"  WARNING: variable '{varname}' not found in either output stream,"
            " stopping.")

# %%
if(file_type == "raw"):
    file_prefix  = f"{icase}.hist.{stats_type}.{frequency}."
    #infiles = sorted(glob.glob(os.path.join(in_dir, f"{file_prefix}*.nc")))
else:
    file_prefix  = f"{icase}.{varname}.{stats_type}.{frequency}."
    #infiles = sorted(glob.glob(os.path.join(in_dir, f"{file_prefix}*.nc")))
    # infiles = [
    # os.path.join(in_dir,
    #             f"{file_prefix}{str(d)}{file_suffix}")
    # for d in date_range]

date_strs = {str(d) for d in date_range}
infiles = [f for f in sorted(glob.glob(os.path.join(in_dir, f"{file_prefix}*.nc")))
           if os.path.basename(f)[len(file_prefix):len(file_prefix)+10] in date_strs]

print(f"Period    : {ts_start}  to  {ts_end}")
print(f"\nFound {len(infiles)} input file(s):")
for fp in infiles:
    print(f"  {fp}")
# %%

# ---------------------------------------------------------------------------
# Open input dataset
# ---------------------------------------------------------------------------
if len(infiles) == 1:
    ds = xr.open_dataset(infiles[0])
else:
    ds = xr.open_mfdataset(infiles, combine='by_coords', parallel=False)

print("\nDataset overview:")
print(ds)

if 'ncol' not in ds.dims:
    raise ValueError("Input dataset does not contain an 'ncol' dimension.")

time_coord = ds['time']

# %%

# Load data as float32; replace fill / huge values with NaN
data = ds[varname].values.astype(np.float32)
#data[data >= 1e30] = np.nan

if varname.startswith("precip_") and varname.endswith("_surf_mass_flux"):
    if ds[varname].attrs.get("units", "") == "m/s":
        data = data * 3600000.0


dims = ds[varname].dims
vert_dim = None
if 'ncol' in dims and len(dims) == 2:
    vdim = '2D'
elif 'ncol' in dims and ('lev' in dims or 'ilev' in dims) \
        and len(dims) == 3:
    vdim = '3D'
    vert_dim = 'lev' if 'lev' in dims else 'ilev'

ncol_axis = dims.index('ncol')

print("  Computing horizontal domain average ...")
havg = np.nanmean(data, axis=ncol_axis)
hvar = np.nanvar(data, axis=ncol_axis)

if vdim == '2D':
    havg_dims   = ('time',)
    havg_coords = {'time': time_coord}
else:
    havg_dims   = tuple(d for d in dims if d != 'ncol')
    havg_coords = {d: ds[d].values for d in havg_dims if d in ds}
    if 'time' in havg_coords:
        havg_coords['time'] = time_coord

havg_attrs = dict(ds[varname].attrs)
havg_attrs['description'] = (
    'Horizontal domain average over all ncol columns')

hvar_attrs = dict(ds[varname].attrs)
hvar_attrs['description'] = (
    'Horizontal domain variance over all ncol columns')

if 'units' in hvar_attrs and hvar_attrs['units']:
    hvar_attrs['units'] = f"({hvar_attrs['units']})^2"

if varname.startswith("precip_") and varname.endswith("_surf_mass_flux"):
    if ds[varname].attrs.get("units", "") == "m/s":
        havg_attrs['units'] = 'mm/hour'
        hvar_attrs['units'] = '(mm/hour)^2'

data_vars_dict = {
    varname: xr.DataArray(havg, dims=havg_dims, coords=havg_coords,
                          attrs=havg_attrs),
    f"{varname}_var": xr.DataArray(hvar, dims=havg_dims, coords=havg_coords,
                                   attrs=hvar_attrs)
}

ds_opened_extra = None
if vdim == '3D':
    # If using processed files, we might need to load ps and hybrid coords from raw files
    ds_extra = ds
    needed_extra = ['ps']
    if vert_dim == 'lev':
        needed_extra.extend(['hyam', 'hybm'])
    elif vert_dim == 'ilev':
        needed_extra.extend(['hyai', 'hybi'])
        
    missing_extra = [v for v in needed_extra if v not in ds_extra]
    if missing_extra:
        raw_dir = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/run"
        raw_prefix = f"{icase}.hist.{stats_type}.{frequency}."
        raw_files = sorted(glob.glob(os.path.join(raw_dir, f"{raw_prefix}*.nc")))
        raw_infiles = [f for f in raw_files if os.path.basename(f)[len(raw_prefix):len(raw_prefix)+10] in date_strs]
        if raw_infiles:
            if len(raw_infiles) == 1:
                ds_opened_extra = xr.open_dataset(raw_infiles[0])
            else:
                ds_opened_extra = xr.open_mfdataset(raw_infiles, combine='by_coords', parallel=False)
            ds_extra = ds_opened_extra

    if 'ps' in ds_extra:
        ps_data = ds_extra['ps'].values.astype(np.float32)
        ps_dims = ds_extra['ps'].dims
        if 'ncol' in ps_dims:
            ps_ncol_axis = ps_dims.index('ncol')
            ps_havg = np.nanmean(ps_data, axis=ps_ncol_axis)
            ps_havg_dims = tuple(d for d in ps_dims if d != 'ncol')
            ps_havg_coords = {d: ds_extra[d].values for d in ps_havg_dims if d in ds_extra}
            if 'time' in ps_havg_coords:
                ps_havg_coords['time'] = time_coord
            
            ps_attrs = dict(ds_extra['ps'].attrs)
            ps_attrs['description'] = 'Horizontal domain average over all ncol columns'
            
            data_vars_dict['ps'] = xr.DataArray(
                ps_havg, dims=ps_havg_dims, coords=ps_havg_coords, attrs=ps_attrs
            )
        else:
            data_vars_dict['ps'] = ds_extra['ps']

    for coeff in needed_extra[1:]:
        if coeff in ds_extra:
            data_vars_dict[coeff] = ds_extra[coeff]

ds_havg = xr.Dataset(
    data_vars_dict,
    attrs={
        'processing' : 'horizontal domain average (mean over ncol) and variance',
    }
)

if vdim == '3D':
    if vert_dim == 'lev' and 'lev' in ds_havg:
        ds_havg['lev'].attrs = {'units': 'mb', 'long_name': 'hybrid level at midpoints'}
    elif vert_dim == 'ilev' and 'ilev' in ds_havg:
        ds_havg['ilev'].attrs = {'units': 'mb', 'long_name': 'hybrid level at interfaces'}

havg_out = os.path.join(
    out_dir,
    f"{icase}.{varname}.havg.{stats_type}.{out_tag}.nc")
ds_havg.to_netcdf(havg_out, encoding={'time': {'_FillValue': None}}, unlimited_dims=["time"])
print(f"  Saved domain-average: {havg_out}")

del ds_havg, data, havg, hvar
if ds_opened_extra is not None:
    ds_opened_extra.close()
# %%

ds.close()
print(f"\n{'='*60}")
print("Done.")

# %%
