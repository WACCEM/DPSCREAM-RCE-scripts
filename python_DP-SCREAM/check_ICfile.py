#!/usr/bin/env python
# %% [markdown]
# # Check Initial Condition Files
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
# Define file paths
file_paths = [
    "/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/RCE_300K_iopfile_4scam.nc",
    "/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/RCE09_dx3km_gpu_equilibrium_300K_profile.nc"
]

for fp in file_paths:
    if not os.path.exists(fp):
        raise FileNotFoundError(f"File not found: {fp}")

# Open the datasets
datasets = {}
for fp in file_paths:
    fname = os.path.basename(fp)
    datasets[fname] = xr.open_dataset(fp)

# Extract shared coordinates from the first dataset
first_ds = list(datasets.values())[0]
times = first_ds['time'].values
lat = first_ds['lat'].values[0]
lon = first_ds['lon'].values[0]
p = first_ds['lev'].values
top_to_bottom = p[0] < p[-1]

print(f"Coordinates: lat={lat}, lon={lon}, time={times}")
print(f"Loaded {len(datasets)} files.")

# %%
# ---------------------------------------------------------
# Determine Variable Types
# ---------------------------------------------------------
single_level_vars = []
multi_level_vars = []

# Exclude dimensions/coordinates and bounds
exclude_vars = list(first_ds.coords.keys()) + ['bdate', 'tsec', 'time_bnds']

for var_name, var in first_ds.variables.items():
    if var_name in exclude_vars:
        continue
    if 'lev' in var.dims:
        multi_level_vars.append(var_name)
    else:
        single_level_vars.append(var_name)

# %%
# ---------------------------------------------------------
# Print single-level variables
# ---------------------------------------------------------
print("\n--- Single-Level Variables ---")

for var_name in single_level_vars:
    units = first_ds[var_name].attrs.get('units', '')
    long_name = first_ds[var_name].attrs.get('long_name', var_name)
    print(f"\n{long_name} ({var_name}) [{units}]:")
    
    for fname, ds in datasets.items():
        if var_name in ds:
            vals = np.squeeze(ds[var_name].values)
            print(f"  {fname}: {vals}")
        else:
            print(f"  {fname}: Variable not found")

# %%
# ---------------------------------------------------------
# Calculate Physical Height (km) using Hydrostatic Equation
# ---------------------------------------------------------
g = 9.80665
R_d = 287.05
epsilon = 0.622

# Dictionary to store height for each file and time step
# z_km_dict[fname][t_idx]
z_km_dict = {fname: {} for fname in datasets.keys()}

for fname, ds in datasets.items():
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
                
        z_km_dict[fname][t_idx] = z / 1000.0  # Convert to km

print("\nPhysical heights calculated successfully for all files.")

# %%
# ---------------------------------------------------------
# Plot multi-level variables
# ---------------------------------------------------------
print("\n--- Plotting Multi-Level Variables ---")

# Define some markers and linestyles to distinguish files and time indices
markers = ['o', 's', '^', 'D', 'v', '<', '>']
#linestyles = ['-', '--', '-', '--']
colors = ['red','blue']

for var_name in multi_level_vars:
    units = first_ds[var_name].attrs.get('units', '')
    long_name = first_ds[var_name].attrs.get('long_name', var_name)
    
    fig, ax = plt.subplots(figsize=(8, 10))
    
    for f_idx, (fname, ds) in enumerate(datasets.items()):
        if var_name not in ds:
            continue
            
        var_data = ds[var_name].isel(lat=0, lon=0)
        marker = markers[f_idx]
        icolor = colors[f_idx]
        for t_idx in range(len(times)):
            if(t_idx == 0):
                ls = '-'
            else:
                ls = '--'

            #ls = linestyles[t_idx % len(linestyles)]

            x_vals = var_data.isel(time=t_idx).values
            y_vals = z_km_dict[fname][t_idx]
            
            
            
            label_name = f"{fname.replace('.nc', '')} (t={t_idx})"
            
            ax.plot(x_vals, y_vals, label=label_name, linestyle=ls, 
            linewidth=1.5, color=icolor) #marker=marker, markersize=3, 
            
    ax.set_ylabel("Height above sea level (km)")
    ax.set_xlabel(f"{long_name} [{units}]")
    ax.set_title(f"{var_name}: {long_name}")
    
    # Place legend outside or adjust font size if there are many files
    ax.legend(fontsize=8, loc='best')
    ax.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    plt.show()

# %%
# Close datasets
for ds in datasets.values():
    ds.close()
