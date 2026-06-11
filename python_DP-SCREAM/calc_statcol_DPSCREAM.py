#!/usr/bin/env python
"""
Calculate vertical column statistics (integration, mean, max, or min) 
of a given variable from DP-SCREAM output.

Usage:
    module load python
    conda activate dpscream_analysis
    python calc_statcol_DPSCREAM.py --varname nc --stat_type int [--icase ICASE] ...
"""
# %%
import argparse
import os
import re
import numpy as np
import xarray as xr

# %%

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
G   = 9.80665      # Gravitational acceleration [m s^-2]
P0  = 100000.0     # Reference pressure [Pa]


# %%

parser = argparse.ArgumentParser(
    description="Calculate vertical column statistics of a given variable from DP-SCREAM output."
)
parser.add_argument("--varname", required=True,
                    help="Name of the variable to process (e.g., 'nc')")
parser.add_argument("--stat_type", required=True, choices=["int", "avg", "max", "min"],
                    help="Type of statistic to calculate: 'int' (mass-weighted sum), 'avg' (mass-weighted mean), 'max', or 'min'")
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
# parser.add_argument("--in_dir", type=str, default=None,
#                     help="Input directory (overrides default path)")
parser.add_argument("--ifreq",  type=str, default="nmins_x5",
                    help="Input frequency (overrides default path)")
args = parser.parse_args()

varname = args.varname
stat_type = args.stat_type
icase   = args.icase
infile  = args.infile
iyear   = args.iyear
imonth  = args.imonth
iday    = args.iday
isecond = args.isecond
#in_dir  = args.in_dir
ifreq   = args.ifreq


# %%
#for testing
# varname = "nc_m3"
# stat_type = "max"
# icase   ="RCE02_dx3km_gpu"
# in_dir  = "/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE02_dx3km_gpu/run"

# infile  = (in_dir + "/RCE02_dx3km_gpu.hist.INSTANT.nhours_x1.2000-03-10-03600.nc")
# ifreq   = "nhours_x1"

# %%
# if in_dir is None:
#     in_dir = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/run"

out_dir    = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/cat_raw"
#out_dir    = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/processed"

if infile is not None:
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

out_basename = f"{icase}.{varname}_{stat_type}.INSTANT.{ifreq}.{timestamp}.nc"

#input_file  = os.path.join(in_dir, in_basename)
output_file = os.path.join(out_dir, out_basename)

print(f"Reading: {infile}")
ds = xr.open_dataset(infile)

# %%
# in case for unit change or other diagnostics 
invarname = varname
if(varname == 'nc_m3'):
    #change units from #/kg to #/m^{-3}
    invarname = 'nc'
if(varname == 'ni_m3'):
    #change units from #/kg to #/m^{-3}
    invarname = 'ni'

if invarname not in ds:
    raise ValueError(f"Variable '{invarname}' not found in the dataset.")

var_data = ds[invarname].values
var_dims = ds[invarname].dims

if "lev" in var_dims:
    vert_dim = "lev"
    vert_axis = var_dims.index("lev")
elif "ilev" in var_dims:
    vert_dim = "ilev"
    vert_axis = var_dims.index("ilev")
else:
    raise ValueError(f"Variable '{invarname}' does not contain 'lev' or 'ilev' dimensions. Dims found: {var_dims}")

original_units = ds[invarname].attrs.get("units", "unknown")

# Get other necessary data
ps    = ds["ps"].values      # (time, ncol)        [Pa]
hyai  = ds["hyai"].values    # (ilev=129,)         dimensionless
hybi  = ds["hybi"].values    # (ilev=129,)         dimensionless
time  = ds["time"]
lat   = ds["lat"]
lon   = ds["lon"]
hyam  = ds["hyam"].values    # (ilev=129,)         dimensionless
hybm  = ds["hybm"].values    # (ilev=129,)         dimensionless

# %%
 # ps: (time, ncol) -> (time, ncol, 1) for broadcasting with ilev
p_mid = (hyam[np.newaxis, np.newaxis, :] * P0
        + hybm[np.newaxis, np.newaxis, :] * ps[:, :, np.newaxis])


# %%
#Units and other manipulations
if('_m3' in varname):
    rho = p_mid / (287.042 * ds.T_mid.values)  
    var_data = var_data*rho #convert from per mass (kg^{-1}) to per volume (m^{-3})
    del rho
    original_units = '1/m3'
# %%
# Ensure var_data can be broadcasted with dm if we are doing int or avg
if stat_type in ["int", "avg"]:
    # Compute layer pressure thickness dp(t, col, lev)
    p_int = (hyai[np.newaxis, np.newaxis, :] * P0
        + hybi[np.newaxis, np.newaxis, :] * ps[:, :, np.newaxis])
    dp = p_int[:, :, 1:] - p_int[:, :, :-1]   # (time, ncol, lev) [Pa]
    dm = dp / G # mass of each layer [kg m^-2]

    if vert_dim == "ilev":
        # Interpolate from interfaces to midpoints for mass weighting
        slices_start = [slice(None)] * var_data.ndim
        slices_start[vert_axis] = slice(None, -1)
        
        slices_end = [slice(None)] * var_data.ndim
        slices_end[vert_axis] = slice(1, None)
        
        var_mid = 0.5 * (var_data[tuple(slices_start)] + var_data[tuple(slices_end)])
    else:
        var_mid = var_data
        
    if stat_type == "int":
        stat_data = np.sum(var_mid * dm, axis=vert_axis)
        long_name_prefix = "Vertically integrated (mass-weighted)"
    elif stat_type == "avg":
        stat_data = np.sum(var_mid * dm, axis=vert_axis) / np.sum(dm, axis=vert_axis)
        long_name_prefix = "Vertical mean (mass-weighted)"
else:
    if stat_type == "max":
        stat_data = np.max(var_data, axis=vert_axis)
        long_name_prefix = "Vertical maximum"
    elif stat_type == "min":
        stat_data = np.min(var_data, axis=vert_axis)
        long_name_prefix = "Vertical minimum"

out_varname = f"{varname}_{stat_type}"

os.makedirs(out_dir, exist_ok=True)

if stat_type == "int":
    out_units = f"({original_units}) * kg m^-2"
else:
    out_units = original_units

# %%

ds_out = xr.Dataset(
    {
        out_varname: xr.DataArray(
            stat_data.astype(np.float32),
            dims=["time", "ncol"],
            attrs={
                "long_name": f"{long_name_prefix} of {varname}",
                "units": out_units,
                "original_variable": varname,
                "statistic_type": stat_type,
            },
        ),
        "lat": lat,
        "lon": lon,
    },
    coords={"time": time},
)
ds_out.attrs.update({
    "source_file": in_basename,
    "script": os.path.basename(__file__),
    "description": f"Calculated column {stat_type} for variable {varname}.",
})

print(f"Writing: {output_file}")
ds_out.to_netcdf(output_file, encoding={'time': {'_FillValue': None}})
print("Done.")

ds.close()

# %%
