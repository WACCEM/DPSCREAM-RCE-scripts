#!/usr/bin/env python
"""
Calculate vertically integrated moist static energy (IMSE) from DP-SCREAM output.

MSE per unit mass (following PINACLES CaseRCE.py):
    h = CPD * T + LV * qv + G * z

Vertically integrated using the hydrostatic approximation (rho * dz = dp / g),
which is the DP-SCREAM equivalent of the PINACLES sum(mse * rho0 * dz):
    IMSE(t, col) = sum_k[ h(t, col, k) * dp(t, col, k) / G ]

Layer pressure thickness dp is derived from hybrid coordinate interface pressures:
    p_int(t, col, k) = hyai(k) * P0 + hybi(k) * ps(t, col)
    dp(t, col, k)    = p_int(t, col, k+1) - p_int(t, col, k)

Physical constants match PINACLES parameters.py:
    CPD = 1004.0    J kg^-1 K^-1
    LV  = 2.5014e6  J kg^-1
    G   = 9.80665   m s^-2

Usage:
    module load python
    conda activate dpscream_analysis
    python calc_imse_DPSCREAM.py [--icase ICASE] [--infile INFILE]
                                 [--iyear IYEAR] [--imonth IMONTH]
                                 [--iday IDAY] [--isecond ISECOND]
                                 [--in_dir IN_DIR]
"""
# %%

import argparse
import os
import re
import numpy as np
import xarray as xr


# ---------------------------------------------------------------------------
# Physical constants — matching PINACLES pinacles/parameters.py
# ---------------------------------------------------------------------------
CPD = 1004.0       # Specific heat of dry air at constant pressure [J kg^-1 K^-1]
LV  = 2.5014e6     # Latent heat of vaporization [J kg^-1]
G   = 9.80665      # Gravitational acceleration [m s^-2]
P0  = 100000.0     # Reference pressure [Pa]

# %%
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="Calculate vertically integrated moist static energy (IMSE) from DP-SCREAM output."
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
args = parser.parse_args()

icase   = args.icase
infile  = args.infile
iyear   = args.iyear
imonth  = args.imonth
iday    = args.iday
isecond = args.isecond
in_dir  = args.in_dir  #cannot use the input argument $icase to set the default value above, so we set it here after parsing arguments
ifreq   = args.ifreq

if in_dir is None:
    in_dir = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/run"
out_dir    = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/cat_raw"
#out_dir    = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/processed"

# %%

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

#timestamp  = "2000-01-01-00000"
out_basename = f"{icase}.imse.INSTANT.{ifreq}.{timestamp}.nc"

input_file  = os.path.join(in_dir, in_basename)
output_file = os.path.join(out_dir, out_basename)

# %%

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print(f"Reading: {input_file}")
ds = xr.open_dataset(input_file)

T_mid = ds["T_mid"].values   # (time, ncol, lev)  [K]
qv    = ds["qv"].values      # (time, ncol, lev)  [kg kg^-1]
z_mid = ds["z_mid"].values   # (time, ncol, lev)  [m]
ps    = ds["ps"].values      # (time, ncol)        [Pa]
hyai  = ds["hyai"].values    # (ilev=129,)         dimensionless
hybi  = ds["hybi"].values    # (ilev=129,)         dimensionless
time  = ds["time"]
lat   = ds["lat"]
lon   = ds["lon"]
lev   = ds["lev"]

# %%

# ---------------------------------------------------------------------------
# Compute layer pressure thickness dp(t, col, lev)
# p_int = hyai * P0 + hybi * ps
# Levels run top-to-bottom, so dp > 0
# ---------------------------------------------------------------------------
# ps: (time, ncol) -> (time, ncol, 1) for broadcasting with ilev
p_int = (hyai[np.newaxis, np.newaxis, :] * P0
         + hybi[np.newaxis, np.newaxis, :] * ps[:, :, np.newaxis])
# p_int: (time, ncol, ilev=129)

dp = p_int[:, :, 1:] - p_int[:, :, :-1]   # (time, ncol, lev=128) [Pa]

# %%

# ---------------------------------------------------------------------------
# MSE per unit mass [J kg^-1]
# h = CPD * T + LV * qv + G * z
# ---------------------------------------------------------------------------
mse = CPD * T_mid + LV * qv + G * z_mid

# ---------------------------------------------------------------------------
# Vertical integration: IMSE = sum(h * dp / g)  [J m^-2]
# This is equivalent to PINACLES: sum(mse * rho0 * dz)
# via the hydrostatic relation rho * dz = dp / g
# ---------------------------------------------------------------------------
imse = np.sum(mse * dp / G, axis=2)   # (time, ncol)

# %%

# ---------------------------------------------------------------------------
# Save output
# ---------------------------------------------------------------------------
os.makedirs(out_dir, exist_ok=True)

ds_out = xr.Dataset(
    {
        "imse": xr.DataArray(
            imse.astype(np.float32),
            dims=["time", "ncol"],
            attrs={
                "long_name": "Integrated Moist Static Energy",
                "standard_name": "integrated_mse",
                "units": "J m^-2",
                "formula": "sum_k[(CPD*T_mid + LV*qv + G*z_mid) * dp_k / G]",
                "CPD_value": f"{CPD} J kg^-1 K^-1",
                "LV_value":  f"{LV} J kg^-1",
                "G_value":   f"{G} m s^-2",
            },
        ),
        "lat": lat,
        "lon": lon,
    },
    coords={"time": time, "lev": lev},
)
ds_out.attrs.update({
    "source_file": in_basename,
    "script": os.path.basename(__file__),
    "description": (
        "Vertically integrated moist static energy from DP-SCREAM output. "
        "Calculated following PINACLES CaseRCE.py, using hydrostatic "
        "approximation (rho*dz = dp/g) for vertical integration."
    ),
})

print(f"Writing: {output_file}")
ds_out.to_netcdf(output_file, encoding={'time': {'_FillValue': None, 'units': 'hours since 2000-01-01 00:00:00.000000'}})
print("Done.")

ds.close()

# %%
