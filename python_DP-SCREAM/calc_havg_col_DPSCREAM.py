#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calculate horizontal domain average and variance of a given 3D variable from DP-SCREAM output for a single day.
It computes the statistics per file to save memory (suitable for login nodes) and concatenates all times
into a single daily output file.

Usage:
    module load python
    conda activate dpscream_analysis
    python calc_havg_col_DPSCREAM.py --varname T_mid --iyear 2000 --imonth 1 --iday 1 [--icase ICASE] ...
"""
# %%
import argparse
import os
import glob
import numpy as np
import xarray as xr

# %%
parser = argparse.ArgumentParser(
    description="Calculate horizontal average for a single history file."
)
parser.add_argument("--varname", required=True,
                    help="Name of the variable to process (e.g., 'T_mid')")
parser.add_argument("--icase",   default="RCE09_dx3km_gpu",
                    help="Case name")
parser.add_argument("--infile",  default=None,
                    help="Input file name or path (overrides --iyear/--imonth/--iday/--isecond)")
parser.add_argument("--iyear",   type=int, default=2000,
                    help="Year component of timestamp (default: 2000)")
parser.add_argument("--imonth",  type=int, default=1,
                    help="Month component of timestamp (default: 1)")
parser.add_argument("--iday",    type=int, default=1,
                    help="Day component of timestamp (default: 1)")
parser.add_argument("--isecond", type=int, default=0,
                    help="Second component of timestamp (default: 0)")
parser.add_argument("--ifreq",  type=str, default="nhours_x1",
                    help="Input frequency (default: nhours_x1)")
parser.add_argument("--stats_type",  type=str, default="INSTANT",
                    help="Stats type (default: INSTANT)")

try:
    __file__
    args = parser.parse_args()
except NameError:
    # running interactively
    class Args:
        varname = "rrtmgp_T_mid_tend"
        icase = "RCE10_dx3km_gpu"
        infile = None
        iyear = 2000
        imonth = 1
        iday = 1
        isecond = 0
        ifreq = "nhours_x1"
        stats_type = "AVERAGE"
    args = Args()

varname = args.varname
icase   = args.icase
infile  = args.infile
iyear   = args.iyear
imonth  = args.imonth
iday    = args.iday
isecond = args.isecond
ifreq   = args.ifreq
stats_type = args.stats_type

# %%
in_dir  = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/run"
out_dir = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/havg"
os.makedirs(out_dir, exist_ok=True)

import re

if infile is not None:
    # get time stamp from file name
    basename = os.path.basename(infile)
    match = re.search(r'\d{4}-\d{2}-\d{2}-\d{5}', basename)
    if not match:
        raise ValueError(f"Could not extract timestamp from filename: {basename}")
    timestamp = match.group()
else:
    timestamp = f"{iyear:04d}-{imonth:02d}-{iday:02d}-{isecond:05d}"
    in_basename  = f"{icase}.hist.{stats_type}.{ifreq}.{timestamp}.nc"
    infile = os.path.join(in_dir, in_basename)

out_basename = f"{icase}.{varname}.havg.{stats_type}.{ifreq}.{timestamp}.nc"
havg_out = os.path.join(out_dir, out_basename)

print(f"Reading: {infile}")
ds = xr.open_dataset(infile)

if varname not in ds:
    ds.close()
    raise ValueError(f"Variable '{varname}' not found in the dataset {infile}.")

# %%
time_coord = ds['time']
data = ds[varname].values.astype(np.float32)

dims = ds[varname].dims
vert_dim = None
if 'ncol' in dims and len(dims) == 2:
    vdim = '2D'
elif 'ncol' in dims and ('lev' in dims or 'ilev' in dims) and len(dims) == 3:
    vdim = '3D'
    vert_dim = 'lev' if 'lev' in dims else 'ilev'
else:
    ds.close()
    raise ValueError(f"Variable '{varname}' does not have expected dimensions: {dims}")

ncol_axis = dims.index('ncol')

print(f"  Computing horizontal domain average for {varname} ...")
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
havg_attrs['description'] = 'Horizontal domain average over all ncol columns'

hvar_attrs = dict(ds[varname].attrs)
hvar_attrs['description'] = 'Horizontal domain variance over all ncol columns'
if 'units' in hvar_attrs and hvar_attrs['units']:
    hvar_attrs['units'] = f"({hvar_attrs['units']})^2"

data_vars_dict = {
    varname: xr.DataArray(havg, dims=havg_dims, coords=havg_coords, attrs=havg_attrs),
    f"{varname}_var": xr.DataArray(hvar, dims=havg_dims, coords=havg_coords, attrs=hvar_attrs)
}

if vdim == '3D':
    if 'ps' in ds:
        ps_data = ds['ps'].values.astype(np.float32)
        ps_dims = ds['ps'].dims
        if 'ncol' in ps_dims:
            ps_ncol_axis = ps_dims.index('ncol')
            ps_havg = np.nanmean(ps_data, axis=ps_ncol_axis)
            ps_havg_dims = tuple(d for d in ps_dims if d != 'ncol')
            ps_havg_coords = {d: ds[d].values for d in ps_havg_dims if d in ds}
            if 'time' in ps_havg_coords:
                ps_havg_coords['time'] = time_coord
            
            ps_attrs = dict(ds['ps'].attrs)
            ps_attrs['description'] = 'Horizontal domain average over all ncol columns'
            
            data_vars_dict['ps'] = xr.DataArray(
                ps_havg, dims=ps_havg_dims, coords=ps_havg_coords, attrs=ps_attrs
            )
        else:
            data_vars_dict['ps'] = ds['ps']
    else:
        print("  WARNING: 'ps' variable not found in dataset. Skipping ps.")

    needed_extra = []
    if vert_dim == 'lev':
        needed_extra.extend(['hyam', 'hybm'])
    elif vert_dim == 'ilev':
        needed_extra.extend(['hyai', 'hybi'])

    for coeff in needed_extra:
        if coeff in ds:
            data_vars_dict[coeff] = ds[coeff]

ds_havg = xr.Dataset(
    data_vars_dict,
    attrs={
        'processing': 'horizontal domain average (mean over ncol) and variance for a single file',
        'source_files': os.path.basename(infile),
    }
)

if vdim == '3D':
    if vert_dim == 'lev' and 'lev' in ds_havg:
        ds_havg['lev'].attrs = {'units': 'mb', 'long_name': 'hybrid level at midpoints'}
    elif vert_dim == 'ilev' and 'ilev' in ds_havg:
        ds_havg['ilev'].attrs = {'units': 'mb', 'long_name': 'hybrid level at interfaces'}

# %%
print(f"\nWriting: {havg_out}")
ds_havg.to_netcdf(havg_out, encoding={'time': {'_FillValue': None}}, unlimited_dims=["time"])
print("Done.")

ds.close()
del ds_havg, data, havg, hvar
# %%
