import numpy as np
import netCDF4 as nc

def create_georeferenced_scrip(nx, ny, dx, dy, target_lat, target_lon, output_file="planar_scrip_deg.nc"):
    """
    Creates a SCRIP file where the planar grid is converted to approximate Degrees
    centered at the target latitude/longitude.
    
    nx, ny: Number of physics columns (400 for your case)
    dx, dy: Grid spacing in meters (1500.0 for your case)
    target_lat, target_lon: The values from your case.setup script (e.g., 0.0, 0.0)
    """
    n_cells = nx * ny
    Lx = nx * dx
    Ly = ny * dy
    
    # Earth radius approximation for degree conversion
    # 1 deg approx 111320 meters
    m_per_deg_lat = 111320.0
    # Adjust longitude scaling for latitude (cos(lat))
    m_per_deg_lon = 111320.0 * np.cos(np.deg2rad(target_lat))
    
    # 1. Generate Coordinates in Meters (Centered at 0)
    # Range: -Lx/2 to +Lx/2
    x_m = (np.arange(nx) * dx + dx/2.0) - Lx/2.0
    y_m = (np.arange(ny) * dy + dy/2.0) - Ly/2.0
    
    X_m, Y_m = np.meshgrid(x_m, y_m) # Shape (ny, nx)
    
    # 2. Convert to Degrees and Shift to Target
    center_lon = target_lon + (X_m.flatten() / m_per_deg_lon)
    center_lat = target_lat + (Y_m.flatten() / m_per_deg_lat)
    
    # 3. Generate Corners (in Meters first, then convert)
    corner_lon = np.zeros((n_cells, 4))
    corner_lat = np.zeros((n_cells, 4))
    
    # Offsets in meters relative to center
    offsets_x_m = np.array([-dx/2,  dx/2,  dx/2, -dx/2])
    offsets_y_m = np.array([-dy/2, -dy/2,  dy/2,  dy/2])
    
    for i in range(4):
        # Apply offset in meters, then convert to degrees
        # Note: This linear approximation is fine for small/planar domains
        corner_lon[:, i] = center_lon + (offsets_x_m[i] / m_per_deg_lon)
        corner_lat[:, i] = center_lat + (offsets_y_m[i] / m_per_deg_lat)

    # 4. Write NetCDF (SCRIP Format)
    f = nc.Dataset(output_file, 'w', format='NETCDF4_CLASSIC')
    
    f.createDimension('grid_size', n_cells)
    f.createDimension('grid_corners', 4)
    f.createDimension('grid_rank', 2)
    
    v_dims = f.createVariable('grid_dims', 'i4', ('grid_rank',))
    v_dims[:] = [nx, ny] 
    
    v_center_lat = f.createVariable('grid_center_lat', 'f8', ('grid_size',))
    v_center_lat.units = "degrees_north"
    v_center_lat[:] = center_lat
    
    v_center_lon = f.createVariable('grid_center_lon', 'f8', ('grid_size',))
    v_center_lon.units = "degrees_east"
    v_center_lon[:] = center_lon
    
    v_corner_lat = f.createVariable('grid_corner_lat', 'f8', ('grid_size', 'grid_corners'))
    v_corner_lat.units = "degrees_north"
    v_corner_lat[:] = corner_lat
    
    v_corner_lon = f.createVariable('grid_corner_lon', 'f8', ('grid_size', 'grid_corners'))
    v_corner_lon.units = "degrees_east"
    v_corner_lon[:] = corner_lon
    
    v_imask = f.createVariable('grid_imask', 'i4', ('grid_size',))
    v_imask[:] = 1
    
    f.close()
    print(f"Created {output_file} centered at {target_lat}, {target_lon}")

# --- YOUR CONFIGURATION ---
# Based on your setup:
# Lat/Lon from script header
target_lat_sim = 0.0
target_lon_sim = 0.0

# Grid Setup for ncol=160000 (Physics Grid)
# nx = 400, dx = 1500m
create_georeferenced_scrip(
    nx=400, 
    ny=400, 
    dx=1500.0, 
    dy=1500.0, 
    target_lat=target_lat_sim, 
    target_lon=target_lon_sim
)