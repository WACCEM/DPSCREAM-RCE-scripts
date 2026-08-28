#!/usr/bin/env python
# ==============================================================================
# Script: concat_dailyfiles.py
# 
# Description:
# Concatenates daily NetCDF files with hourly samples into a single file
# over a specified date range for either DP-SCREAM or PINACLES RCE simulations.
#
# Usage Instructions:
# Before running this script on Perlmutter, ensure you load the python module
# and activate the correct conda environment:
# 
#   module load python
#   conda activate analysis_2026
#   python concat_dailyfiles.py
#
# ==============================================================================

import sys
import os
import glob
import numpy as np
import pandas as pd
import xarray as xr
from pathlib import Path

# Add parent directory to path so rce_tools can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rce_tools.rce_utils import days_since_jan1_to_month_day, month_day_to_days_since_jan1

# ==============================================================================
# 1. USER CONFIGURATION
# ==============================================================================

# Select model: 'DP-SCREAM' or 'PINACLES'
MODEL = 'DP-SCREAM'
case_name = "dx1km_L150km_RCE02_gpu"

#MODEL = 'PINACLES'
#case_name = "RCE03_150x150_1km"

# Date-range timestamps (inclusive, YYYY-MM-DD)
ts_start = "2000-01-01"
ts_end   = "2000-04-30"

# -- For PINACLES --
# Integer simulation days (0-based) will be calculated automatically 
# from ts_start and ts_end using a baseline year.
baseline_year = 2000

# ==============================================================================
# 2. MODEL-SPECIFIC SETTINGS
# ==============================================================================

if MODEL == 'DP-SCREAM':
    
    var_name  = "LW_flux_up_at_model_top"
    
    in_dir = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{case_name}/remapped/"
    out_dir = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{case_name}/org_ind/"
    
    # File pattern expects {date} to be replaced by YYYY-MM-DD
    file_pattern = f"{case_name}.{var_name}.INSTANT.nhours_x1.PINACLES_YX_dx1km_150x150km*{'{date}'}*nc"

elif MODEL == 'PINACLES':
    
    var_name  = "toa_lw_up"
    
    in_dir = f"/pscratch/sd/w/wcmca1/PINACLES/{case_name}/cat_raw/"
    out_dir = f"/pscratch/sd/w/wcmca1/PINACLES/{case_name}/org_ind/"
    
    # File pattern expects {date} to be replaced by 'dayXX'
    file_pattern = f"{case_name}.{var_name}*{'{date}'}*nc"

else:
    raise ValueError(f"Unknown MODEL: {MODEL}. Must be 'DP-SCREAM' or 'PINACLES'")

# ==============================================================================
# 3. PROCESSING
# ==============================================================================

def main():
    print("======================================================")
    print(f" Concatenating {MODEL} output")
    print("======================================================")
    
    # Ensure output directory exists
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    
    files_to_concat = []
    
    if MODEL == 'DP-SCREAM':
        print(f"Date range : {ts_start} to {ts_end}")
        start_date = pd.to_datetime(ts_start)
        end_date   = pd.to_datetime(ts_end)
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        for single_date in date_range:
            date_str = single_date.strftime("%Y-%m-%d")
            search_pattern = os.path.join(in_dir, file_pattern.format(date=date_str))
            matched_files = glob.glob(search_pattern)
            
            if len(matched_files) == 0:
                print(f"  [WARNING] No file found for date: {date_str}")
            else:
                files_to_concat.append(matched_files[0])
                
        out_filename = f"{case_name}_{var_name}_{ts_start}_to_{ts_end}.nc"
                
    elif MODEL == 'PINACLES':
        print(f"Date range : {ts_start} to {ts_end}")
        
        start_date_obj = pd.to_datetime(ts_start)
        end_date_obj   = pd.to_datetime(ts_end)
        
        pinacles_day_start = month_day_to_days_since_jan1(start_date_obj.month, start_date_obj.day, baseline_year)
        pinacles_day_end   = month_day_to_days_since_jan1(end_date_obj.month, end_date_obj.day, baseline_year)
        
        print(f"Day range  : day {pinacles_day_start} to day {pinacles_day_end}")
        
        for day in range(pinacles_day_start, pinacles_day_end + 1):
            date_str = f"day{day:02d}"
            search_pattern = os.path.join(in_dir, file_pattern.format(date=date_str))
            matched_files = glob.glob(search_pattern)
            
            if len(matched_files) == 0:
                print(f"  [WARNING] No file found for {date_str}")
            else:
                files_to_concat.append(matched_files[0])
                
        out_filename = f"{case_name}_{var_name}_{ts_start}_to_{ts_end}.nc"

    if len(files_to_concat) == 0:
        print("\n[ERROR] No files found to concatenate. Exiting.")
        return

    print(f"\nFound {len(files_to_concat)} files. Proceeding with concatenation...")
    
    # Open all files as a single dataset using xarray
    ds = xr.open_mfdataset(
        files_to_concat, 
        combine='nested', 
        concat_dim='time',
        data_vars='minimal',
        coords='minimal',
        compat='override'
    )
    
    ds_out = ds[[var_name]]
    out_filepath = os.path.join(out_dir, out_filename)
    
    print(f"\nSaving concatenated dataset to:\n  {out_filepath}")
    
    ds_out.to_netcdf(out_filepath)
    print("✓ Success! File saved.")
    
if __name__ == "__main__":
    main()
