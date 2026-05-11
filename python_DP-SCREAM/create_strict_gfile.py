import netCDF4
import numpy as np

def create_uxarray_compliant_exodus(filename, nx, ny, Lx, Ly):
    # --- Setup Dimensions ---
    num_nodes = (nx + 1) * (ny + 1)
    num_elem = nx * ny
    
    with netCDF4.Dataset(filename, 'w', format='NETCDF4_CLASSIC') as nc:
        # --- 1. Define Dimensions ---
        # CHANGE 1: Set num_dim to 3 so we can include Z coords
        nc.createDimension('num_dim', 3)
        nc.createDimension('num_nodes', num_nodes)
        nc.createDimension('num_elem', num_elem)
        nc.createDimension('num_el_blk', 1)
        
        # Dimensions for Block 1 (Required by UXarray)
        nc.createDimension('num_el_in_blk1', num_elem)
        nc.createDimension('num_nod_per_el1', 4) 
        
        # Dimension for strings
        nc.createDimension('len_name', 33) 
        
        # --- 2. Global Attributes ---
        nc.api_version = 4.98
        nc.version = 4.98
        nc.floating_point_word_size = 8
        nc.file_size = 1
        nc.title = "DP-SCREAM Planar Mesh"

        # --- 3. Coordinates ---
        x_1d = np.linspace(0, Lx, nx + 1)
        y_1d = np.linspace(0, Ly, ny + 1)
        X, Y = np.meshgrid(x_1d, y_1d) 
        
        vx = nc.createVariable('coordx', 'f8', ('num_nodes',))
        vy = nc.createVariable('coordy', 'f8', ('num_nodes',))
        # CHANGE 2: Add coordz variable
        vz = nc.createVariable('coordz', 'f8', ('num_nodes',))
        
        vx[:] = X.flatten()
        vy[:] = Y.flatten()
        # CHANGE 3: Set Z to 0.0 for all nodes
        vz[:] = np.zeros(num_nodes)
        
        # Coordinate Names
        coord_names = nc.createVariable('coor_names', 'S1', ('num_dim', 'len_name'))
        coord_names[0] = netCDF4.stringtochar(np.array(['x'], 'S33'))
        coord_names[1] = netCDF4.stringtochar(np.array(['y'], 'S33'))
        # CHANGE 4: Add 'z' name
        coord_names[2] = netCDF4.stringtochar(np.array(['z'], 'S33'))

        # --- 4. Connectivity ---
        connect = np.zeros((num_elem, 4), dtype='int32')
        
        idx = 0
        for j in range(ny):
            for i in range(nx):
                # Counter-Clockwise winding
                n1 = i + j * (nx + 1)
                n2 = (i + 1) + j * (nx + 1)
                n3 = (i + 1) + (j + 1) * (nx + 1)
                n4 = i + (j + 1) * (nx + 1)
                # 1-based indexing
                connect[idx, :] = [n1+1, n2+1, n3+1, n4+1]
                idx += 1
                
        v_conn = nc.createVariable('connect1', 'i4', ('num_el_in_blk1', 'num_nod_per_el1'))
        v_conn.setncattr('elem_type', 'QUAD') 
        v_conn[:] = connect

        # --- 5. Element Block IDs ---
        v_eb_prop = nc.createVariable('eb_prop1', 'i4', ('num_el_blk',))
        v_eb_prop.setncattr('name', 'ID') 
        v_eb_prop[:] = [1]
        
        v_eb_status = nc.createVariable('eb_status', 'i4', ('num_el_blk',))
        v_eb_status[:] = [1]
        
        print(f"Successfully created {filename} (3D-Compliant)")

# --- USER SETTINGS ---
nx_sim = 200
ny_sim = 200
Lx_sim = 600000.0
Ly_sim = 600000.0

create_uxarray_compliant_exodus('planar_mesh_v5.g', nx_sim, ny_sim, Lx_sim, Ly_sim)