# %% [markdown]
# # Concatenate DP-SCREAM Output Variable
# 
# This notebook extracts a specified variable from multiple DP-SCREAM history files for a given day and concatenates them into a single output file for that day.
# 
# **Variable:** `LW_flux_up_at_model_top`  
# **Source:** `scream_cpu_dpxx_RCE_dx1km` simulation run output (AVERAGE, 5-min interval)  
# **Period:** 2000-01-01-00000 to 2000-01-25-83100
# 

# %%
import os
import glob
import xarray as xr
import numpy as np
import ctypes, ctypes.util
import cftime

# Suppress benign HDF5 "file not found" diagnostics printed to stderr
_hdf5_lib = ctypes.util.find_library("hdf5")
if _hdf5_lib:
    _ = ctypes.CDLL(_hdf5_lib).H5Eset_auto2(0, None, None)

import warnings
warnings.filterwarnings("ignore")


# %%

def extract_timestamp(filepath):
    """Return the YYYY-MM-DD-sssss timestamp string from a filename."""
    basename = os.path.basename(filepath)
    # Remove prefix and suffix to isolate timestamp
    ts = basename[len(file_prefix):-len(file_suffix)]
    return ts


# %%
# --- CONFIGURATION ---
icase      = "RCE01_dx3km_gpu"
in_dir    = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/run"
#in_dir     = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/processed"
#out_dir    = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/processed"
#in_dir    = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/run"
out_dir    = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/cat_raw"

varname    = "VapWaterPath"

# File naming parameters
#stats_type = "AVERAGE"
stats_type = "INSTANT"

file_type="raw" # 'raw' for the direct model output, or 'proc' for post-processed files, 
   #this is used to construct the file name pattern for searching the input files to be concatenated
   #"cp" for cold-pool diagnostics with multiple variables in the same file: cp_depth, cp_base, cp_intensity, buoy_sfc; also has domain-wide variable "cp_area_frac"
   #use "proc" for the post-processed files with one variable per file, which is the current output of calc_imse_DPSCREAM.py

frequency = "nhours_x1" # e.g. "5min", "1hr", etc., this is used to construct the file name pattern for searching the input files to be concatenated

# Date-range timestamps (inclusive) matching filename format YYYY-MM-DD
ts_start = "2000-01-01"
ts_end   = "2000-02-16"


# %%
if(file_type == "raw"):
    file_prefix  = f"{icase}.hist.{stats_type}.{frequency}."
    file_suffix  = ".nc"
elif(file_type == "cp"):
    file_prefix  = f"{icase}.cp.{stats_type}.{frequency}."
    file_suffix  = ".nc"
else:
    file_prefix  = f"{icase}.{varname}.{stats_type}.{frequency}."
    file_suffix  = ".nc"

styear = int(ts_start[:4])
stmonth = int(ts_start[5:7])
stday = int(ts_start[8:10])

edyear = int(ts_end[:4])
edmonth = int(ts_end[5:7])
edday = int(ts_end[8:10])

print(f"Variable  : {varname}")
print(f"Run dir   : {in_dir}")
print(f"Output dir: {out_dir}")
print(f"Period    : {ts_start}  to  {ts_end}")

init_year = None
init_month = None
init_day = None
init_time = None


# %% [markdown]
# some data are saved with the file name date stamp of the previous and next days
# So better to include the day before stday (if file exist) and the day after the edday


# %%
#create day arrays with numpy datetime64
start_date = np.datetime64(f"{styear:04d}-{stmonth:02d}-{stday:02d}")
end_date = np.datetime64(f"{edyear:04d}-{edmonth:02d}-{edday:02d}")

date_range = np.arange(start_date, end_date + np.timedelta64(1, 'D'), dtype='datetime64[D]')

ndays = len(date_range)

# %%
for idct in range(ndays):
#idct = 0 #for debugging
    idate = date_range[idct]
    iyear = idate.astype('datetime64[Y]').astype(int) + 1970
    imonth = (idate.astype('datetime64[M]') - idate.astype('datetime64[Y]')).astype(int) + 1
    iday = (idate - idate.astype('datetime64[M]')).astype(int) + 1

    day_str = str(idate)  # Format: 'YYYY-MM-DD'
    print("============================================")
    print(f"Processing day {idct+1}/{ndays}: {day_str}")

    # Filter files for this day
    day_files = sorted(glob.glob(os.path.join(in_dir, file_prefix + day_str + "-*.nc")))
    #day_files = [f for f in selected_files if extract_timestamp(f).startswith(day_str)]

    print(f"  Found {len(day_files)} files for {day_str}, opening...")
    
    #get time-independent coordinate variables from the first file of the first day, assuming they are the same for all files; this is to avoid repeatedly reading the same coordinate variables from every file for every day, which can be time-consuming
    if(idct == 0):
        ds_first = xr.open_dataset(day_files[0]) if day_files else None
        if ds_first is not None:
            lat = ds_first['lat'].assign_attrs({'units': 'm'}) if 'lat' in ds_first else None
            lon = ds_first['lon'].assign_attrs({'units': 'm'}) if 'lon' in ds_first else None
            lev = ds_first['lev'] if 'lev' in ds_first else None
            ds_first.close()
            del ds_first

    # Open and concatenate files for this day
    ds_day = xr.open_mfdataset(day_files, combine='by_coords', parallel=False)[[varname]] if day_files else None

    # check simulation initial time from the dataset attributes, and compare with the start date of the current day file; this is to verify if the initial time is included in the current day file or not, which is important for deciding whether to add missing value for the initial time or concatenate the time samples from the previous or next day history files
    if(idct == 0):
        init_time= ds_day.attrs['case_t0'] if 'case_t0' in ds_day.attrs else 'unknown'
        if(init_time == 'unknown'):
            print("  WARNING: Initial time not found in dataset attributes, cannot verify against filename timestamps.")
        else:
            init_year = int(init_time[:4]) 
            init_month = int(init_time[5:7])
            init_day = int(init_time[8:10])
            print(f"  Initial time from dataset attributes: {init_time} (year {init_year}, month {init_month}, day {init_day})")

    time_today = ds_day['time'] #time arrat for all time samples in the current day file, some could be from the previous or next day due to the file naming issue

    #refine the time array to only include the time samples for the current day
    time_on_today = time_today.sel(time=(time_today.dt.year == iyear) & (time_today.dt.month == imonth) & (time_today.dt.day == iday))

    var_today = ds_day[varname].sel(time=time_on_today) #extract only the target time samples for the current day from the variable data array

    # Insert missing value for the initial time for average history files, or concatenate the time samples from the previous or next day history files; this is likely caused by a discontinuity in the first restart time in the test run "scream_cpu_dpxx_RCE_dx1km" case
    if(stats_type == "AVERAGE" and styear == init_year and stmonth == init_month and stday == init_day and iday == init_day):
        print(f"  Initial time {init_time} matches the start date {ts_start}. Add missing values for the output time corresponding to the initial time.")
        nan_slice = xr.full_like(var_today.isel(time=0), fill_value=np.nan).expand_dims(time=[cftime.DatetimeNoLeap(init_year, init_month, init_day, 0, 0, 0)])
        var_today_extended = xr.concat([nan_slice, var_today], dim='time')

        init_cftime = cftime.DatetimeNoLeap(init_year, init_month, init_day, 0, 0, 0)
        #time_today_extended = xr.DataArray(
        #    np.concatenate([[init_cftime], time_on_today.values]),dims=['time'])
        # NOTE on xr.concat usage:
        #   (1) dim must be a string (e.g. dim='time'), NOT a list (dim=['time']).
        #       Passing a list makes xarray treat it as coordinate *values* for a
        #       brand-new 'concat_dim' dimension, causing a "conflicting sizes"
        #       ValueError.
        #   (2) Every object passed to xr.concat must be a DataArray or Dataset.
        #       A bare cftime scalar raises TypeError.  Also, the DataArray wrapping
        #       the scalar must carry an explicit coords={'time': [...]} so that the
        #       'time' dimension is indexed; without it xarray tries to expand_dims
        #       on the already-indexed 'time' of time_on_today and raises
        #       "Dimension time already exists."
        time_today_extended = xr.concat(
            [xr.DataArray([init_cftime], dims=['time'], coords={'time': [init_cftime]}),
            time_on_today],
            dim='time')
        
        
    else:
        print(f"  Initial time {init_time} does not match the start date {ts_start}, no need to add missing value for the initial time.")
        var_today_extended = var_today
        time_today_extended = time_on_today

    # check any outputs for today in the previous day file -----------------------------------
    print(f"  Checking any outputs in the previous day's last file")
    previous_day = date_range[idct] - np.timedelta64(1, 'D')
    previous_day_str = str(previous_day)
    previous_day_files = sorted(glob.glob(os.path.join(in_dir, file_prefix + previous_day_str + "-*.nc")))
    previous_day_file = previous_day_files[-1] if previous_day_files else None
    var_prevday = None

    if(previous_day_file):
        ds_prev = xr.open_dataset(previous_day_file) if previous_day_file else None
        time_prevday = ds_prev['time'] 
        print(f"    Previous day file time range: {time_prevday[0]} to {time_prevday[-1]}")
        tprev_on_idate = time_prevday.sel(time=(time_prevday.dt.year == iyear) & (time_prevday.dt.month == imonth) & (time_prevday.dt.day == iday))
        if(tprev_on_idate.size > 0):
            print(f"  WARNING: Found {tprev_on_idate.size} time points in the previous day's file that match the current day {day_str}.")
            var_prevday = ds_prev[varname].sel(time=tprev_on_idate)
            ds_prev.close()
            del ds_prev
        else:
            print(f"  No time points in the previous day's file match the current day {day_str}, good.")
            ds_prev.close()
            del ds_prev
            
    else:
        print(f"  No previous day file found, skipping check.")

    # check next day file ---------------------------------------
    print(f"  Checking any outputs in the next day's first file")
    next_day = date_range[idct] + np.timedelta64(1, 'D')
    next_day_str = str(next_day)
    next_day_files = sorted(glob.glob(os.path.join(in_dir, file_prefix + next_day_str + "-*.nc")))
    next_day_file = next_day_files[0] if next_day_files else None
    next_day_file
    var_nextday = None

    if(next_day_file):
        # Open and concatenate files for this day
        ds_next = xr.open_dataset(next_day_file)
        time_nextday = ds_next['time']
        print(f"    Next day file time range: {time_nextday[0]} to {time_nextday[-1]}")
        tnext_on_idate = time_nextday.sel(time=(time_nextday.dt.year == iyear) & (time_nextday.dt.month == imonth) & (time_nextday.dt.day == iday))
        if(tnext_on_idate.size > 0):
            print(f"  WARNING: Found {tnext_on_idate.size} time points in the next day's file that match the current day {day_str}.")
            var_nextday = ds_next[varname].sel(time=tnext_on_idate)
            ds_next.close()
            del ds_next
        else:
            print(f"  No time points in the next day's file match the current day {day_str}, good.")
            ds_next.close()
            del ds_next
            
    else:
        print(f"  No next day file found, skipping check.")


    if(var_prevday is not None):
        print(f"  Concatenating {var_prevday.shape[0]} time points from the previous day's file that match the current day {day_str}.")
        var_today_extended = xr.concat([var_prevday, var_today_extended], dim='time')
        time_today_extended = xr.concat([tprev_on_idate, time_today_extended], dim='time')
        del var_prevday, tprev_on_idate
    if(var_nextday is not None):
        print(f"  Concatenating {var_nextday.shape[0]} time points from the next day's file that match the current day {day_str}.")
        var_today_extended = xr.concat([var_today_extended, var_nextday], dim='time')
        time_today_extended = xr.concat([time_today_extended, tnext_on_idate], dim='time')
        del var_nextday, tnext_on_idate

    # Sort and deduplicate the assembled time axis to guarantee strict
    # monotonicity.  Duplicate timestamps can arise when the same boundary
    # time step appears in both the prev/next-day run file and in the current
    # day's own run files.  np.unique returns sorted indices, so this also
    # handles any out-of-order entries.
    _, unique_idx = np.unique(time_today_extended.values, return_index=True)
    if len(unique_idx) < len(time_today_extended):
        print(f"  WARNING: Removed {len(time_today_extended) - len(unique_idx)} "
              f"duplicate/out-of-order time step(s) to ensure monotonicity.")
    time_today_extended = xr.DataArray(
        time_today_extended.values[unique_idx], dims=['time'])
    var_today_extended = xr.DataArray(
        var_today_extended.values[unique_idx],
        dims=var_today_extended.dims,
        coords={'time': time_today_extended},
        attrs=var_today_extended.attrs,
    )

    ds_vars = {varname: xr.DataArray(var_today_extended.values, dims=var_today_extended.dims, coords={'time': time_today_extended}, attrs=var_today_extended.attrs)}
    if lat is not None:
        ds_vars['lat'] = lat
    if lon is not None:
        ds_vars['lon'] = lon
    if lev is not None:
        ds_vars['lev'] = lev
    
    ds_today_extended = xr.Dataset(ds_vars)

    # Save concatenated dataset for this day
    out_path = os.path.join(out_dir, f"{icase}.{varname}.{stats_type}.{frequency}.{day_str}.nc")
    # Encode time as float64 (double) instead of xarray's default int64 so that
    # ncview and other tools that don't recognise NC_INT64 (type 10) can read it.
    # _FillValue=None suppresses the unwanted _FillValue attribute on the time coordinate.
    ds_today_extended.to_netcdf(out_path, encoding={'time': {'dtype': 'float64', '_FillValue': None}})
    print(f"  Saved concatenated data to {out_path}")

    #clean up memory
    ds_today_extended.close()
    del ds_today_extended

    ds_day.close()
    del ds_day

    del day_files, previous_day_files, next_day_files
    del var_today, time_today, time_on_today, var_today_extended, time_today_extended

print("Done.")

# %%
# --- VERIFY OUTPUT ---
if(False):
    ds_check = xr.open_dataset(out_path)
    print("Output file contents:")
    print(ds_check)
    print(f"\n'{varname}' shape : {ds_check[varname].shape}")
    print(f"time range        : {ds_check['time'].values[0]}  to  {ds_check['time'].values[-1]}")
    ds_check.close()




# %%
