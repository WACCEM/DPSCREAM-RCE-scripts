#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regrid_avg_DPSCREAM.py

Reads concatenated DP-SCREAM output produced by concat_DPSCREAM.py and
performs two post-processing steps on each requested variable:

  1. Horizontal domain average  – arithmetic mean over every ncol column,
     yielding a pure time (+ lev for 3-D) series with all spatial
     information collapsed.

  2. Cartesian regridding       – maps the unstructured ncol grid to a
     regular lat/lon grid via a pre-computed ESMF weight file, following
     the same approach as remap/regrid_dpxx_output.py.

Output files are written to out_dir:
  {casename}.{varname}.havg.{stats_type}.{out_tag}.nc   – horizontal average
  {casename}.{varname}.regrid.{stats_type}.{out_tag}.nc – Cartesian-regridded field
"""
# %%

import os
import glob
import numpy as np
import xarray as xr
import netCDF4 as nc4
from scipy.sparse import csr_matrix
# %%
# ---------------------------------------------------------------------------
# User configuration
# ---------------------------------------------------------------------------
icase      = "scream_cpu_dpxx_RCE_dx1km"
stats_type = "AVERAGE"
varname = "LW_flux_up_at_model_top"

# Variables to process.  Use ["all"] to process every ncol-based variable
# found in the input file(s).
vartodo = [varname]

# %%

# Input file(s) produced by concat_DPSCREAM.py.
# Accepts either a single file path or a glob pattern.
# Multiple matching files are sorted and concatenated along the time axis.
in_dir  = (f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases"
           f"/{icase}/processed")


# Date-range timestamps (inclusive) matching filename format YYYY-MM-DD
ts_start = "2000-01-01"
ts_end   = "2000-01-03"

# ESMF weight file produced by ESMF_RegridWeightGen.
# Maps from the unstructured DP-SCREAM source grid (ncol columns) to the
# desired regular Cartesian destination grid.
weightdir  = "/global/cfs/cdirs/wcm_shr/DP-SCREAM/remap/"
weightfile = ("DPSCREAM_RCE_dx1km_600x600km_to_PINACLES_YX_dx1km_"
              "600x600km_conserve.nc")

# Destination grid spacing in metres – used to compute Cartesian x/y
# cell-centre coordinates (dst_dx/2, 3*dst_dx/2, …) in the regridded output.
dst_dx = 1500.0

# ---------------------------------------------------------------------------
# End user configuration
# ---------------------------------------------------------------------------
styear = int(ts_start[:4])
stmonth = int(ts_start[5:7])
stday = int(ts_start[8:10])

edyear = int(ts_end[:4])
edmonth = int(ts_end[5:7])
edday = int(ts_end[8:10])

print(f"Period    : {ts_start}  to  {ts_end}")

start_date = np.datetime64(f"{styear:04d}-{stmonth:02d}-{stday:02d}")
end_date = np.datetime64(f"{edyear:04d}-{edmonth:02d}-{edday:02d}")

date_range = np.arange(start_date, end_date + np.timedelta64(1, 'D'), dtype='datetime64[D]')

ndays = len(date_range)
infiles = []

for idct in range(ndays):
    date_str = str(date_range[idct])
    infiles.append(os.path.join(in_dir, f"{icase}.{varname}.hist.{stats_type}.{date_str}.nc"))

print(f"\nFound {len(infiles)} input file(s):")
for fp in infiles:
    print(f"  {fp}")

# Output directory (created if it does not already exist)
out_dir = in_dir # os.path.join(in_dir, "post_processed")

out_tag = f"{ts_start}_to_{ts_end}"
# %%
weightfile_path = os.path.join(weightdir, weightfile)
if not os.path.isfile(weightfile_path):
    raise FileNotFoundError(
        f"ESMF weight file not found: {weightfile_path}")

os.makedirs(out_dir, exist_ok=True)

# ---------------------------------------------------------------------------
# Helper functions  (load/apply ESMF weights; ported from regrid_dpxx_output.py)
# ---------------------------------------------------------------------------

def load_esmf_weights(wfile):
    """Load an ESMF offline weight file and return sparse matrix + grid info.

    Parameters
    ----------
    wfile : str
        Path to the ESMF/SCRIP-format weight file.

    Returns
    -------
    W      : scipy.sparse.csr_matrix, shape (n_b, n_a)
    x_out  : 1-D array – destination x / longitude coordinate values
    y_out  : 1-D array – destination y / latitude  coordinate values
    nx_out : int – number of destination x (longitude) points
    ny_out : int – number of destination y (latitude)  points
    n_a    : int – number of source columns (must equal ncol in model output)
    """
    f      = nc4.Dataset(wfile)
    col    = f.variables['col'][:].astype(int) - 1   # 0-indexed source
    row    = f.variables['row'][:].astype(int) - 1   # 0-indexed destination
    S      = f.variables['S'][:]
    n_a    = len(f.dimensions['n_a'])
    n_b    = len(f.dimensions['n_b'])
    # dst_grid_dims is in Fortran order: [fast, slow] = [ny, nx] for YX grid
    dst_dims = f.variables['dst_grid_dims'][:]
    ny_out   = int(dst_dims[0])   # fast  dim = lat
    nx_out   = int(dst_dims[1])   # slow  dim = lon
    xc_b = f.variables['xc_b'][:]
    yc_b = f.variables['yc_b'][:]
    f.close()

    W = csr_matrix((S, (row, col)), shape=(n_b, n_a))

    # Flat index k = ix * ny_out + iy  →  reshape to (nx_out, ny_out)
    xc_b_2d = xc_b.reshape(nx_out, ny_out)
    yc_b_2d = yc_b.reshape(nx_out, ny_out)
    x_out   = xc_b_2d[:, 0]   # unique lon values (one per lon strip)
    y_out   = yc_b_2d[0, :]   # unique lat values (one per lat strip)

    return W, x_out, y_out, nx_out, ny_out, n_a

def apply_esmf_weights(data, W, ny_out, nx_out):
    """Apply the ESMF sparse weight matrix to data on the unstructured grid.

    Parameters
    ----------
    data   : ndarray
        Shape (ntime, ncol)        for 2-D fields, or
               (ntime, ncol, nlev) for 3-D fields.
    W      : scipy.sparse.csr_matrix, shape (n_b, n_a), n_a == ncol
    ny_out : int – number of destination y (latitude) points
    nx_out : int – number of destination x (longitude) points

    Returns
    -------
    out : ndarray
        Shape (ntime, ny_out, nx_out)         for 2-D fields, or
               (ntime, nlev, ny_out, nx_out)  for 3-D fields.
    """
    ntime = data.shape[0]

    if data.ndim == 2:
        out = np.empty((ntime, ny_out, nx_out), dtype=np.float32)
        for t in range(ntime):
            # Flat k = ix*ny_out + iy; reshape to (nx,ny) then transpose
            # to give (ny, nx) = (lat, lon)
            out[t] = W.dot(data[t]).reshape(nx_out, ny_out).T

    elif data.ndim == 3:
        nlev = data.shape[2]
        out  = np.empty((ntime, nlev, ny_out, nx_out), dtype=np.float32)
        for t in range(ntime):
            for k in range(nlev):
                out[t, k] = W.dot(data[t, :, k]).reshape(nx_out, ny_out).T

    return out

def find_ncol_vars(ds, vartodo):
    """Return lists of variable names and dimension labels for ncol-based vars.

    Parameters
    ----------
    ds      : xarray.Dataset
    vartodo : list of str, or ["all"]

    Returns
    -------
    matching : list of str   – variable names to process
    dimarr   : list of str   – '2D' or '3D' for each matching variable
    """
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
# ---------------------------------------------------------------------------
# Load ESMF weights
# ---------------------------------------------------------------------------
print("Loading ESMF weight file ...")
W_esmf, x_esmf, y_esmf, nx_esmf, ny_esmf, n_a_esmf = \
    load_esmf_weights(weightfile_path)
print(f"  src cols : {n_a_esmf}")
print(f"  dst grid : {ny_esmf} (lat) x {nx_esmf} (lon)")

# %%
# ---------------------------------------------------------------------------
# Open input files
# ---------------------------------------------------------------------------

if len(infiles) == 1:
    ds = xr.open_dataset(infiles[0])
else:
    ds = xr.open_mfdataset(infiles, combine='by_coords', parallel=False)

print("\nDataset overview:")
print(ds)

# %%
# Validate ncol size against the weight file
if 'ncol' not in ds.dims:
    raise ValueError("Input dataset does not contain an 'ncol' dimension.")
ncol_in = ds.dims['ncol']
if ncol_in != n_a_esmf:
    raise ValueError(
        f"ncol in input ({ncol_in}) does not match weight file n_a "
        f"({n_a_esmf}).  Ensure the weight file was built for this grid.")

# Retrieve coordinate arrays
time_coord = ds['time']
lev_vals   = ds['lev'].values if 'lev' in ds else None

# %%
# ---------------------------------------------------------------------------
# Determine variables to process
# ---------------------------------------------------------------------------
proc_vars, dim_types = find_ncol_vars(ds, vartodo)
if not proc_vars:
    raise RuntimeError(
        "No processable ncol-based variables found in the input dataset.")

print(f"\nVariables to process ({len(proc_vars)}):")
for vn, vd in zip(proc_vars, dim_types):
    print(f"  {vn}  [{vd}]")

# %%

# ---------------------------------------------------------------------------
# Cartesian x/y cell-centre coordinates for the regridded output
# ---------------------------------------------------------------------------
x_meters = np.arange(nx_esmf) * dst_dx + dst_dx / 2.0
y_meters = np.arange(ny_esmf) * dst_dx + dst_dx / 2.0

fill_val = np.float32(9.96921e+36)

# %%

# ---------------------------------------------------------------------------
# Process each variable
# ---------------------------------------------------------------------------
for vname, vdim in zip(proc_vars, dim_types):
    print(f"\n{'='*60}")
    print(f"Processing variable : {vname}  ({vdim})")

    # -----------------------------------------------------------------------
    # Extract data as float32 numpy array; replace fill / huge values with NaN
    # so they propagate cleanly through the sparse dot product.
    # -----------------------------------------------------------------------
    data = ds[vname].values.astype(np.float32)
    data[data >= 1e30] = np.nan

    # Ensure 3-D data is (time, ncol, lev); transpose if (time, lev, ncol)
    if vdim == '3D':
        orig_dims = ds[vname].dims
        if orig_dims.index('ncol') == 1:
            # (time, lev, ncol) -> (time, ncol, lev)
            data = data.transpose(0, 2, 1)
        # else already (time, ncol, lev) — no action needed

    # -----------------------------------------------------------------------
    # 1. Horizontal domain average (mean over ncol)
    # -----------------------------------------------------------------------
    print("  Computing horizontal domain average ...")
    # axis=1 collapses the ncol dimension for both 2-D and 3-D cases:
    #   2-D: (ntime, ncol)       -> (ntime,)
    #   3-D: (ntime, ncol, nlev) -> (ntime, nlev)
    havg = np.nanmean(data, axis=1)

    if vdim == '2D':
        havg_dims   = ('time',)
        havg_coords = {'time': time_coord}
    else:
        havg_dims   = ('time', 'lev')
        havg_coords = {'time': time_coord, 'lev': lev_vals}

    havg_attrs = dict(ds[vname].attrs)
    havg_attrs['description'] = (
        'Horizontal domain average over all ncol columns')

    ds_havg = xr.Dataset(
        {vname: xr.DataArray(havg, dims=havg_dims, coords=havg_coords,
                             attrs=havg_attrs)},
        attrs={
            'source_file' : str(infiles),
            'processing'  : 'horizontal domain average (mean over ncol)',
        }
    )
    if lev_vals is not None and vdim == '3D':
        ds_havg['lev'].attrs = {
            'units': 'mb', 'long_name': 'hybrid level at midpoints'}

    havg_out = os.path.join(
        out_dir,
        f"{icase}.{vname}.havg.{stats_type}.{out_tag}.nc")
    ds_havg.to_netcdf(havg_out)
    print(f"  Saved domain-average  : {havg_out}")
    del ds_havg

    # -----------------------------------------------------------------------
    # 2. Cartesian regridding via ESMF weights
    # -----------------------------------------------------------------------
    print("  Applying ESMF weights for Cartesian regridding ...")
    var_regrid = apply_esmf_weights(data, W_esmf, ny_esmf, nx_esmf)

    # Replace NaN with the standard fill value for NetCDF compliance
    var_regrid = np.where(np.isnan(var_regrid), fill_val, var_regrid)

    regrid_attrs = dict(ds[vname].attrs)
    regrid_attrs['description'] = (
        'Regridded from unstructured ncol grid to regular Cartesian '
        'lat/lon grid via ESMF conservative weights')

    if vdim == '2D':
        # var_regrid: (ntime, ny_esmf, nx_esmf)
        regrid_da = xr.DataArray(
            var_regrid,
            dims=('time', 'lat', 'lon'),
            coords={
                'time': time_coord,
                'lat' : y_esmf,
                'lon' : x_esmf,
            },
            attrs=regrid_attrs,
        )
    else:
        # var_regrid: (ntime, nlev, ny_esmf, nx_esmf)
        regrid_da = xr.DataArray(
            var_regrid,
            dims=('time', 'lev', 'lat', 'lon'),
            coords={
                'time': time_coord,
                'lev' : lev_vals,
                'lat' : y_esmf,
                'lon' : x_esmf,
            },
            attrs=regrid_attrs,
        )

    # x/y Cartesian coordinates in metres as auxiliary coordinate variables
    x_coord = xr.DataArray(
        x_meters, dims='lon',
        attrs={'units': 'm', 'long_name': 'x coordinate (west-east)'})
    y_coord = xr.DataArray(
        y_meters, dims='lat',
        attrs={'units': 'm', 'long_name': 'y coordinate (south-north)'})

    ds_regrid = xr.Dataset(
        {vname: regrid_da, 'x': x_coord, 'y': y_coord},
        attrs={
            'source_file' : str(infiles),
            'weight_file' : weightfile_path,
            'processing'  : ('ESMF conservative regridding from unstructured'
                             ' ncol grid to regular Cartesian grid'),
        }
    )
    ds_regrid['lat'].attrs = {
        'units': 'degrees_north', 'long_name': 'latitude'}
    ds_regrid['lon'].attrs = {
        'units': 'degrees_east', 'long_name': 'longitude'}
    if lev_vals is not None and vdim == '3D':
        ds_regrid['lev'].attrs = {
            'units': 'mb', 'long_name': 'hybrid level at midpoints'}

    regrid_out = os.path.join(
        out_dir,
        f"{icase}.{vname}.regrid.{stats_type}.{out_tag}.nc")
    ds_regrid.to_netcdf(
        regrid_out,
        encoding={vname: {'_FillValue': fill_val, 'dtype': 'float32'}})
    print(f"  Saved regridded output: {regrid_out}")
    del ds_regrid

    del data, var_regrid, havg

ds.close()
print(f"\n{'='*60}")
print("Done.")

# %%
