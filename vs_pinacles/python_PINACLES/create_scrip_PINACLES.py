# %%
import xarray as xr
import numpy as np
import netCDF4 as nc
import os

# %%
def create_pinacles_scrip_xy_transposed(pinacles_file, scrip_file, target_lat=0.0, target_lon=0.0):
    # --- 1. READ PINACLES DIMENSIONS ---
    print(f"Reading coordinates from {pinacles_file}...")
    ds = xr.open_dataset(pinacles_file, engine='netcdf4')
    
    # Read 1D axes (Meters)
    x_m = ds['X'].values 
    y_m = ds['Y'].values
    
    nx = len(x_m)
    ny = len(y_m)
    n_cells = nx * ny
    
    print(f"  Grid Shape: {nx} (x) x {ny} (y)")
    print(f"  Data Ordering: (time, X, Y) -> Y varies fastest")

    # Determine Grid Spacing
    dx = np.mean(np.diff(x_m))
    dy = np.mean(np.diff(y_m))

    # --- 2. GENERATE MESH (THE KEY CHANGE) ---
    # use indexing='ij' to create (nx, ny) arrays
    # X_2d[i, j] corresponds to x[i]
    # Y_2d[i, j] corresponds to y[j]
    X_2d, Y_2d = np.meshgrid(x_m, y_m, indexing='ij')
    
    # Flattening these now follows the (X, Y) storage order:
    # It walks the last dimension (Y) first.
    # Sequence: (x0, y0), (x0, y1), (x0, y2) ... (x1, y0) ...
    x_flat_m = X_2d.flatten()
    y_flat_m = Y_2d.flatten()

    # --- 3. CONVERT TO DEGREES ---
    # Earth Radius constants
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * np.cos(np.deg2rad(target_lat))
    
    # Calculate Center Offsets
    x_domain_center = (x_m.max() + x_m.min()) / 2.0
    y_domain_center = (y_m.max() + y_m.min()) / 2.0
    
    x_offset = x_flat_m - x_domain_center
    y_offset = y_flat_m - y_domain_center
    
    # Convert to Lat/Lon
    center_lon = target_lon + (x_offset / m_per_deg_lon)
    center_lat = target_lat + (y_offset / m_per_deg_lat)

    # --- 4. CALCULATE CORNERS ---
    corner_lat = np.zeros((n_cells, 4))
    corner_lon = np.zeros((n_cells, 4))
    
    dx2 = dx / 2.0
    dy2 = dy / 2.0
    
    # Corners relative to center (SW, SE, NE, NW)
    # 1: SW (-dx, -dy)
    corner_lat[:, 0] = target_lat + ((y_offset - dy2) / m_per_deg_lat)
    corner_lon[:, 0] = target_lon + ((x_offset - dx2) / m_per_deg_lon)
    
    # 2: SE (+dx, -dy)
    corner_lat[:, 1] = target_lat + ((y_offset - dy2) / m_per_deg_lat)
    corner_lon[:, 1] = target_lon + ((x_offset + dx2) / m_per_deg_lon)
    
    # 3: NE (+dx, +dy)
    corner_lat[:, 2] = target_lat + ((y_offset + dy2) / m_per_deg_lat)
    corner_lon[:, 2] = target_lon + ((x_offset + dx2) / m_per_deg_lon)
    
    # 4: NW (-dx, +dy)
    corner_lat[:, 3] = target_lat + ((y_offset + dy2) / m_per_deg_lat)
    corner_lon[:, 3] = target_lon + ((x_offset - dx2) / m_per_deg_lon)

    # --- 5. WRITE SCRIP FILE ---
    print(f"Writing to {scrip_file}...")
    # Remove existing file if it exists to avoid permission errors
    if os.path.exists(scrip_file):
        os.remove(scrip_file)
    f = nc.Dataset(scrip_file, 'w', format='NETCDF3_64BIT_OFFSET') #format='NETCDF3_64BIT_OFFSET' format='NETCDF4_CLASSIC'
    
    f.createDimension('grid_size', n_cells)
    f.createDimension('grid_corners', 4)
    f.createDimension('grid_rank', 2)
    
    v_dims = f.createVariable('grid_dims', 'i4', ('grid_rank',))
    v_dims[:] = [nx, ny] # Metadata: Matches your (X, Y) dims
    
    v_clat = f.createVariable('grid_center_lat', 'f8', ('grid_size',))
    v_clat.units = "degrees"
    v_clat[:] = center_lat
    
    v_clon = f.createVariable('grid_center_lon', 'f8', ('grid_size',))
    v_clon.units = "degrees"
    v_clon[:] = center_lon
    
    v_imask = f.createVariable('grid_imask', 'i4', ('grid_size',))
    v_imask[:] = 1
    
    v_corn_lat = f.createVariable('grid_corner_lat', 'f8', ('grid_size', 'grid_corners'))
    v_corn_lat.units = "degrees"
    v_corn_lat[:] = corner_lat
    
    v_corn_lon = f.createVariable('grid_corner_lon', 'f8', ('grid_size', 'grid_corners'))
    v_corn_lon.units = "degrees"
    v_corn_lon[:] = corner_lon
    
    # Add Attributes to help tools verify it
    f.title = "PINACLES Rectilinear Grid (SCRIP format)"
    f.Conventions = "SCRIP"

    f.close()
    print("Done. Grid matches (time, X, Y) ordering.")

# %%
def create_pinacles_scrip_yx_original(pinacles_file, scrip_file, target_lat=0.0, target_lon=0.0):
    # --- 1. READ PINACLES DIMENSIONS ---
    print(f"Reading coordinates from {pinacles_file}...")
    ds = xr.open_dataset(pinacles_file, engine='netcdf4')
    
    # Read 1D axes (Meters)
    x_m = ds['X'].values 
    y_m = ds['Y'].values
    
    nx = len(x_m)
    ny = len(y_m)
    n_cells = nx * ny
    
    print(f"  Grid Shape: {nx} (x) x {ny} (y)")
    print(f"  Data Ordering: (time, Y, X) -> X varies fastest")

    # Determine Grid Spacing
    dx = np.mean(np.diff(x_m))
    dy = np.mean(np.diff(y_m))

    # --- 2. GENERATE MESH (THE KEY CHANGE) ---
    # use indexing='ij' to create (nx, ny) arrays
    # X_2d[i, j] corresponds to x[i]
    # Y_2d[i, j] corresponds to y[j]
    X_2d, Y_2d = np.meshgrid(x_m, y_m, indexing='ij')
    
    # Flattening these follows the common (Y, X) storage order:
    # It walks the last dimension (X) first.
    # Sequence: (y0, x0), (y0, x1), (y0, x2) ... (y1, x0) ...
    x_flat_m = X_2d.flatten()
    y_flat_m = Y_2d.flatten()

    # --- 3. CONVERT TO DEGREES ---
    # Earth Radius constants
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * np.cos(np.deg2rad(target_lat))
    
    # Calculate Center Offsets
    x_domain_center = (x_m.max() + x_m.min()) / 2.0
    y_domain_center = (y_m.max() + y_m.min()) / 2.0
    
    x_offset = x_flat_m - x_domain_center
    y_offset = y_flat_m - y_domain_center
    
    # Convert to Lat/Lon
    center_lon = target_lon + (x_offset / m_per_deg_lon)
    center_lat = target_lat + (y_offset / m_per_deg_lat)

    # --- 4. CALCULATE CORNERS ---
    corner_lat = np.zeros((n_cells, 4))
    corner_lon = np.zeros((n_cells, 4))
    
    dx2 = dx / 2.0
    dy2 = dy / 2.0
    
    # Corners relative to center (SW, SE, NE, NW)
    # 1: SW (-dx, -dy)
    corner_lat[:, 0] = target_lat + ((y_offset - dy2) / m_per_deg_lat)
    corner_lon[:, 0] = target_lon + ((x_offset - dx2) / m_per_deg_lon)
    
    # 2: SE (+dx, -dy)
    corner_lat[:, 1] = target_lat + ((y_offset - dy2) / m_per_deg_lat)
    corner_lon[:, 1] = target_lon + ((x_offset + dx2) / m_per_deg_lon)
    
    # 3: NE (+dx, +dy)
    corner_lat[:, 2] = target_lat + ((y_offset + dy2) / m_per_deg_lat)
    corner_lon[:, 2] = target_lon + ((x_offset + dx2) / m_per_deg_lon)
    
    # 4: NW (-dx, +dy)
    corner_lat[:, 3] = target_lat + ((y_offset + dy2) / m_per_deg_lat)
    corner_lon[:, 3] = target_lon + ((x_offset - dx2) / m_per_deg_lon)

    # --- 5. WRITE SCRIP FILE ---
    print(f"Writing to {scrip_file}...")
    # Remove existing file if it exists to avoid permission errors
    if os.path.exists(scrip_file):
        os.remove(scrip_file)
    f = nc.Dataset(scrip_file, 'w', format='NETCDF3_64BIT_OFFSET') #format='NETCDF3_64BIT_OFFSET' format='NETCDF4_CLASSIC'
    
    f.createDimension('grid_size', n_cells)
    f.createDimension('grid_corners', 4)
    f.createDimension('grid_rank', 2)
    
    v_dims = f.createVariable('grid_dims', 'i4', ('grid_rank',))
    v_dims[:] = [nx, ny] # Metadata: Matches your (X, Y) dims
    
    v_clat = f.createVariable('grid_center_lat', 'f8', ('grid_size',))
    v_clat.units = "degrees"
    v_clat[:] = center_lat
    
    v_clon = f.createVariable('grid_center_lon', 'f8', ('grid_size',))
    v_clon.units = "degrees"
    v_clon[:] = center_lon
    
    v_imask = f.createVariable('grid_imask', 'i4', ('grid_size',))
    v_imask[:] = 1
    
    v_corn_lat = f.createVariable('grid_corner_lat', 'f8', ('grid_size', 'grid_corners'))
    v_corn_lat.units = "degrees"
    v_corn_lat[:] = corner_lat
    
    v_corn_lon = f.createVariable('grid_corner_lon', 'f8', ('grid_size', 'grid_corners'))
    v_corn_lon.units = "degrees"
    v_corn_lon[:] = corner_lon
    
    # Add Attributes to help tools verify it
    f.title = "PINACLES Rectilinear Grid (SCRIP format)"
    f.Conventions = "SCRIP"

    f.close()
    print("Done. Grid matches (time, Y, X) ordering.")

# %%
# --- EXECUTION ---
pinacles_filename = "/pscratch/sd/k/ksa/simulation/PINACLES/rce/test_runs2/RCE06_dx1km_150x150km/RCE06_dx1km_150x150km/fields2d/00d-00h-00m-00s-000ms.h5" 

# %%
scrip_filename    = "./scrip_PINACLES_YX_dx1km_150x150km.nc"

create_pinacles_scrip_yx_original(
    pinacles_filename, 
    scrip_filename, 
    target_lat=0.0, 
    target_lon=0.0
)

# %% [markdown]
# For PINACLES,the coordinate is: ordered time, x, y
# 
# 2D horizontal planes: (time, x, y) or (time, nx, ny)
# 
# 3D fields: (time, x, y, z) or (time, nx, ny, nz)
# 
# For the main part, arrays are created with C order (row major), but for interfaces with physics libraries, 
# arrays are created with Fortran order (order="F")

# %%
# scrip_filename    = "./scrip_PINACLES_XY_dx3km_600x600km.nc"

# create_pinacles_scrip_xy_transposed(
#     pinacles_filename, 
#     scrip_filename, 
#     target_lat=0.0, 
#     target_lon=0.0
# )



