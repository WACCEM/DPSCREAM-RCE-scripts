#!/usr/bin/env python
# %% [markdown]
# # Create DP-SCREAM IC using RCEMIP Analytical Profiles
# 
# To run this script on NERSC (Perlmutter):
# ```bash
# module load python
# conda activate dpscream_analysis
# python create_RCEMIP_IC.py
# ```

# %%
import os
import shutil
import numpy as np
import xarray as xr
import netCDF4 as nc

# %%
# Configurations
orig_ic_file = "/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/RCE_300K_iopfile_4scam.nc"
new_ic_file = "/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/RCEMIP_analytical_profile_4scam.nc"

# %%
# 1. Make a copy of the original IC file
print(f"Copying {orig_ic_file} to\n        {new_ic_file}")
shutil.copy2(orig_ic_file, new_ic_file)

# %%
# 2. Calculate Analytical Profiles (RCEMIP Protocol)
print("\nCalculating RCEMIP analytical profiles...")
T0 = 300.0       
p0 = 1014.8 * 100.0
qv0 = 18.65/1000.0
qt = 1e-11 / 1000.0
Tv0 = T0 * (1.0 +  0.608 * qv0)

Z = np.linspace(0.0, 35000, 5000) # Use a fine vertical resolution for accuracy
gamma_z = 0.0067
zt = 15000.0 
Tvt = Tv0 - gamma_z * zt 

zq1 = 4000.0
zq2 = 7500.0

qz = qv0 * np.exp(-Z/zq1)*np.exp(-(Z/zq2)**2.0)
qz[Z > zt] = qt

Tvz = Tv0 - gamma_z * Z
Tvz[Z > zt] = Tvt

T_ana = Tvz/(1.0 + 0.608 * qz)

RD = 287.0
G = 9.8

pz = p0 * ((Tv0 - gamma_z * Z)/Tv0)**(G/(RD * gamma_z))
pt = p0 * (Tvt/Tv0)**(G/(RD * gamma_z))

pz[Z > zt] = pt * np.exp((-(G * (Z[Z > zt] - zt)/(RD * Tvt))))

# Ensure pressure is strictly increasing for np.interp
if pz[0] > pz[-1]:
    pz_asc = pz[::-1]
    T_asc = T_ana[::-1]
    q_asc = qz[::-1]
else:
    pz_asc = pz
    T_asc = T_ana
    q_asc = qz

Ps_ana = p0
print(f"RCEMIP surface pressure: {Ps_ana} Pa")

# %%
# 3. Overwrite values in the copied IC file
print("\nInterpolating and overwriting IC file...")
with nc.Dataset(new_ic_file, 'r+') as ds_ic:
    lev_dpscream = ds_ic.variables['lev'][:]
    
    # Interpolate T and q
    T_interp = np.interp(lev_dpscream, pz_asc, T_asc)
    q_interp = np.interp(lev_dpscream, pz_asc, q_asc)
    
    var_data = {
        'T': T_interp,
        'q': q_interp,
        'Ps': Ps_ana
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

print("\nRCEMIP analytical IC file successfully created and updated!")
