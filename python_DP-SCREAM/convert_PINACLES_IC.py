#!/usr/bin/env python
# %% [markdown]
# # Create DP-SCREAM IC from PINACLES Initial Condition File
# 
# To run this script on NERSC (Perlmutter):
# ```bash
# module load python
# conda activate dpscream_analysis
# python convert_PINACLES_IC.py
# ```

# %%
import os
import shutil
import numpy as np
import xarray as xr
import netCDF4 as nc

# %%
# Configurations
pinacles_ic_file = "/global/cfs/cdirs/wcm_code/PINACLES/share/data/profile_from_RCE03_150x150_1km.nc"
orig_ic_file = "/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/RCE_300K_iopfile_4scam.nc"
new_ic_file = "/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/PINACLES_RCE03_150x150_1km_profile_4scam.nc"

# %%
# 1. Make a copy of the original IC file
print(f"Copying {orig_ic_file} to\n        {new_ic_file}")
shutil.copy2(orig_ic_file, new_ic_file)

# %%
# 2. Read PINACLES IC data
print(f"\nReading PINACLES IC from {pinacles_ic_file}")
ds_pin = xr.open_dataset(pinacles_ic_file)
p_pin = ds_pin['p'].values
T_pin = ds_pin['T'].values
qv_pin = ds_pin['qv'].values
ds_pin.close()

# Ensure pressure is strictly increasing for np.interp
if p_pin[0] > p_pin[-1]:
    p_pin_asc = p_pin[::-1]
    T_pin_asc = T_pin[::-1]
    qv_pin_asc = qv_pin[::-1]
else:
    p_pin_asc = p_pin
    T_pin_asc = T_pin
    qv_pin_asc = qv_pin

# We assume surface pressure is the max pressure from PINACLES profile
Ps_pin = np.max(p_pin)
print(f"PINACLES surface pressure: {Ps_pin} Pa")

# %%
# 3. Overwrite values in the copied IC file
print("\nInterpolating and overwriting IC file...")
with nc.Dataset(new_ic_file, 'r+') as ds_ic:
    lev_dpscream = ds_ic.variables['lev'][:]
    
    # Interpolate T and q
    T_interp = np.interp(lev_dpscream, p_pin_asc, T_pin_asc)
    q_interp = np.interp(lev_dpscream, p_pin_asc, qv_pin_asc)
    
    var_data = {
        'T': T_interp,
        'q': q_interp,
        'Ps': Ps_pin
    }
    
    for iop_var, new_val in var_data.items():
        var_shape = ds_ic.variables[iop_var].shape
        
        # Determine if it's a 1D profile or a scalar
        if np.isscalar(new_val) or np.ndim(new_val) == 0:
            new_data = np.full(var_shape, new_val)
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
            reshape_dims[lev_idx] = len(new_val)
            new_val_reshaped = new_val.reshape(tuple(reshape_dims))
            
            # Broadcast the values to match the IOP file dimensions
            new_data = np.broadcast_to(new_val_reshaped, var_shape)
        
        # Overwrite the data in the netCDF dataset
        ds_ic.variables[iop_var][:] = new_data
        print(f"  --> Overwrote '{iop_var}'")

print("\nDP-SCREAM IC file from PINACLES successfully created and updated!")
