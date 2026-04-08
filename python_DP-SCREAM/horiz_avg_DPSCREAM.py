#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
horiz_avg_DPSCREAM.py

Reads concatenated DP-SCREAM output produced by concat_DPSCREAM.py and
computes the horizontal domain average (arithmetic mean over all ncol
columns) for each requested variable, yielding a pure time series
(or time × lev for 3-D fields) with all spatial information collapsed.

Output files are written to out_dir:
  {casename}.{varname}.havg.{stats_type}.{out_tag}.nc
"""
# %%

import os
import glob
import numpy as np
import xarray as xr

# %%
# ---------------------------------------------------------------------------
# User configuration
# ---------------------------------------------------------------------------
icase      = "scream_cpu_dpxx_RCE_dx1km"
stats_type = "INSTANT"
varname    = "VapWaterPath"

# Variables to process.  Use ["all"] to process every ncol-based variable
# found in the input file(s).
vartodo = [varname]

# Input files produced by concat_DPSCREAM.py.
in_dir = (f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases"
          f"/{icase}/processed")

# Date-range timestamps (inclusive, YYYY-MM-DD)
ts_start = "2000-01-01"
ts_end   = "2000-01-25"

# Output directory (created if it does not already exist)
out_dir = in_dir

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

    for vname in targets:
        if vname not in ds:
            print(f"  WARNING: variable '{vname}' not found in dataset,"
                  " skipping.")
            continue
        dims = ds[vname].dims
        if 'ncol' in dims and len(dims) == 2:
            matching.append(vname)
            dimarr.append('2D')
        elif 'ncol' in dims and ('lev' in dims or 'ilev' in dims) \
                and len(dims) == 3:
            matching.append(vname)
            dimarr.append('3D')

    return matching, dimarr

# %%



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
#for vname, vdim in zip(proc_vars, dim_types):
for vname in vartodo:
    print(f"\n{'='*60}")
    print(f"Processing variable : {vname}")

    infiles = [
        os.path.join(in_dir,
                    f"{icase}.{vname}.hist.{stats_type}.{str(d)}.nc")
        for d in date_range]

    print(f"Period    : {ts_start}  to  {ts_end}")
    print(f"\nFound {len(infiles)} input file(s):")
    for fp in infiles:
        print(f"  {fp}")

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
    lev_vals   = ds['lev'].values if 'lev' in ds else None

    # Load data as float32; replace fill / huge values with NaN
    data = ds[vname].values.astype(np.float32)
    #data[data >= 1e30] = np.nan

    dims = ds[vname].dims
    if 'ncol' in dims and len(dims) == 2:
        vdim = '2D'
    elif 'ncol' in dims and ('lev' in dims or 'ilev' in dims) \
            and len(dims) == 3:
        vdim = '3D'

    # Ensure 3-D data is (time, ncol, lev)
    if vdim == '3D':
        orig_dims = ds[vname].dims
        if orig_dims.index('ncol') == 1:
            # (time, lev, ncol) -> (time, ncol, lev)
            data = data.transpose(0, 2, 1)

    # axis=1 collapses ncol:
    #   2-D: (ntime, ncol)       -> (ntime,)
    #   3-D: (ntime, ncol, nlev) -> (ntime, nlev)
    print("  Computing horizontal domain average ...")
    havg = np.nanmean(data, axis=1)
    hvar = np.nanvar(data, axis=1)

    if vdim == '2D':
        havg_dims   = ('time',)
        havg_coords = {'time': time_coord}
    else:
        havg_dims   = ('time', 'lev')
        havg_coords = {'time': time_coord, 'lev': lev_vals}

    havg_attrs = dict(ds[vname].attrs)
    havg_attrs['description'] = (
        'Horizontal domain average over all ncol columns')

    hvar_attrs = dict(ds[vname].attrs)
    hvar_attrs['description'] = (
        'Horizontal domain variance over all ncol columns')
    if 'units' in hvar_attrs and hvar_attrs['units']:
        hvar_attrs['units'] = f"({hvar_attrs['units']})^2"

    ds_havg = xr.Dataset(
        {vname: xr.DataArray(havg, dims=havg_dims, coords=havg_coords,
                             attrs=havg_attrs),
         f"{vname}_var": xr.DataArray(hvar, dims=havg_dims, coords=havg_coords,
                                      attrs=hvar_attrs)},
        attrs={
            'processing' : 'horizontal domain average (mean over ncol) and variance',
        }
    )
    if lev_vals is not None and vdim == '3D':
        ds_havg['lev'].attrs = {
            'units': 'mb', 'long_name': 'hybrid level at midpoints'}

    havg_out = os.path.join(
        out_dir,
        f"{icase}.{vname}.havg.{stats_type}.{out_tag}.nc")
    ds_havg.to_netcdf(havg_out)
    print(f"  Saved domain-average: {havg_out}")

    del ds_havg, data, havg, hvar

ds.close()
print(f"\n{'='*60}")
print("Done.")
