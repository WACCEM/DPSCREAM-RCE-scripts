#!/usr/bin/env python
# %% [markdown]
# # Create Equilibrium Initial Condition File
# 
# To run this script on NERSC (Perlmutter):
# ```bash
# module load python
# conda activate dpscream_analysis
# python create_equilibrium_IC.py
# ```

# %%
import os
import glob
import shutil
import numpy as np
import xarray as xr
import netCDF4 as nc

# %%
# Configurations
casename = "RCE09_dx3km_gpu"
orig_ic_file = "/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/RCE_300K_iopfile_4scam.nc"
new_ic_file = f"/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/{casename}_equilibrium_300K_profile.nc"
hist_dir = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{casename}/run"

# Number of days to average over (assuming 1 file per day based on filename structure)
ndays = 30

# Variable mapping: {IOP_var: Hist_var}
# These are the prognostic variables we want to update with equilibrium states.
# (Forcings like Ptend, divT, divq, phis are left unchanged)
var_mapping = {
    'T': 'T_mid',
    'q': 'qv',
    'Ps': 'ps'
}

# %%
# 1. Make a copy of the original IC file
print(f"Copying {orig_ic_file} to\n        {new_ic_file}")
shutil.copy2(orig_ic_file, new_ic_file)

# %%
# 2. Find and select the last 30 days of history files
file_pattern = os.path.join(hist_dir, f"{casename}.hist.INSTANT.nhours_x1.2000-*.nc")
all_files = sorted(glob.glob(file_pattern))

if len(all_files) == 0:
    raise FileNotFoundError(f"No history files found matching {file_pattern}")

# Select the last 'ndays' files
files_to_read = all_files[-ndays:]
print(f"\nFound {len(all_files)} total files.")
print(f"Reading the last {len(files_to_read)} files for equilibrium averaging.")
print(f"  First file in average: {os.path.basename(files_to_read[0])}")
print(f"  Last file in average:  {os.path.basename(files_to_read[-1])}")

# %%
# 3. Calculate time and horizontal mean
print("\nLoading history files and calculating means...")
# Open multiple datasets efficiently
ds_hist = xr.open_mfdataset(files_to_read, combine='by_coords')

# Calculate mean over time and all columns (ncol)
hist_vars = list(var_mapping.values())
ds_mean = ds_hist[hist_vars].mean(dim=['time', 'ncol']).compute()

print("Calculation complete. Overwriting IC file...")

# %%
# 4. Overwrite values in the copied IC file
with nc.Dataset(new_ic_file, 'r+') as ds_ic:
    for iop_var, hist_var in var_mapping.items():
        if hist_var not in ds_mean:
            print(f"  Warning: {hist_var} not found in history means. Skipping {iop_var}.")
            continue
            
        mean_val = ds_mean[hist_var].values
        
        # Get shape of the variable in the IOP file
        # The IOP file usually has dimensions (time, lev, lat, lon) or (time, lat, lon)
        # where time=2, lat=1, lon=1
        var_shape = ds_ic.variables[iop_var].shape
        
        # Determine if it's a 1D profile or a scalar
        if np.isscalar(mean_val) or mean_val.ndim == 0:
            new_data = np.full(var_shape, mean_val)
        else:
            # It's a 1D profile of size 'lev'
            dims = ds_ic.variables[iop_var].dimensions
            try:
                lev_idx = dims.index('lev')
            except ValueError:
                print(f"  Warning: 'lev' dimension not found in {iop_var}. Skipping.")
                continue
            
            # Reshape the 1D profile to be broadcastable to var_shape
            reshape_dims = [1] * len(var_shape)
            reshape_dims[lev_idx] = len(mean_val)
            mean_val_reshaped = mean_val.reshape(tuple(reshape_dims))
            
            # Broadcast the values to match the IOP file dimensions
            # This automatically duplicates the data across the 2 time steps
            new_data = np.broadcast_to(mean_val_reshaped, var_shape)
        
        # Overwrite the data in the netCDF dataset
        ds_ic.variables[iop_var][:] = new_data
        print(f"  --> Overwrote '{iop_var}' with mean of '{hist_var}'")

print("\nEquilibrium IC file successfully created and updated!")

# %%
# Close dataset
ds_hist.close()
