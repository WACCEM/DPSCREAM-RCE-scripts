# %%
import xarray as xr
import numpy as np
import netCDF4 as nc
import os

# %%

rundir = "/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE01_dx3km_gpu/run"
hist_file = "RCE01_dx3km_gpu.hist.AVERAGE.nhours_x1.2000-01-01-00000.nc"
scrip_file  = "scrip_DPSCREAM_RCE_dx3km_600x600km.nc"

history_file = os.path.join(rundir, hist_file)

target_lat=0.0
target_lon=0.0

# Domain parameters from your setup
Lx = 600000.0
Ly = 600000.0
dx = 5000.0  # Physics grid spacing
dy = 5000.0


# %%
# Earth Radius approx for conversion
# 1 deg lat = 111320 meters
m_per_deg_lat = 111320.0
m_per_deg_lon = 111320.0 * np.cos(np.deg2rad(target_lat))

# --- 2. READ HISTORY FILE ---
print(f"Reading physics coordinates from {history_file}...")
ds = xr.open_dataset(history_file)

# Read the arrays (Shape: 160,000)
# These are in Meters (0 to 600,000)
# They contain the specific "Z-curve" ordering
lat_m_in = ds['lat'].values
lon_m_in = ds['lon'].values

n_cells = len(lat_m_in)
print(f"  Found {n_cells} physics columns (ncol).")

# --- 3. CONVERT CENTERS TO DEGREES ---
# We assume (Lx/2, Ly/2) is the center (target_lat, target_lon)
# So we shift the meters by half the domain size.

# Calculate offset from center in meters
y_offset_m = lat_m_in - (Ly / 2.0)
x_offset_m = lon_m_in - (Lx / 2.0)

# Convert to degrees
center_lat = target_lat + (y_offset_m / m_per_deg_lat)
center_lon = target_lon + (x_offset_m / m_per_deg_lon)

# --- 4. CALCULATE CORNERS ---
# For every center point, calculate the 4 corners relative to it.
# Since we have the exact centers, we just add +/- dx/2.

# Initialize corner arrays (ncol, 4)
corner_lat = np.zeros((n_cells, 4))
corner_lon = np.zeros((n_cells, 4))

# Offsets in meters (Counter-Clockwise: SW, SE, NE, NW)
# Note: SCRIP standard is Counter-Clockwise
dx2 = dx / 2.0
dy2 = dy / 2.0

# Corner 1: SW (-x, -y)
corner_lat[:, 0] = target_lat + ((y_offset_m - dy2) / m_per_deg_lat)
corner_lon[:, 0] = target_lon + ((x_offset_m - dx2) / m_per_deg_lon)

# Corner 2: SE (+x, -y)
corner_lat[:, 1] = target_lat + ((y_offset_m - dy2) / m_per_deg_lat)
corner_lon[:, 1] = target_lon + ((x_offset_m + dx2) / m_per_deg_lon)

# Corner 3: NE (+x, +y)
corner_lat[:, 2] = target_lat + ((y_offset_m + dy2) / m_per_deg_lat)
corner_lon[:, 2] = target_lon + ((x_offset_m + dx2) / m_per_deg_lon)

# Corner 4: NW (-x, +y)
corner_lat[:, 3] = target_lat + ((y_offset_m + dy2) / m_per_deg_lat)
corner_lon[:, 3] = target_lon + ((x_offset_m - dx2) / m_per_deg_lon)

# --- 5. WRITE SCRIP FILE ---
print(f"Writing to {scrip_file}...")
# Remove existing file if it exists to avoid permission errors
if os.path.exists(scrip_file):
    os.remove(scrip_file)

f = nc.Dataset(scrip_file, 'w', format='NETCDF3_64BIT_OFFSET') #format='NETCDF3_64BIT_OFFSET' format='NETCDF4_CLASSIC'

# Dimensions
f.createDimension('grid_size', n_cells)
f.createDimension('grid_corners', 4)
f.createDimension('grid_rank', 1) # 1D Unstructured list

# Variables
v_dims = f.createVariable('grid_dims', 'i4', ('grid_rank',))
v_dims[:] = [n_cells]

v_clat = f.createVariable('grid_center_lat', 'f8', ('grid_size',))
v_clat.units = "degrees"
v_clat[:] = center_lat

v_clon = f.createVariable('grid_center_lon', 'f8', ('grid_size',))
v_clon.units = "degrees"
v_clon[:] = center_lon

v_imask = f.createVariable('grid_imask', 'i4', ('grid_size',))
v_imask.units = "unitless"
v_imask[:] = 1

v_corn_lat = f.createVariable('grid_corner_lat', 'f8', ('grid_size', 'grid_corners'))
v_corn_lat.units = "degrees"
v_corn_lat[:] = corner_lat

v_corn_lon = f.createVariable('grid_corner_lon', 'f8', ('grid_size', 'grid_corners'))
v_corn_lon.units = "degrees"
v_corn_lon[:] = corner_lon

    # Add Attributes to help tools verify it
f.title = "DP-SCREAM unstructured grid (SCRIP format)"
f.Conventions = "SCRIP"

f.close()
print("Done. Success!")

# %%



