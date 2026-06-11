#load environment pinacles_share (/global/common/software/m1867/python/pinacles_share)

# %%

import matplotlib.pyplot as plt
import xarray as xr
import numpy as np
import pandas as pd
import os
import glob
import warnings

warnings.filterwarnings("ignore")

# %%

def read_group_variable(nc_path, group_name, var_name, engine=None):
    """Read a variable from a NetCDF group with xarray."""
    try:
        with xr.open_dataset(nc_path, group=group_name, engine=engine) as ds_group:
            if var_name not in ds_group:
                raise KeyError(
                    f"Variable '{var_name}' not found in group '{group_name}' of {nc_path}"
                )
            return ds_group[var_name].values
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read {group_name}/{var_name} from {nc_path}: {exc}"
        ) from exc


# %%

parent_cases = ['output_RCE_600x600_3km_scream_init'] #, 'output_RCE_500x500_3km_scream_init_100dz_nz330'
subcases = ['RCE_600x600_3km'] # 'RCE_500x500_3km'
ilegend = ['dz200'] #, 'dz100']

infile = 'stats.nc' #for vertical grid
# %%
indir_root = '/pscratch/sd/k/ksa/simulation/PINACLES/rce/test_runs'

# %%
Zgrid = {}
ZEdge = {}
for ic, parent_case in enumerate(parent_cases):
    subcase = subcases[ic]
    indir = os.path.join(indir_root, parent_case, subcase)
    infile_path = os.path.join(indir, infile)
    z = read_group_variable(infile_path, group_name='reference', var_name='z')
    zedge = read_group_variable(infile_path, group_name='reference', var_name='z_edge')
    dz = np.diff(z)
    print(f'{ilegend[ic]}: dz range: {dz.min()} - {dz.max()}')
    Zgrid[ic] = z
    ZEdge[ic] = zedge



# %%
# RCEMIP reference vertical grid (Table 3, Wing et al. 2018, GMD)
# https://doi.org/10.5194/gmd-11-793-2018
z_rcemip = np.array([
      37,   112,   194,   288,   395,   520,   667,   843,  1062,  1331,  # levels  1-10
    1664,  2055,  2505,  3000,  3500,  4000,  4500,  5000,  5500,  6000,  # levels 11-20
    6500,  7000,  7500,  8000,  8500,  9000,  9500, 10000, 10500, 11000,  # levels 21-30
   11500, 12000, 12500, 13000, 13500, 14000, 14500, 15000, 15500, 16000,  # levels 31-40
   16500, 17000, 17500, 18000, 18500, 19000, 19500, 20000, 20500, 21000,  # levels 41-50
   21500, 22000, 22500, 23000, 23500, 24000, 24500, 25000, 25500, 26000,  # levels 51-60
   26500, 27000, 27500, 28000, 28500, 29000, 29500, 30000, 30500, 31000,  # levels 61-70
   31500, 32000, 32500, 33000,                                             # levels 71-74
], dtype=float)  # height in metres, 74 levels

# %%
#planned 3D slice levels

# z_slice_levels = np.array([100, 300, 500, 650, 850, 1000, 1300, 1700, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 6000, 
#                            7000, 8000, 9000, 10000], dtype=float)

z_slice_levels = np.array([100,  500, 1000, 2000, 3000, 5000, 6000, 8000, 10000], dtype=float)

#find corresponding indices in the vertical grid for the planned slice levels
z = Zgrid[0]
indices = np.array([np.argmin(np.abs(z - level)) for level in z_slice_levels])

#check if the indices are correct
for idx, level in zip(indices, z_slice_levels):
    print(f"target={level:.0f} m -> z[{idx}]={z[idx]:.1f} m")

# %%

plt.figure(figsize=(7, 6))
#for ic, subcase in enumerate(subcases):
ic=0
z = Zgrid[ic]
idx = np.arange(z.size)
plt.plot(z, idx, '.', linewidth=2, label=ilegend[ic])

plt.plot(z_rcemip, np.arange(z_rcemip.size), 'ko-', linewidth=2, label='RCEMIP reference')
#plt.plot(z_slice_levels, indices, 'o', label='slice levels')
plt.plot(z[indices], indices, 'o', label='slice levels')


plt.xlabel('Height (m)')
plt.ylabel('Array index')
plt.title('Vertical Grid Profiles')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

# %%

# Vertical grid spacing (dz) profiles
plt.figure(figsize=(7, 6))
for ic, subcase in enumerate(subcases):
    z = Zgrid[ic]
    dz = np.diff(z)
    z_mid = 0.5 * (z[:-1] + z[1:])  # mid-level heights for dz
    plt.plot(dz, z_mid, linewidth=2, label=ilegend[ic])

dz_rcemip = np.diff(z_rcemip)
z_mid_rcemip = 0.5 * (z_rcemip[:-1] + z_rcemip[1:])
plt.plot(dz_rcemip, z_mid_rcemip, 'k-', linewidth=2, label='RCEMIP reference')

plt.xlabel('Grid spacing dz (m)')
plt.ylabel('Height (m)')
plt.title('Vertical Grid Spacing Profiles')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

# %%
