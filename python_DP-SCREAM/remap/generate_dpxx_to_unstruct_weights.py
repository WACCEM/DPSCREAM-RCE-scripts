# -*- coding: utf-8 -*-
"""
Generate a nearest-neighbour mapping file that remaps from the DPxx structured
physics grid to an arbitrary unstructured destination grid.

This is an ILLUSTRATION script.  The destination grid is a small randomly
scattered set of points inside the domain (a "dummy" unstructured grid).
Replace the dst_x / dst_y arrays with your real destination coordinates to
use this for an actual case.

The output file contains:
  S   (n_s)  – sparse weights  (all 1.0 for nearest-neighbour)
  col (n_s)  – 1-based source column indices
  row (n_s)  – 1-based destination point indices

These three arrays are all the EAMxx online remapper needs
(same format as the horizontal-average mapping file).

Point to the result in your YAML file like so:
  horiz_remap_file: /path/to/mapping_dpxx_..._to_unstruct_NNpts.YYYYMMDD.nc

Script author: adapted from generate_dpxx_horiz_avg_weights.py
               (Bogenschutz / Zhang)
"""

import netCDF4 as nc4
import numpy as np
import os
from datetime import datetime
from scipy.spatial import cKDTree

#######################################################################
###### Start user input

# Source grid – must match your run script exactly
num_ne_x     = 200
num_ne_y     = 200
domain_size_x = 600000   # [m]
domain_size_y = 600000   # [m]

# Destination (unstructured) grid
#   Here we create a DUMMY grid using a jittered regular lattice.
#   This gives uniform spatial coverage (unlike pure random scatter) while
#   still being "unstructured" – a good approximation of a real unstructured mesh.
#   Replace dst_x / dst_y with your real destination coordinates (in metres,
#   same Cartesian system as the source grid) for an actual case.
np.random.seed(42)          # fix seed so the dummy grid is reproducible
n_dst_x = 100                 # lattice columns
n_dst_y = 150                 # lattice rows
n_dst   = n_dst_x * n_dst_y # = 200 destination points

# Cell size of the destination lattice
cdx = float(domain_size_x) / n_dst_x
cdy = float(domain_size_y) / n_dst_y

# Start from cell centres, then add a small jitter (±20 % of cell size)
jitter_frac = 0.20
cx = (np.arange(n_dst_x) + 0.5) * cdx
cy = (np.arange(n_dst_y) + 0.5) * cdy
CX, CY = np.meshgrid(cx, cy)                          # (n_dst_y, n_dst_x)
dst_x = CX.ravel() + np.random.uniform(-jitter_frac * cdx, jitter_frac * cdx, n_dst)
dst_y = CY.ravel() + np.random.uniform(-jitter_frac * cdy, jitter_frac * cdy, n_dst)

# Keep points inside the domain
dst_x = np.clip(dst_x, 0, domain_size_x)
dst_y = np.clip(dst_y, 0, domain_size_y)

# Output path
outputpath = "./"           # current directory – change as needed

###### End user input
#######################################################################

# -----------------------------------------------------------------------
# 1.  Build the source column (x, y) positions
#     DPxx physics columns sit on a regular Cartesian grid.
#     There are (num_ne_x*2) columns in x and (num_ne_y*2) in y.
#     Each column centre is at the midpoint of its cell.
# -----------------------------------------------------------------------
nx_cols = num_ne_x * 2
ny_cols = num_ne_y * 2
phys_col = nx_cols * ny_cols   # = num_ne_x * num_ne_y * 4

dx = float(domain_size_x) / nx_cols
dy = float(domain_size_y) / ny_cols

# Column centres
src_x_1d = (np.arange(nx_cols) + 0.5) * dx   # shape (nx_cols,)
src_y_1d = (np.arange(ny_cols) + 0.5) * dy   # shape (ny_cols,)

# Row-major (C order) meshgrid → flat arrays of length phys_col
SX, SY   = np.meshgrid(src_x_1d, src_y_1d)   # (ny_cols, nx_cols)
src_x    = SX.ravel()                          # shape (phys_col,)
src_y    = SY.ravel()

# -----------------------------------------------------------------------
# 2.  Nearest-neighbour search: for each destination point find the
#     single closest source column.
# -----------------------------------------------------------------------
tree        = cKDTree(np.column_stack([src_x, src_y]))
_, nn_idx   = tree.query(np.column_stack([dst_x, dst_y]))   # shape (n_dst,)

# Sparse matrix entries  (n_s == n_dst for nearest-neighbour)
n_s     = n_dst
S_out   = np.ones(n_s,   dtype=np.float64)           # weight = 1 (NN)
col_out = (nn_idx + 1).astype(np.int32)               # 1-based source index
row_out = (np.arange(n_dst) + 1).astype(np.int32)    # 1-based destination index

# -----------------------------------------------------------------------
# 3.  Write the NetCDF mapping file
# -----------------------------------------------------------------------
current_date   = datetime.now()
formatted_date = current_date.strftime("%Y%m%d")

filename = (
    f"mapping_dpxx_x{domain_size_x}m_y{domain_size_y}m"
    f"_nex{num_ne_x}_ney{num_ne_y}"
    f"_to_unstruct_{n_dst}pts.{formatted_date}.nc"
)
fullfile = os.path.join(outputpath, filename)

if os.path.isfile(fullfile):
    os.remove(fullfile)

f = nc4.Dataset(fullfile, 'w', format='NETCDF4')

f.createDimension('n_s', n_s)
f.createDimension('n_a', phys_col)   # number of source columns
f.createDimension('n_b', n_dst)      # number of destination points

S_var   = f.createVariable('S',   'f8', 'n_s')
col_var = f.createVariable('col', 'i4', 'n_s')
row_var = f.createVariable('row', 'i4', 'n_s')

S_var[:]   = S_out
col_var[:] = col_out
row_var[:] = row_out

# Store destination coordinates as metadata (optional, but helpful)
dst_x_var = f.createVariable('dst_x', 'f8', 'n_b')
dst_y_var = f.createVariable('dst_y', 'f8', 'n_b')
dst_x_var.units = 'm'
dst_y_var.units = 'm'
dst_x_var[:] = dst_x
dst_y_var[:] = dst_y

f.title       = "DPxx nearest-neighbour remap: structured → unstructured (dummy grid)"
f.source_grid = f"DPxx {num_ne_x}x{num_ne_y} elements, {domain_size_x}x{domain_size_y} m domain"
f.dst_grid    = f"Dummy unstructured grid, {n_dst} randomly scattered points"

f.close()

print(f"n_src columns : {phys_col}")
print(f"n_dst points  : {n_dst}")
print(f"n_s entries   : {n_s}")
print(f"Generated file: {fullfile}")
