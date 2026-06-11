#!/usr/bin/env python
"""
Interpolate DP-SCREAM 3D output to a specified height above the surface (or sea level)
using the z_mid variable.

Usage:
    module load python
    conda activate dpscream_analysis
    python interpz_DPSCREAM.py [--icase ICASE] [--infile INFILE]
                               [--iyear IYEAR] [--imonth IMONTH]
                               [--iday IDAY] [--isecond ISECOND]
                               [--in_dir IN_DIR] [--ifreq IFREQ]
                               [--varname VARNAME] [--target_z TARGET_Z]
"""

# %%
import argparse
import os
import re
import numpy as np
import xarray as xr

# -------------------------------------------------------------------------
# %%

# Configuration
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="Interpolate 3D variable to a specified height using z_mid."
)
parser.add_argument("--icase",   default="scream_cpu_dpxx_RCE_dx1km",
                    help="Case name (default: scream_cpu_dpxx_RCE_dx1km)")
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
parser.add_argument("--in_dir", type=str, default=None,
                    help="Input directory (overrides default path)")
parser.add_argument("--ifreq",  type=str, default="nmins_x5",
                    help="Input frequency (overrides default path)")
parser.add_argument("--varname", type=str, default="nc",
                    help="Variable to interpolate (default: nc)")
parser.add_argument("--target_z", type=float, default=5000.0,
                    help="Target height for interpolation in meters (default: 5000.0)")
args = parser.parse_args()

icase    = args.icase
infile   = args.infile
iyear    = args.iyear
imonth   = args.imonth
iday     = args.iday
isecond  = args.isecond
in_dir   = args.in_dir
ifreq    = args.ifreq
varname  = args.varname
target_z = args.target_z

#for testing
# varname  = "nc_m3"
# icase    = "RCE02_dx3km_gpu"
# infile   = "RCE02_dx3km_gpu.hist.INSTANT.nhours_x1.2000-02-01-03600.nc"
# ifreq    = "nhours_x1"
# target_z = 2000.0
# in_dir  = None
# %%

if in_dir is None:
    in_dir = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/run"
out_dir    = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/cat_raw"
#out_dir    = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/processed"

if(infile is not None):
    in_basename  = infile
    #get time stamp from file name
    basename = os.path.basename(infile)
    match = re.search(r'\d{4}-\d{2}-\d{2}-\d{5}', basename)
    if not match:
        raise ValueError(f"Could not extract timestamp from filename: {basename}")
    timestamp = match.group()
else:
    timestamp = f"{iyear:04d}-{imonth:02d}-{iday:02d}-{isecond:05d}"
    in_basename  = f"{icase}.hist.INSTANT.{ifreq}.{timestamp}.nc"


input_file  = os.path.join(in_dir, in_basename)
if infile is not None and os.path.isabs(infile):
    input_file = infile
    

# %%

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print(f"Reading: {input_file}")
ds = xr.open_dataset(input_file)

invarname = varname
if varname == 'nc_m3':
    invarname = 'nc'
if varname == 'ni_m3':
    invarname = 'ni'

if invarname not in ds:
    raise ValueError(f"Variable '{invarname}' not found in {input_file}")

var_3d = ds[invarname].values  # (time, ncol, lev)
z_mid  = ds["z_mid"].values  # (time, ncol, lev)
time   = ds["time"]
lat    = ds["lat"]
lon    = ds["lon"]

if '_m3' in varname:
    P0  = 100000.0
    ps    = ds["ps"].values
    hyam  = ds["hyam"].values
    hybm  = ds["hybm"].values
    p_mid = (hyam[np.newaxis, np.newaxis, :] * P0
            + hybm[np.newaxis, np.newaxis, :] * ps[:, :, np.newaxis])
    rho = p_mid / (287.042 * ds["T_mid"].values)
    var_3d = var_3d * rho


# %%

# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------
print(f"Interpolating '{varname}' to {target_z} m...")
ntime, ncol, nlev = z_mid.shape
out_vals = np.zeros((ntime, ncol), dtype=np.float32)

for t in range(ntime):
    z_diff = z_mid[t] - target_z
    
    # Find the first level where z_mid falls below target_z
    idx_below = np.argmax(z_diff < 0, axis=1)
    
    # Handle columns where target_z is lower than all model levels
    never_below = np.all(z_diff >= 0, axis=1)
    idx_below[never_below] = nlev - 1
    
    # Ensure idx_below is at least 1 so idx_above is valid
    idx_below = np.clip(idx_below, 1, nlev - 1)
    idx_above = idx_below - 1
    
    n_idx = np.arange(ncol)
    
    z1 = z_mid[t, n_idx, idx_above]
    z2 = z_mid[t, n_idx, idx_below]
    v1 = var_3d[t, n_idx, idx_above]
    v2 = var_3d[t, n_idx, idx_below]
    
    denom = z2 - z1
    denom = np.where(denom == 0, 1e-10, denom) # avoid division by zero
    w = (target_z - z1) / denom
    
    out_vals[t, :] = v1 + (v2 - v1) * w


# %%

# ---------------------------------------------------------------------------
# Save output
# ---------------------------------------------------------------------------
os.makedirs(out_dir, exist_ok=True)
outvarname = f"{varname}_{int(target_z)}m"
out_basename = f"{icase}.{outvarname}.INSTANT.{ifreq}.{timestamp}.nc"


attrs_out = ds[invarname].attrs.copy()
if '_m3' in varname:
    attrs_out['units'] = '1/m3'

ds_out = xr.Dataset(
    {
        f"{outvarname}": xr.DataArray(
            out_vals,
            dims=["time", "ncol"],
            attrs=attrs_out,
        ),
        "lat": lat,
        "lon": lon,
    },
    coords={"time": time},
)

# Update attributes
ds_out[outvarname].attrs["long_name"] = f"{ds_out[outvarname].attrs.get('long_name', varname)} interpolated to {target_z} m"
ds_out[outvarname].attrs["height_m"] = target_z

ds_out.attrs.update({
    "source_file": in_basename,
    "script": os.path.basename(__file__),
    "description": (
        f"Variable '{varname}' interpolated to {target_z} m "
        "above sea level using z_mid from DP-SCREAM output."
    ),
})

output_file = os.path.join(out_dir, out_basename)

print(f"Writing: {output_file}")
ds_out.to_netcdf(output_file, encoding={'time': {'_FillValue': None}})
print("Done.")

ds.close()

# %%
