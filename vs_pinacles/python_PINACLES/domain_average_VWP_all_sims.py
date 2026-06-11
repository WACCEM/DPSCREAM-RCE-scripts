# %% [markdown]
# # Domain-Average Water Vapor Path: PINACLES vs DP-SCREAM
# 
# This notebook compares domain-average water vapor path (VWP) time series between PINACLES and DP-SCREAM RCE simulations.
# 
# **Analysis:**
# - Loads VWP from MicroBase/timeseries group for PINACLES
# - Loads column_water_vapor from DP-SCREAM processed outputs
# - Plots time series comparison across multiple experiments
# 
# **Data Sources:**
# - **PINACLES:** Domain-mean VWP from `/pscratch/sd/p/paccini/test_runs/` and `/pscratch/sd/k/ksa/simulation/PINACLES/`
# - **DP-SCREAM:** Processed column water vapor from `/pscratch/sd/p/paccini/temp/output_dp_scream/processed_*`

# %% [markdown]
# ## Configuration
# 
# Configure which experiments to load and analyze.

# %%
# ============================================================================
# EXPERIMENT CONFIGURATION
# ============================================================================

# PINACLES experiments (VWP from MicroBase/timeseries group)
PINACLES_EXPERIMENTS = {
    '600x600_iSCREAM': {
        'path': '/pscratch/sd/p/paccini/test_runs/output_RCE_600x600_3km_scream_init/',
        'pattern': 'RCE_600x600_3km*',
        'label': 'PINACLES 600x600 dx3km iSCREAM',
        'color': 'g',
        'linestyle': '-'
    },
    '500x500_iSCREAM': {
        'path': '/pscratch/sd/p/paccini/test_runs/output_RCE_500x500_3km_scream_init_100dz_nz330/',
        'pattern': 'RCE_500x500_3km*',
        'label': 'PINACLES 500x500 dx3km dz100m iSCREAM',
        'color': 'teal',
        'linestyle': '-'
    },
    '500x500_3km200z_iSCREAM': {
        'path': '/pscratch/sd/k/ksa/simulation/PINACLES/rce/test_grid/RCE_500x500_dx3km_dz200m_root/',
        'pattern': 'RCE_500x500_dx3km*',
        'label': 'PINACLES 500x500 dx3km iSCREAM',
        'color': 'b',
        'linestyle': '-'
    },
    '500x500_1km200z_iSCREAM': {
        'path': '/pscratch/sd/k/ksa/simulation/PINACLES/rce/test_grid/RCE_500x500_dx1km_dz200m_root/',
        'pattern': 'RCE_500x500_dx1km*',
        'label': 'PINACLES 500x500 dx1km iSCREAM',
        'color': 'cyan',
        'linestyle': '-'
    },
    '600x600_1km200z_iSCREAM': {
        'path': '/pscratch/sd/k/ksa/simulation/PINACLES/rce/test_runs2/RCE_600x600_1km/',
        'pattern': 'RCE_600x600_1km_started*',
        'label': 'PINACLES 600x600 dx1km iSCREAM',
        'color': 'lime',
        'linestyle': '-'
    },
     '150x150_1km100z_iSCREAM': {
        'path': '/pscratch/sd/k/ksa/simulation/PINACLES/rce/test_runs2/RCE_150x150_1km/',
        'pattern': 'RCE_150x150_1km_started*',
        'label': 'PINACLES 150x150 dx1km iSCREAM',
        'color': 'black',
        'linestyle': '-'
    },
}

# DP-SCREAM experiments (processed column water vapor)
DPSCREAM_EXPERIMENTS = {
    '500x500': {
        'path': '/pscratch/sd/p/paccini/temp/output_dp_scream/processed_500x500/',
        'file': 'column_water_vapor',  # Will look for part1, part2, etc.
        'multipart': True,
        'n_parts': 4,
        'label': 'SCREAM 500x500 dx3km',
        'color': 'brown',
        'linestyle': '-'
    },
    '600x600': {
        'path': '/pscratch/sd/p/paccini/temp/output_dp_scream/processed_600x600/',
        'file': 'column_water_vapor.nc',
        'multipart': False,
        'label': 'SCREAM 600x600 dx3km',
        'color': 'orange',
        'linestyle': '-'
    }
}

# New set of 1 km DP-SCREAM experiments (processed column water vapor)
DPSCREAM_NEW_EXPERIMENTS = {
    '600x600_1km_init': {
        'path': '/pscratch/sd/w/wcmca1/DP-SCREAM/scream_cpu_dpxx_RCE_dx1km/havg/',
        'file': 'scream_cpu_dpxx_RCE_dx1km.VapWaterPath.havg.INSTANT.2000-01-01_to_2000-02-16.nc',  # Will look for part1, part2, etc.
        'multipart': False,
        'label': 'SCREAM 600x600 dx1km init',
        'color': 'purple',
        'linestyle': '-'
    },
    '600x600_1km_brnch': {
        'path': '/pscratch/sd/w/wcmca1/DP-SCREAM/RCE01_dx1km_gpu_branch/havg/',
        'file': 'RCE01_dx1km_gpu_branch.VapWaterPath.havg.INSTANT.2000-02-17_to_2000-04-30.nc',  # Will look for part1, part2, etc.
        'multipart': False,
        'label': 'SCREAM 600x600 dx1km branch',
        'color': 'purple',
        'linestyle': '--'
    },
     '600x600_3km_v3.0.2': {
        'path': '/pscratch/sd/w/wcmca1/DP-SCREAM/RCE01_dx3km_gpu/havg/',
        'file': 'RCE01_dx3km_gpu.VapWaterPath.havg.INSTANT.2000-01-01_to_2000-05-31.nc',  # Will look for part1, part2, etc.
        'multipart': False,
        'label': 'SCREAM 600x600 dx3km v3.0.2',
        'color': 'navy',
        'linestyle': '-'
     },
      '600x600_3km_v3.1.0': {
        'path': '/pscratch/sd/w/wcmca1/DP-SCREAM/RCE02_dx3km_gpu/havg/',
        'file': 'RCE02_dx3km_gpu.VapWaterPath.havg.INSTANT.2000-01-01_to_2000-05-15.nc',  # Will look for part1, part2, etc.
        'multipart': False,
        'label': 'SCREAM 600x600 dx3km v3.1.0',
        'color': 'purple',
        'linestyle': '--'
     }

}

# Plotting configuration
PLOT_TIME_RANGE = ('2000-01-01', '2000-04-10')
SAVE_FIGURE = True
FIGURE_NAME = 'domain_average_VWP_comparison.png'

# %% [markdown]
# ## Imports and Utilities

# %%
import matplotlib.pyplot as plt
import xarray as xr
import numpy as np
import pandas as pd
import os
import glob
import warnings
import matplotlib.dates as mdates

warnings.filterwarnings("ignore")

# %%
def update_time(ds1):
    # Reference start date
    start_date = pd.Timestamp('2000-01-01 00:00:00')
    # Convert time in seconds to pandas Timedelta
    timedeltas = pd.to_timedelta(ds1.time.values, unit='s')
    # Convert time in seconds to datetime format
    pd_time = pd.Series(start_date + timedeltas) 
    ds1 = ds1.assign_coords(time=pd_time.values)
    ds1 = ds1.sortby('time')

    return(ds1)

# %%
def load_pinacles_vwp(parent_dir, pattern):
    """
    Load PINACLES VWP data from multiple stats.nc files.
    
    Parameters:
    -----------
    parent_dir : str
        Parent directory containing simulation outputs
    pattern : str
        Glob pattern to match stats.nc files
        
    Returns:
    --------
    model_vwp : xr.Dataset
        VWP dataset with duplicates removed
    """
    # Create glob pattern
    full_pattern = os.path.join(parent_dir, pattern, 'stats.nc')
    file_list = sorted(glob.glob(full_pattern))
    
    if not file_list:
        raise FileNotFoundError(f"No files found matching {full_pattern}")
    
    # Initialize list for datasets
    datasets = []
    
    for file_path in file_list:
        # Open dataset from MicroBase/timeseries group
        print(file_path)
        ds = xr.open_dataset(file_path, group='MicroBase/timeseries')
        
        # Update time coordinates
        ds = update_time(ds)
        
        datasets.append(ds)
    
    # Concatenate and remove duplicates
    combined = xr.concat(datasets, dim='time')
    
    # Remove duplicate times and sort
    model_vwp = combined.sel(time=~combined.indexes['time'].duplicated()).sortby('time')
    
    return model_vwp

# %%
def load_dpscream_vwp(base_dir, file_name, multipart=True, n_parts=4):
    """
    Load DP-SCREAM column water vapor data.
    
    Parameters:
    -----------
    base_dir : str
        Directory containing processed DP-SCREAM files
    file_name : str
        Base file name (e.g., 'column_water_vapor' or 'column_water_vapor.nc')
    multipart : bool
        Whether files are split into multiple parts
    n_parts : int
        Number of parts if multipart=True
        
    Returns:
    --------
    ds : xr.Dataset
        Combined and sorted dataset with duplicates removed
    """
    if multipart:
        datasets = []
        for i in range(1, n_parts + 1):
            file_path = os.path.join(base_dir, f"{file_name}_part{i}.nc")
            
            if not os.path.exists(file_path):
                print(f"Warning: Could not find {file_path}")
                continue
                
            ds = xr.open_dataset(file_path)
            datasets.append(ds)
        
        if not datasets:
            raise FileNotFoundError(f"No files found for {file_name} in {base_dir}")
            
        combined = xr.concat(datasets, 'time')
    else:
        file_path = os.path.join(base_dir, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        combined = xr.open_dataset(file_path)
    
    # Remove duplicate times and sort
    ds = combined.sel(time=~combined.indexes['time'].duplicated()).sortby('time')
    
    return ds


# %%
def load_dpscream_vwp_new(base_dir, file_name, multipart=False, n_parts=4):
    """
    Load DP-SCREAM column water vapor data.
    
    Parameters:
    -----------
    base_dir : str
        Directory containing processed DP-SCREAM files
    file_name : str
        Base file name (e.g., 'column_water_vapor' or 'column_water_vapor.nc')
    multipart : bool
        Whether files are split into multiple parts
    n_parts : int
        Number of parts if multipart=True
        
    Returns:
    --------
    ds : xr.Dataset
        Combined and sorted dataset with duplicates removed
    """
    if multipart:
        datasets = []
        for i in range(1, n_parts + 1):
            file_path = os.path.join(base_dir, f"{file_name}_part{i}.nc")
            
            if not os.path.exists(file_path):
                print(f"Warning: Could not find {file_path}")
                continue
                
            ds = xr.open_dataset(file_path)
            datasets.append(ds)
        
        if not datasets:
            raise FileNotFoundError(f"No files found for {file_name} in {base_dir}")
            
        combined = xr.concat(datasets, 'time')
    else:
        file_path = os.path.join(base_dir, file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        combined = xr.open_dataset(file_path)
    
    # Remove duplicate times and sort
    ds = combined.sel(time=~combined.indexes['time'].duplicated()).sortby('time')
    
    return ds
# %% [markdown]
# Load all configured PINACLES experiments
pinacles_vwp = {}

for exp_name, exp_config in PINACLES_EXPERIMENTS.items():
    print(f"Loading PINACLES VWP: {exp_name}")
    try:
        vwp = load_pinacles_vwp(exp_config['path'], exp_config['pattern'])
        pinacles_vwp[exp_name] = {'data': vwp, 'config': exp_config}
        print(f"  ✓ Loaded {len(vwp.time)} time steps")
    except Exception as e:
        print(f"  ✗ Error loading {exp_name}: {e}")

# %%
# Load all configured DP-SCREAM experiments
dpscream_vwp = {}

for exp_name, exp_config in DPSCREAM_EXPERIMENTS.items():
    print(f"Loading DP-SCREAM VWP: {exp_name}")
    try:
        vwp = load_dpscream_vwp(
            exp_config['path'], 
            exp_config['file'],
            multipart=exp_config['multipart'],
            n_parts=exp_config.get('n_parts', 4)
        )
        dpscream_vwp[exp_name] = {'data': vwp, 'config': exp_config}
        print(f"  ✓ Loaded {len(vwp.time)} time steps")
    except Exception as e:
        print(f"  ✗ Error loading {exp_name}: {e}")

# %%
# Load all configured new DP-SCREAM experiments
dpscream_new_vwp = {}

for exp_name, exp_config in DPSCREAM_NEW_EXPERIMENTS.items():
    print(f"Loading DP-SCREAM VWP: {exp_name}")
    try:
        vwp = load_dpscream_vwp_new(
            exp_config['path'], 
            exp_config['file'],
            multipart=exp_config['multipart'],
            n_parts=exp_config.get('n_parts', 4)
        )
        dpscream_new_vwp[exp_name] = {'data': vwp, 'config': exp_config}
        print(f"  ✓ Loaded {len(vwp.time)} time steps")
    except Exception as e:
        print(f"  ✗ Error loading {exp_name}: {e}")
# %% [markdown]
# ## Plot Water Vapor Path Comparison
# 
# Compare domain-average VWP time series across all experiments.

# Time range for plotting
ti, tf = PLOT_TIME_RANGE

# Create figure
fig, ax = plt.subplots(1, 1, figsize=(11, 5))

# Plot PINACLES experiments
for exp_name, exp_data in pinacles_vwp.items():
    vwp = exp_data['data'].VWP.sel(time=slice(ti, tf))
    config = exp_data['config']
    _=ax.plot(vwp.time, vwp,
           color=config['color'],
           alpha=0.7,
           label=config['label'],
           linestyle=config['linestyle'],
           linewidth=1.5)

# Plot DP-SCREAM experiments (need to average over ncol dimension)
for exp_name, exp_data in dpscream_vwp.items():
    vwp_data = exp_data['data'].sel(time=slice(ti, tf))
    config = exp_data['config']
    
    # Check if VWP variable exists, otherwise try column_water_vapor
    if 'VWP' in vwp_data.data_vars:
        vwp = vwp_data.VWP.mean('ncol')
    elif 'column_water_vapor' in vwp_data.data_vars:
        vwp = vwp_data.column_water_vapor.mean('ncol')
    else:
        # If neither, just take the mean of all data variables
        vwp = vwp_data.mean('ncol')
    
    _=ax.plot(vwp.time, vwp,
           color=config['color'],
           alpha=0.7,
           label=config['label'],
           linewidth=1.5,
           linestyle=config['linestyle'])

# Plot new 1km DP-SCREAM experiments
for exp_name, exp_data in dpscream_new_vwp.items():
    vwp_data = exp_data['data'].sel(time=slice(ti, tf))
    config = exp_data['config']
    
    # Check if VWP variable exists, otherwise try column_water_vapor
    vwp = exp_data['data'].VapWaterPath.sel(time=slice(ti, tf))
    
    _=ax.plot(vwp.time, vwp,
           color=config['color'],
           alpha=0.7,
           label=config['label'],
           linewidth=1.5,
           linestyle=config['linestyle'])

# Formatting
_=ax.set_title('Domain-Average Water Vapor Path', fontsize=12, loc='left')
_=ax.set_ylabel('kg/m²', fontsize=11)
_=ax.set_xlabel('Day of Year', fontsize=11)
_=ax.grid(True, alpha=0.3, linestyle='--')
_=ax.legend(frameon=False, fontsize=9, loc='best')

# Convert x-axis to day of year
xticks = ax.get_xticks()
xtick_labels = [pd.Timestamp(mdates.num2date(tick)).dayofyear for tick in xticks]
_=ax.set_xticks(xticks)
_=ax.set_xticklabels(xtick_labels)
_=ax.set_xlim(pd.Timestamp(ti), pd.Timestamp(tf))

plt.tight_layout()

# # Save figure if requested
# if SAVE_FIGURE:
#     plt.savefig(FIGURE_NAME, dpi=300, bbox_inches='tight')
#     print(f"Figure saved as {FIGURE_NAME}")

# plt.show()

# %%


# %%



