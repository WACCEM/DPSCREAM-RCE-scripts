# -*- coding: utf-8 -*-
"""
Process 2D & 3D fields and put them on an x & y grid.
Data will be placed in a folder called post_processed_output
in your case directory.

3D currently only works with data on the lev grid (as opposed to ilev).
This is because ilev currently doesn't appear to be written to to
output files for some reason.

This comes with no warranty and is provided as a convenience. 
"""

import netCDF4 as nc4
import numpy as np
import scipy as sp
from scipy.sparse import csr_matrix
import pylab
import os
import glob
import matplotlib.pyplot as plt

###### Start user input ################################################
# What variables do you want to process?  You have two options, you
#   can either list specific variables or simply put "all" to regrid every
#   2D & 3D variable in your output stream. Example below of selected vars.
#vartodo=["T_mid","IceWaterPath"]
vartodo=["all"]

# Supply the run directory, casename, and the specific input file to process
casedir='/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/'
casename='test_regrid_cpu_dpxx_RCE_dx1km'
inputfile=casedir+casename+'/run/test_regrid_cpu_dpxx_RCE_dx1km.hist.INSTANT.nmins_x5.2000-01-01-00000.nc'

# --- ESMF weight-based regridding ---
# Set use_esmf_weights=True to regrid using a pre-computed ESMF weight file
# produced by ESMF_RegridWeightGen.  The weight file must map from the
# DP-SCREAM unstructured source grid (n_a columns, in the same ncol order
# as the model output) to the desired regular destination grid.
# When False, the native reshape method is used instead.
use_esmf_weights = True
weightdir = '/global/cfs/cdirs/wcm_shr/DP-SCREAM/remap/'
weightfile = 'DPSCREAM_RCE_dx1km_600x600km_to_PINACLES_YX_dx1km_600x600km_conserve.nc'
# Destination grid spacing in metres — used to compute Cartesian x/y
# cell-centre coordinates (750, 2250, ...) when use_esmf_weights=True.
dst_dx = 1500.0

###### End user input

weightfile_path = weightdir + weightfile
if use_esmf_weights and not os.path.isfile(weightfile_path):
   raise FileNotFoundError(
      'ESMF weight file not found at the specified path: {}'.format(weightfile_path))

#######################################################################

def regrid_array(data, x_coords, y_coords):
    # Create dictionaries to map the coordinates to their indices
    unique_x = sorted(set(x_coords))
    unique_y = sorted(set(y_coords))
    
    x_index = {value: idx for idx, value in enumerate(unique_x)}
    y_index = {value: idx for idx, value in enumerate(unique_y)}
    
    # Determine the shape of the 2D array
    max_x = len(unique_x)
    max_y = len(unique_y)

    # Convert x_coords and y_coords to indices
    x_indices = np.array([x_index[x] for x in x_coords])
    y_indices = np.array([y_index[y] for y in y_coords])
    
    # Determine the number of slices (time or vertical levels)
    num_slices = data.shape[0]
    
    if (data.ndim == 2):
    
       # Create an empty 3D array with the determined shape
       arranged_array = np.empty((num_slices, max_y, max_x))
    
       # Use advanced indexing to place the data in the correct locations in one go
       arranged_array[:, y_indices, x_indices] = data
       
    if (data.ndim == 3):
       num_levs = data.shape[2]  # Assuming the 3rd dimension is the number of levels
    
       # Create an empty 4D array with the determined shape
       arranged_array = np.empty((num_slices, num_levs, max_y, max_x))

       # Vectorized operation to place data into 4D array
       # Use broadcasting to index array positions efficiently
       arranged_array[:, :, y_indices, x_indices] = data.transpose(0, 2, 1)
    
    # Create the appropriately arranged x and y coordinate arrays
    arranged_x_coords = np.array(unique_x)
    arranged_y_coords = np.array(unique_y)
    
    return arranged_array, arranged_x_coords, arranged_y_coords

################################

def SCREAM_get_cords(initfile):

   f=nc4.Dataset(initfile)
   time=f.variables['time'][:]
   lev=f.variables['lev'][:] if 'lev' in f.variables else None
   crm_grid_x=f.variables['lon'][:]
   crm_grid_y=f.variables['lat'][:]
   
#   conversion_fac=(3.14/180.)
   conversion_fac=1.
   
   crm_grid_x=crm_grid_x*conversion_fac
   crm_grid_y=crm_grid_y*conversion_fac
   
   f.close()

   return time, lev, crm_grid_x, crm_grid_y

################################

def determine_var_dim(var,var_name,matching_vars,dimarr):

   # Check if the dimensions are ('time', 'ncol')
   if var.dimensions == ('time', 'ncol'):
      matching_vars.append(var_name)
      dimarr.append('2D')
   
   # Check if the dimensions are ('time', 'ncol')
   if var.dimensions == ('time', 'ncol','lev'):
      matching_vars.append(var_name)
      dimarr.append('3D')   

################################
   
def find_variables(filename,varlist_in):
    # Open the NetCDF file
    dataset = nc4.Dataset(filename)

    # Initialize a list to store variable names that match the criteria
    matching_vars = []
    dimarr = []

    for var_entry in varlist_in:

       # If all variables are done, search for variables in file
       if (var_entry == "all"): 

          # Iterate over all the variables in the NetCDF file
          for var_name in dataset.variables:
             var = dataset.variables[var_name]
             determine_var_dim(var,var_name,matching_vars,dimarr)		
       else:

          # user specified output
          var = dataset.variables[var_entry]
          determine_var_dim(var,var_entry,matching_vars,dimarr)

    # Close the dataset
    dataset.close()

    return matching_vars, dimarr

################################

def check_path(dim):
   
   # Check to see if post process directory exists for 2d output; if not create it
   postpath_dim=casedir+casename+'/post_processed_output/'+dim+'/'
   ishere=os.path.isdir(postpath_dim)

   # Make directory for post processing
   if not ishere:
      os.system('mkdir '+postpath_dim)
      
   return postpath_dim

################################

def load_esmf_weights(weightfile):
   """Load an ESMF offline regridding weight file (SCRIP/NCAR-CSM format) and
   return a sparse weight matrix together with the destination grid coordinates.

   The weight file is produced by ESMF_RegridWeightGen.  It contains:
     col / row  : 1-indexed source / destination cell indices   (n_s,)
     S          : interpolation weights                          (n_s,)
     dst_grid_dims : [nx, ny] of the destination grid           (Fortran order)
     xc_b / yc_b   : destination cell-centre coordinates in degrees

   Returns
   -------
   W        : scipy.sparse.csr_matrix of shape (n_b, n_a)
   x_out    : 1-D array of destination x (longitude) coordinates, degrees
   y_out    : 1-D array of destination y (latitude)  coordinates, degrees
   nx_out   : number of destination x points
   ny_out   : number of destination y points
   n_a      : number of source columns (must match ncol in the model output)
   """
   f    = nc4.Dataset(weightfile)
   col  = f.variables['col'][:].astype(int) - 1   # convert to 0-indexed
   row  = f.variables['row'][:].astype(int) - 1   # convert to 0-indexed
   S    = f.variables['S'][:]
   n_a  = len(f.dimensions['n_a'])
   n_b  = len(f.dimensions['n_b'])
   # In ESMF/SCRIP, dst_grid_dims lists dimensions in Fortran order where the
   # first element is the fastest-varying dimension.  For the PINACLES YX grid
   # Y (latitude) is the fast index, so dst_dims[0]=ny_out and dst_dims[1]=nx_out.
   dst_dims = f.variables['dst_grid_dims'][:]
   ny_out   = int(dst_dims[0])   # fast dim = lat
   nx_out   = int(dst_dims[1])   # slow dim = lon
   xc_b = f.variables['xc_b'][:]
   yc_b = f.variables['yc_b'][:]
   f.close()

   W = csr_matrix((S, (row, col)), shape=(n_b, n_a))

   # Flat index: k = ix * ny_out + iy  (lon slow, lat fast).
   # C-order reshape to (nx_out, ny_out) gives arr[ix, iy].
   xc_b_2d = xc_b.reshape(nx_out, ny_out)
   yc_b_2d = yc_b.reshape(nx_out, ny_out)
   x_out   = xc_b_2d[:, 0]   # unique lon values (one per lon strip, iy=0)
   y_out   = yc_b_2d[0, :]   # unique lat values (one per lat strip, ix=0)

   return W, x_out, y_out, nx_out, ny_out, n_a

################################

def apply_esmf_weights(data, W, ny_out, nx_out):
   """Apply the ESMF sparse weight matrix to data on the unstructured source grid.

   Parameters
   ----------
   data   : ndarray, shape (ntime, ncol) for 2-D fields
                     or (ntime, ncol, nlev) for 3-D fields
   W      : scipy.sparse CSR matrix, shape (n_b, n_a)  with n_a == ncol
   ny_out : number of destination y points
   nx_out : number of destination x points

   Returns
   -------
   out : ndarray, shape (ntime, ny_out, nx_out)         for 2-D fields
                  or    (ntime, nlev, ny_out, nx_out)   for 3-D fields
   """
   ntime = data.shape[0]

   if data.ndim == 2:
      out = np.empty((ntime, ny_out, nx_out), dtype=np.float32)
      for t in range(ntime):
         # Flat k = ix*ny_out + iy; reshape to (nx,ny) then transpose -> (ny,nx)=(lat,lon)
         out[t] = W.dot(data[t]).reshape(nx_out, ny_out).T

   elif data.ndim == 3:
      nlev = data.shape[2]
      out  = np.empty((ntime, nlev, ny_out, nx_out), dtype=np.float32)
      for t in range(ntime):
         for k in range(nlev):
            out[t, k] = W.dot(data[t, :, k]).reshape(nx_out, ny_out).T

   return out

##############################################################################  
##############################################################################
##############################################################################
# Begin main function

# Check to see if post process directory exists; if not create it
postpath=casedir+casename+'/post_processed_output/'
ishere=os.path.isdir(postpath)

# Make directory for post processing
if not ishere:
   os.system('mkdir '+postpath)
   
############################################################
#

# Make a list of files to process
filelist=[inputfile]
print(inputfile)
# Get coordinates and timing information
# open first file
time_in, lev_in, crm_grid_x, crm_grid_y = SCREAM_get_cords(filelist[0])

if use_esmf_weights:
   # Load ESMF weight matrix and destination grid coordinates
   W_esmf, arranged_x_coords, arranged_y_coords, nx_esmf, ny_esmf, n_a_esmf = \
      load_esmf_weights(weightfile_path)
   print('Loaded ESMF weights: src={:d} cols -> dst={:d}x{:d} grid'.format(
         n_a_esmf, ny_esmf, nx_esmf))
   if n_a_esmf != len(crm_grid_x):
      raise ValueError(
         'ESMF weight file has {:d} source columns but the model output has '
         '{:d} ncol values.  Ensure the weight file matches this grid.'.format(
         n_a_esmf, len(crm_grid_x)))
else:
   # Native reshape: reconstruct the regular grid from the unique coordinate values
   unique_x = sorted(set(crm_grid_x))
   unique_y = sorted(set(crm_grid_y))
   arranged_x_coords = np.array(unique_x)
   arranged_y_coords = np.array(unique_y)

# figure out number of times in files
numfiles=len(filelist)
numtimes=len(time_in)

# figure out number of times for output file
ntimes=numtimes*(numfiles-1.)

# figure out number of times in last file
if (numfiles > 1):
   time_in, lev_in, crm_grid_x, crm_grid_y = SCREAM_get_cords(filelist[len(filelist)-1])
   ntimes=ntimes+len(time_in)

# Are we doing all variables or selected variables?
vartodo,dimarr=find_variables(filelist[0],vartodo)

numvars=len(vartodo)

#############################################################
# Process each variable one at a time
for v in range(0,numvars):

   # Make sure output directory has been created
   postpath_dim=check_path(dimarr[v])

   print('PROCESSING VARIABLE: ',vartodo[v])
   outputfile=postpath_dim+casename+'_'+dimarr[v]+'_'+vartodo[v]+'.nc'   
   
   ishere=os.path.isfile(outputfile)
   print('Making output file ',outputfile)
   if ishere:
      os.system('rm '+outputfile)
   f=nc4.Dataset(outputfile,'w',format='NETCDF4')
   if use_esmf_weights:
      f.createDimension('lon', len(arranged_x_coords))
      f.createDimension('lat', len(arranged_y_coords))
   else:
      f.createDimension('x', len(arranged_x_coords))
      f.createDimension('y', len(arranged_y_coords))
   f.createDimension('time',ntimes)
   if (dimarr[v] == '3D'):
      f.createDimension('lev',len(lev_in))

   if use_esmf_weights:
      lon_var = f.createVariable('lon', 'f4', 'lon')
      lat_var = f.createVariable('lat', 'f4', 'lat')
      x_var   = f.createVariable('x',   'f4', 'lon')
      y_var   = f.createVariable('y',   'f4', 'lat')
   else:
      x_var = f.createVariable('x', 'f4', 'x')
      y_var = f.createVariable('y', 'f4', 'y')
   time=f.createVariable('time','f4','time')
   if use_esmf_weights:
      if (dimarr[v] == '2D'):
         out_var=f.createVariable(vartodo[v],'f4',('time','lat','lon'),
                                  fill_value=np.float32(9.96921e+36))
      if (dimarr[v] == '3D'):
         lev=f.createVariable('lev','f4','lev')
         out_var=f.createVariable(vartodo[v],'f4',('time','lev','lat','lon'),
                                  fill_value=np.float32(9.96921e+36))
   else:
      if (dimarr[v] == '2D'):
         out_var=f.createVariable(vartodo[v],'f4',('time','y','x'),
                                  fill_value=np.float32(9.96921e+36))
      if (dimarr[v] == '3D'):
         lev=f.createVariable('lev','f4','lev')
         out_var=f.createVariable(vartodo[v],'f4',('time','lev','y','x'),
                                  fill_value=np.float32(9.96921e+36))

   if use_esmf_weights:
      lon_var[:] = arranged_x_coords
      lon_var.units = 'degrees_east'
      lon_var.long_name = 'longitude'

      lat_var[:] = arranged_y_coords
      lat_var.units = 'degrees_north'
      lat_var.long_name = 'latitude'

      x_meters = np.arange(len(arranged_x_coords)) * dst_dx + dst_dx / 2.0
      y_meters = np.arange(len(arranged_y_coords)) * dst_dx + dst_dx / 2.0
      x_var[:] = x_meters
      x_var.units = 'm'
      x_var.long_name = 'x coordinate'
      y_var[:] = y_meters
      y_var.units = 'm'
      y_var.long_name = 'y coordinate'
   else:
      x_var[:] = arranged_x_coords
      x_var.units = 'm'
      x_var.long_name = 'x coordinate'
      y_var[:] = arranged_y_coords
      y_var.units = 'm'
      y_var.long_name = 'y coordinate'
   
   if (dimarr[v] == '3D'):
      lev[:]=lev_in
      lev.units='mb'
      lev.long_name='hybrid level at midpoints'      

   time.units='days'
   time.long_name='time'

   out_var.long_name=vartodo[v]
   
   # Now loop over each file
   ts=0
   te=numtimes
   for thefile in filelist:
   
      print("Processing file: ", thefile)
      
      fi=nc4.Dataset(thefile,mode='r')
      fi.set_auto_mask(False)   # return plain numpy arrays
      time_in=fi.variables['time'][:]
      var=fi.variables[vartodo[v]][:].astype(np.float32)
      # Replace source fill / unphysical values with NaN so they propagate
      # cleanly through the sparse dot product rather than contaminating
      # destination cells with huge numbers.
      var[var >= 1e30] = np.nan

      if use_esmf_weights:
         var_arranged = apply_esmf_weights(var, W_esmf, ny_esmf, nx_esmf)
      else:
         var_arranged,dummyx,dummyy=regrid_array(var, crm_grid_x, crm_grid_y)

      # Convert any NaN in regridded output to the standard fill value so
      # that ncdump / ncview honour the _FillValue attribute correctly.
      fill_out = np.float32(9.96921e+36)
      var_arranged = np.where(np.isnan(var_arranged), fill_out, var_arranged)
   
      te=ts+len(time_in)
      time[ts:te]=time_in
      if (dimarr[v] == '2D'):
         out_var[ts:te,:,:]=var_arranged
      if (dimarr[v] == '3D'):
         out_var[ts:te,:,:,:]=var_arranged
      ts=te
   
      del(var)
      del(var_arranged)
   
      fi.close()

   f.close()
