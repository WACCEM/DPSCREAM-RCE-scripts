# %% [markdown]
# # Check History File for NaNs and Infs
# This script reads a specific history file and checks for invalid values.

# %%
# --- IMPORT LIBRARIES ---
import os
import xarray as xr
import numpy as np

# %%
# --- CONFIGURATION ---
indir = "/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/dx1km_L600km_RCE03_gpu/run"
infile = "dx1km_L600km_RCE03_gpu.hist.INSTANT.nhours_x1.2000-02-11-03600.nc"
var_list = ["U", "V", "omega", "T_mid","p_mid", "qc"]

filepath = os.path.join(indir, infile)

# %%
# --- LOAD DATASET ---
if not os.path.exists(filepath):
    print(f"Error: File not found: {filepath}")
else:
    print(f"Loading dataset: {filepath}")
    ds = xr.open_dataset(filepath)
    print("\nDataset loaded successfully:")
    print(ds)

# %%
# --- CHECK VARIABLES ---
for var in var_list:
    print(f"\n{'-'*50}")
    print(f"Variable: {var}")
    
    if var not in ds.variables:
        print(f"  WARNING: Variable '{var}' not found in the dataset.")
        continue
        
    # Extract underlying numpy array
    # Converting to float64 to ensure no overflow during statistics calculations
    data = ds[var].values.astype(np.float64)
    
    # Check for NaNs and Infs
    nan_count = np.isnan(data).sum()
    inf_count = np.isinf(data).sum()
    total_count = data.size
    
    print(f"  Total elements : {total_count}")
    print(f"  NaN count      : {nan_count} ({(nan_count/total_count)*100:.3f}%)")
    print(f"  Inf count      : {inf_count} ({(inf_count/total_count)*100:.3f}%)")
    
    # Calculate statistics ignoring NaNs and Infs
    valid_mask = ~(np.isnan(data) | np.isinf(data))
    valid_data = data[valid_mask]
    
    if valid_data.size > 0:
        print("  Statistics (excluding NaNs and Infs):")
        print(f"    Min    : {np.nanmin(valid_data):.4e}")
        print(f"    Max    : {np.nanmax(valid_data):.4e}")
        print(f"    Mean   : {np.nanmean(valid_data):.4e}")
        print(f"    Median : {np.nanmedian(valid_data):.4e}")
        print(f"    Std    : {np.nanstd(valid_data):.4e}")
    else:
        print("  Statistics: Cannot calculate, no valid data points (all NaN/Inf).")

# %%
# --- CLEANUP ---
ds.close()
print(f"\n{'-'*50}")
print("Done.")
