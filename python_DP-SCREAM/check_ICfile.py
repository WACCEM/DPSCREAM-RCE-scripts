#!/usr/bin/env python
# %% [markdown]
# # Check Initial Condition File
# 
# To run this script on NERSC (e.g., Perlmutter), execute the following commands in your terminal:
# ```bash
# module load python
# conda activate dpscream_analysis
# python check_ICfile.py
# ```
# Alternatively, you can run this script section by section in an interactive Python window 
# (e.g., in VSCode, Spyder, or Jupyter) thanks to the `# %%` separators.

# %%
import os
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt

# %%
# Define file path
#file_path = "/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/RCE_300K_iopfile_4scam.nc"
file_path = "/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/RCE09_dx3km_gpu_equilibrium_300K_profile.nc"

if not os.path.exists(file_path):
    raise FileNotFoundError(f"File not found: {file_path}")

# Open the dataset
ds = xr.open_dataset(file_path)

# Extract single value coordinates
times = ds['time'].values
lat = ds['lat'].values[0]
lon = ds['lon'].values[0]

print(f"File: {file_path}")
print(f"Coordinates: lat={lat}, lon={lon}, time={times}")

# %%
# ---------------------------------------------------------
# Print single-level variables
# ---------------------------------------------------------
print("\n--- Single-Level Variables ---")
single_level_vars = []
multi_level_vars = []

# Exclude dimensions/coordinates and bounds
exclude_vars = list(ds.coords.keys()) + ['bdate', 'tsec', 'time_bnds']

for var_name, var in ds.variables.items():
    if var_name in exclude_vars:
        continue
    if 'lev' in var.dims:
        multi_level_vars.append(var_name)
    else:
        single_level_vars.append(var_name)

for var_name in single_level_vars:
    vals = ds[var_name].values
    units = ds[var_name].attrs.get('units', '')
    long_name = ds[var_name].attrs.get('long_name', var_name)
    # Using np.squeeze to remove single dimensions like (lat, lon)
    squeezed_vals = np.squeeze(vals)
    print(f"{long_name} ({var_name}): {squeezed_vals} {units}")

# %%
# ---------------------------------------------------------
# Calculate Physical Height (km) using Hydrostatic Equation
# ---------------------------------------------------------
# Variables needed: T, q, lev (pressure in Pa), Ps (surface pressure in Pa), phis (surface geopotential)
# We calculate height for each time step.
# z_surf = phis / g
# dz = R_d * Tv / g * d(ln p)
g = 9.80665
R_d = 287.05
epsilon = 0.622

# lev is mid-point pressure in Pa
p = ds['lev'].values

# Check if pressure levels are ordered top-to-bottom or bottom-to-top
top_to_bottom = p[0] < p[-1]

# We will calculate Z for each time step and store it in a dictionary
z_km_dict = {}

for t_idx in range(len(times)):
    T_prof = ds['T'].isel(time=t_idx, lat=0, lon=0).values
    
    # If moisture q exists, use it for virtual temperature, otherwise Tv = T
    if 'q' in ds.variables:
        q_prof = ds['q'].isel(time=t_idx, lat=0, lon=0).values
        Tv = T_prof * (1 + (1/epsilon - 1) * q_prof)
    else:
        Tv = T_prof
        
    Ps = ds['Ps'].isel(time=t_idx, lat=0, lon=0).values
    phis = ds['phis'].isel(time=t_idx, lat=0, lon=0).values
    
    z_surf = phis / g
    
    z = np.zeros_like(p)
    
    # Integrate hydrostatic equation
    if top_to_bottom:
        # Calculate lowest level height from surface pressure
        z[-1] = z_surf + R_d * Tv[-1] / g * np.log(Ps / p[-1])
        # Integrate upward (backwards in array)
        for i in range(len(p)-2, -1, -1):
            z[i] = z[i+1] + R_d * 0.5 * (Tv[i] + Tv[i+1]) / g * np.log(p[i+1] / p[i])
    else:
        # Calculate lowest level height from surface pressure
        z[0] = z_surf + R_d * Tv[0] / g * np.log(Ps / p[0])
        # Integrate upward (forwards in array)
        for i in range(1, len(p)):
            z[i] = z[i-1] + R_d * 0.5 * (Tv[i] + Tv[i-1]) / g * np.log(p[i-1] / p[i])
            
    z_km_dict[t_idx] = z / 1000.0  # Convert to km

print("\nPhysical heights calculated successfully.")

# %%
# ---------------------------------------------------------
# Plot multi-level variables
# ---------------------------------------------------------
print("\n--- Plotting Multi-Level Variables ---")

for var_name in multi_level_vars:
    var_data = ds[var_name].isel(lat=0, lon=0)
    units = ds[var_name].attrs.get('units', '')
    long_name = ds[var_name].attrs.get('long_name', var_name)
    
    fig, ax = plt.subplots(figsize=(6, 8))
    
    for t_idx in range(len(times)):
        x_vals = var_data.isel(time=t_idx).values
        y_vals = z_km_dict[t_idx]
        
        ax.plot(x_vals, y_vals, label=f"Time index {t_idx}", marker='.', markersize=4, linestyle='-')
        
    ax.set_ylabel("Height above sea level (km)")
    ax.set_xlabel(f"{long_name} [{units}]")
    ax.set_title(f"{var_name}: {long_name}")
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    plt.show()

# %%
# Close the dataset
ds.close()

# %%
