#!/usr/bin/env python
# %% [markdown]
# # Create RCEMIP O3 Profile File
# 
# To run this script on NERSC (Perlmutter):
# ```bash
# module load python
# conda activate dpscream_analysis
# python create_RCEMIP_O3.py
# ```

# %%
import os
import shutil
import numpy as np
import xarray as xr
import netCDF4 as nc
import matplotlib.pyplot as plt

# %%
# Configurations
orig_file = "/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/screami_ne30np4L128_20221004.nc"
new_file = "/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/O3_RCEMIP.nc"
plot_file = "/global/cfs/cdirs/wcm_code/ksa/python_WACCEM/O3_profile_comparison.png"

# RCEMIP Constants for O3
g1 = 3.6478   # ppmv hPa^(-g2)
g2 = 0.83209
g3 = 11.3515  # hPa

# %%
# 1. Make a copy of the original IC file
print(f"Copying {orig_file} to\n        {new_file}")
shutil.copy2(orig_file, new_file)

# %%
# 2. Open the climatology file to read necessary variables
print("Reading variables from the climatology file...")
ds = xr.open_dataset(orig_file)

# Read variables
ps = ds['ps']
hyam = ds['hyam']
hybm = ds['hybm']
P0 = ds['P0']
o3_clim = ds['o3_volume_mix_ratio']

# Calculate pressure at each vertical level (in Pa)
# p = hyam * P0 + hybm * ps
# xarray automatically handles the broadcasting across (time, ncol, lev)
p_pa = hyam * P0 + hybm * ps

# Convert pressure to hPa
p_hpa = p_pa / 100.0

# %%
# 3. Calculate the analytical O3 profile
print("Calculating RCEMIP analytical O3 profile...")
# O3(p) = g1 * p^g2 * exp(-p / g3)  [result in ppmv]
o3_analytical_ppmv = g1 * (p_hpa ** g2) * np.exp(-p_hpa / g3)

# Convert from ppmv to mol/mol to match the netCDF variable unit
o3_analytical_mol_mol = o3_analytical_ppmv * 1e-6

# %%
# 4. Plot the climatology and analytical O3 profiles together
print("Plotting the O3 profiles...")

# We take the mean over time and ncol to plot a single vertical profile
p_mean_hpa = p_hpa.mean(dim=['time', 'ncol'])
o3_clim_mean = o3_clim.mean(dim=['time', 'ncol'])
o3_analytical_mean = o3_analytical_mol_mol.mean(dim=['time', 'ncol'])

plt.figure(figsize=(8, 6))
plt.plot(o3_clim_mean, p_mean_hpa, label='Climatology', linewidth=2)
plt.plot(o3_analytical_mean, p_mean_hpa, label='RCEMIP Analytical', linestyle='--', linewidth=2)

plt.gca().invert_yaxis()
plt.yscale('log')
# Set y-axis to a logarithmic scale for pressure, matching typical atmospheric profile plots
plt.ylabel('Pressure (hPa)')
plt.xlabel('O3 Volume Mixing Ratio (mol/mol)')
plt.title('O3 Profile Comparison: Climatology vs RCEMIP')
plt.legend()
plt.grid(True, which='both', linestyle=':', alpha=0.6)

# Save the plot
plt.savefig(plot_file, dpi=300, bbox_inches='tight')
print(f"Plot saved to {plot_file}")

# %%
# 5. Overwrite o3_volume_mix_ratio in the copied O3_RCEMIP.nc file
print(f"Overwriting o3_volume_mix_ratio in {new_file}...")

with nc.Dataset(new_file, 'r+') as ds_nc:
    # Ensure dimensions match and write the data
    # Transpose back if necessary, but xarray `.values` from matching calculation
    # usually preserves the (time, ncol, lev) dimension order.
    # Let's ensure the dimension order matches the variable in the netCDF file.
    
    # Target variable shape in netCDF:
    o3_var = ds_nc.variables['o3_volume_mix_ratio']
    dims = o3_var.dimensions # e.g., ('time', 'ncol', 'lev')
    
    # Transpose the DataArray to match the exact dimension order
    o3_analytical_aligned = o3_analytical_mol_mol.transpose(*dims)
    
    # Overwrite the data
    o3_var[:] = o3_analytical_aligned.values

print("RCEMIP O3 IC file successfully created and updated!")

# Close the xarray dataset
ds.close()
