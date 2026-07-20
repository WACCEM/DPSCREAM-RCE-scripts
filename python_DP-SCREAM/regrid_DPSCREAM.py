#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regrid_DPSCREAM.py

Reads concatenated DP-SCREAM output produced by concat_DPSCREAM.py and
remaps each requested variable from the unstructured ncol grid to a regular
Cartesian lat/lon grid using a pre-computed ESMF weight file, following the
same approach as remap/regrid_dpxx_output.py.
In general, read input files concatenated to daily files by concat_DPSCREAM.py.

Output files are written to out_dir:
  {casename}.{varname}.regrid.{stats_type}.{out_tag}.nc
"""
# %%
import os
import re
import numpy as np
import xarray as xr
import netCDF4 as nc4
from scipy.sparse import csr_matrix
import glob

# %%
# ---------------------------------------------------------------------------
# User configuration
# ---------------------------------------------------------------------------
icase      = "RCE02_dx1km_gpu"
varname    = "diag_equiv_reflectivity_max" # "precip_total_surf_mass_flux" #"LW_flux_up_at_model_top"
#diag_equiv_reflectivity_max
# File naming parameters
stats_type = "INSTANT"
#stats_type = "AVERAGE"

file_type="proc" # 'raw' for the direct model output, or 'proc' for post-processed files, 
   #this is used to construct the file name pattern for searching the input files to be concatenated
   #"cp" for cold-pool diagnostics with multiple variables in the same file: cp_depth, cp_base, cp_intensity, buoy_sfc; also has domain-wide variable "cp_area_frac"
   #use "proc" for the post-processed files with one variable per file, which is the current output of calc_imse_DPSCREAM.py
frequency = "nhours_x1" # e.g. "5min", "1hr", etc., this is used to construct the file name pattern for searching the input files to be concatenated

#in_dir = (f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/processed")
#in_dir = (f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/freq_change")
in_dir = (f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/cat_raw")


# Output directory (created if it does not already exist)
out_dir = (f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/remapped")

# Date-range timestamps (inclusive, YYYY-MM-DD) to process.  Must match the timestamps in the input file names.
ts_start = "2000-01-01"
ts_end   = "2000-03-15"

# %%

# ESMF weight file produced by ESMF_RegridWeightGen.
# Maps from the unstructured DP-SCREAM source grid (ncol columns) to the
# desired regular Cartesian destination grid.
remap_method = "patch"
weightdir  = "/global/cfs/cdirs/wcm_shr/DP-SCREAM/remap/"
srcgrid = "DPSCREAM_RCE_dx1km_600x600km"
dstgrid = "PINACLES_YX_dx1km_600x600km"
weightfile = (f"{srcgrid}_to_{dstgrid}_{remap_method}.nc")

# Destination grid spacing in metres – used to compute Cartesian x/y
# cell-centre coordinates (dst_dx/2, 3*dst_dx/2, …) in the regridded output.
dst_dx = 1500.0 #1,500m for physics grid of the 1km simulation
if(dstgrid == "PINACLES_YX_dx1km_600x600km"):
    dst_dx = 1000.0 #1,000m for PINACLES 1km grid
elif(dstgrid == "PINACLES_YX_dx3km_600x600km"):
    dst_dx = 3000.0 #3,000m for PINACLES 3km grid

# ---------------------------------------------------------------------------
# End user configuration
# ---------------------------------------------------------------------------
# %%
styear  = int(ts_start[:4]);  stmonth = int(ts_start[5:7]);  stday = int(ts_start[8:10])
edyear  = int(ts_end[:4]);    edmonth = int(ts_end[5:7]);    edday = int(ts_end[8:10])

out_tag = f"{ts_start}_to_{ts_end}"

start_date = np.datetime64(f"{styear:04d}-{stmonth:02d}-{stday:02d}")
end_date   = np.datetime64(f"{edyear:04d}-{edmonth:02d}-{edday:02d}")
date_range = np.arange(start_date, end_date + np.timedelta64(1, 'D'),
                       dtype='datetime64[D]')

filevarname = varname

if(file_type == "raw"):
    file_prefix  = f"{icase}.hist.{stats_type}.{frequency}."
    file_suffix  = ".nc"
elif(file_type == "cp"):
    file_prefix  = f"{icase}.cp.{stats_type}.{frequency}."
    file_suffix  = ".nc"
else:
    file_prefix  = f"{icase}.{filevarname}.{stats_type}.{frequency}."
    file_suffix  = ".nc"

date_strs = {str(d) for d in date_range}
infiles = [f for f in sorted(glob.glob(os.path.join(in_dir, f"{file_prefix}*.nc")))
           if os.path.basename(f)[len(file_prefix):len(file_prefix)+10] in date_strs]

print(f"Period    : {ts_start}  to  {ts_end}")
print(f"\nFound {len(infiles)} input file(s):")
for fp in infiles:
    print(f"  {fp}")

weightfile_path = os.path.join(weightdir, weightfile)
if not os.path.isfile(weightfile_path):
    raise FileNotFoundError(
        f"ESMF weight file not found: {weightfile_path}")

os.makedirs(out_dir, exist_ok=True)
# %%
# ---------------------------------------------------------------------------
# Helper functions
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
    f        = nc4.Dataset(wfile)
    col      = f.variables['col'][:].astype(int) - 1   # 0-indexed source
    row      = f.variables['row'][:].astype(int) - 1   # 0-indexed destination
    S        = f.variables['S'][:]
    n_a      = len(f.dimensions['n_a'])
    n_b      = len(f.dimensions['n_b'])
    # dst_grid_dims is in Fortran order: [fast, slow] = [ny, nx] for YX grid
    dst_dims = f.variables['dst_grid_dims'][:]
    ny_out   = int(dst_dims[0])   # fast  dim = lat
    nx_out   = int(dst_dims[1])   # slow  dim = lon
    xc_b     = f.variables['xc_b'][:]
    yc_b     = f.variables['yc_b'][:]
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


# %%
# ---------------------------------------------------------------------------
# Load ESMF weights
# ---------------------------------------------------------------------------
print("Loading ESMF weight file ...")
W_esmf, x_esmf, y_esmf, nx_esmf, ny_esmf, n_a_esmf = \
    load_esmf_weights(weightfile_path)
print(f"  src cols : {n_a_esmf}")
print(f"  dst grid : {ny_esmf} (lat) x {nx_esmf} (lon)")

# Cartesian x/y cell-centre coordinates for the regridded output (computed once)
x_meters = np.arange(nx_esmf) * dst_dx + dst_dx / 2.0
y_meters = np.arange(ny_esmf) * dst_dx + dst_dx / 2.0

fill_val = np.float32(9.96921e+36)

# Prefix used to extract the date-stamp from each input filename
file_prefix = f"{icase}.{varname}.hist.{stats_type}."

# %%
# ---------------------------------------------------------------------------
# Loop over input files – one output file per input file
# ---------------------------------------------------------------------------
for infile in infiles:
    # Extract the YYYY-MM-DD date stamp from the filename using a regex.
    # This is robust to filenames with extra fields after the date
    # (e.g. a time-of-day offset like "2000-02-17-03600").
    _m = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(infile))
    if _m is None:
        print(f"  WARNING: cannot find a YYYY-MM-DD date in "
              f"'{os.path.basename(infile)}', skipping.")
        continue
    date_str = _m.group(1)

    print(f"\n{'='*60}")
    print(f"Processing file : {infile}  (date: {date_str})")

    ds = xr.open_dataset(infile, use_cftime=True)   # preserve noleap calendar

    # Validate ncol size against the weight file
    if 'ncol' not in ds.dims:
        raise ValueError(f"{infile} does not contain an 'ncol' dimension.")
    ncol_in = ds.dims['ncol']
    if ncol_in != n_a_esmf:
        raise ValueError(
            f"ncol in input ({ncol_in}) does not match weight file n_a "
            f"({n_a_esmf}).  Ensure the weight file was built for this grid.")

    if varname not in ds:
        print(f"  WARNING: '{varname}' not found in {infile}, skipping.")
        ds.close()
        continue

    # Determine whether the variable is 2-D (time, ncol) or 3-D (time, ncol, lev)
    dims = ds[varname].dims
    if 'ncol' in dims and len(dims) == 2:
        vdim = '2D'
    elif 'ncol' in dims and ('lev' in dims or 'ilev' in dims) and len(dims) == 3:
        vdim = '3D'
    else:
        print(f"  WARNING: '{varname}' has unexpected dims {dims}, skipping.")
        ds.close()
        continue

    print(f"  Variable : {varname}  ({vdim})")

    time_coord = ds['time']
    lev_vals   = ds['lev'].values if 'lev' in ds else None

    # Load data as float32; replace fill / huge values with NaN so they
    # propagate cleanly through the sparse dot product.
    data = ds[varname].values.astype(np.float32)
    data[data >= 1e30] = np.nan

    # Ensure 3-D data is (time, ncol, lev)
    if vdim == '3D':
        if ds[varname].dims.index('ncol') == 1:
            # (time, lev, ncol) -> (time, ncol, lev)
            data = data.transpose(0, 2, 1)

    print("  Applying ESMF weights for Cartesian regridding ...")
    var_regrid = apply_esmf_weights(data, W_esmf, ny_esmf, nx_esmf)

    # Replace NaN with the standard fill value for NetCDF compliance
    var_regrid = np.where(np.isnan(var_regrid), fill_val, var_regrid)

    regrid_attrs = dict(ds[varname].attrs)
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
        {varname: regrid_da, 'x': x_coord, 'y': y_coord},
        attrs={
            'source_file': infile,
            'weight_file': weightfile_path,
            'processing' : ('ESMF conservative regridding from unstructured'
                            ' ncol grid to regular Cartesian grid'),
        }
    )
    # ds_regrid['lat'].attrs = {
    #     'units': 'degrees_north', 'long_name': 'latitude'}
    # ds_regrid['lon'].attrs = {
    #     'units': 'degrees_east', 'long_name': 'longitude'}
    if lev_vals is not None and vdim == '3D':
        ds_regrid['lev'].attrs = {
            'units': 'mb', 'long_name': 'hybrid level at midpoints'}

    regrid_out = os.path.join(
        out_dir,
        f"{icase}.{varname}.{stats_type}.{frequency}.{dstgrid}.{date_str}.nc")
    ds_regrid.to_netcdf(
        regrid_out,
        encoding={
            varname: {'_FillValue': fill_val, 'dtype': 'float32'},
            'time'  : {'_FillValue': None, 'units': 'hours since 2000-01-01 00:00:00.000000'},
            'lat'   : {'_FillValue': None},
            'lon'   : {'_FillValue': None},
            'x'     : {'_FillValue': None},
            'y'     : {'_FillValue': None},
        })
    print(f"  Saved regridded output: {regrid_out}")

    ds.close()
    del ds_regrid, data, var_regrid

print(f"\n{'='*60}")
print("Done.")

# %%
