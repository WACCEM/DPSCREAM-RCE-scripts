# ESMF Weight-Based Regridding — Changes to `regrid_dpxx_output.py`

## Overview

The `xesmf` branch adds support for regridding DP-SCREAM output from its
unstructured column grid (`ncol`) to a regular lat/lon or Cartesian grid using
a pre-computed ESMF weight file produced by `ESMF_RegridWeightGen`.  The
original coordinate-reshape method is preserved and remains the default.

---

## What Changed

### 1. New import

```python
from scipy.sparse import csr_matrix
```

The ESMF weight matrix is stored as a `scipy.sparse.csr_matrix` so that
sparse matrix–vector products can be used efficiently during regridding.

---

### 2. Two new user-input settings

```python
# Set True to use ESMF weight-based regridding; False keeps the native reshape.
use_esmf_weights = False
weightfile = '/global/cfs/cdirs/wcm_shr/DP-SCREAM/remap/\
DPSCREAM_RCE_dx1km_600x600km_to_PINACLES_YX_dx1km_600x600km_conserve.nc'
```

| Setting | Type | Description |
|---|---|---|
| `use_esmf_weights` | `bool` | Switch between the two regridding paths |
| `weightfile` | `str` | Full path to the `ESMF_RegridWeightGen` output file |

---

### 3. New function: `load_esmf_weights(weightfile)`

Reads the ESMF weight file (SCRIP / NCAR-CSM convention) and returns
everything needed to apply the remapping.

**Reads from the weight file:**

| Variable | Description |
|---|---|
| `col` (n_s,) | 1-indexed source cell indices |
| `row` (n_s,) | 1-indexed destination cell indices |
| `S` (n_s,) | Interpolation weights |
| `dst_grid_dims` (2,) | `[nx, ny]` of the destination grid (Fortran order) |
| `xc_b` (n_b,) | Destination cell-centre x (longitude) in degrees |
| `yc_b` (n_b,) | Destination cell-centre y (latitude) in degrees |

**Returns:**

| Return value | Description |
|---|---|
| `W` | `csr_matrix` of shape `(n_b, n_a)` — the sparse weight matrix |
| `x_out` | 1-D array of destination x coordinates (degrees), length `nx_out` |
| `y_out` | 1-D array of destination y coordinates (degrees), length `ny_out` |
| `nx_out` | Number of destination x points |
| `ny_out` | Number of destination y points |
| `n_a` | Number of source columns (must equal `ncol` in the model output) |

The flat `n_b`-length destination array in the ESMF file uses Fortran
column-major ordering (`x` varies fastest).  The function reshapes it to
`(ny_out, nx_out)` using NumPy C-order, which produces the correct mapping.

---

### 4. New function: `apply_esmf_weights(data, W, ny_out, nx_out)`

Applies the sparse weight matrix to a variable read from a DP-SCREAM output
file.

**Input `data` shapes:**

| Field type | Input shape | Output shape |
|---|---|---|
| 2-D (surface) | `(ntime, ncol)` | `(ntime, ny_out, nx_out)` |
| 3-D (atmospheric column) | `(ntime, ncol, nlev)` | `(ntime, nlev, ny_out, nx_out)` |

For each timestep (and level for 3-D fields) the function computes:

```
out[t, y, x] = sum_k  W[row_k, col_k] * data[t, col_k]
```

via a sparse matrix–vector product: `W.dot(data[t])`.

**Note on dimension ordering for 3-D fields:**
The output shape `(ntime, nlev, ny_out, nx_out)` places the vertical dimension
before the horizontal spatial dimensions.  This is **not** a new behaviour
introduced by the ESMF path — the original `regrid_array` function already
performed the same reordering via `.transpose(0, 2, 1)`, converting the model's
`(time, ncol, lev)` storage to `(time, lev, y, x)` in the output file.
Both methods produce identical dimension ordering for two reasons:

1. **Implementation convenience:** the sparse matrix–vector product
   `W.dot(data[t, :, k])` naturally operates over all columns for a single
   level `k`, making looping over levels the straightforward approach and
   resulting in a `(time, lev, y, x)` layout.
2. **CF / NetCDF convention:** placing the vertical dimension before the
   horizontal spatial dimensions (`time, lev, lat, lon`) is the standard for
   4-D atmospheric data, making level slicing simple and compatible with
   common analysis tools.

---

### 5. Changes to the main processing loop

**Grid initialisation** (after reading the first file's coordinates):

- If `use_esmf_weights=True`: calls `load_esmf_weights()` to obtain the
  destination grid.  A sanity check raises `ValueError` if the number of
  source columns in the weight file does not match `ncol` in the model output.
- If `use_esmf_weights=False`: original behaviour — `sorted(set(...))` is used
  to recover the unique x and y coordinates from the native mesh.

**Per-variable regridding** (inside the file loop):

- If `use_esmf_weights=True`: calls `apply_esmf_weights(var, W_esmf, ny_esmf, nx_esmf)`.
- If `use_esmf_weights=False`: calls the original `regrid_array(var, crm_grid_x, crm_grid_y)`.

**Output coordinate metadata:**

| Mode | `x.units` | `x.long_name` | `y.units` | `y.long_name` |
|---|---|---|---|---|
| ESMF weights | `degrees_east` | `longitude` | `degrees_north` | `latitude` |
| Native reshape | `m` | `x coordinate` | `m` | `y coordinate` |

---

## How to Use

1. Generate a weight file with `ESMF_RegridWeightGen` mapping from the
   DP-SCREAM source SCRIP grid file to the desired destination SCRIP grid file.

2. Set `use_esmf_weights = True` and point `weightfile` to that file in the
   user input section of `regrid_dpxx_output.py`.

3. Run the script as usual.  Output dimensions and coordinates will reflect
   the destination grid defined in the weight file.

### Example weight file used during development

```
/global/cfs/cdirs/wcm_shr/DP-SCREAM/remap/
    DPSCREAM_RCE_dx1km_600x600km_to_PINACLES_YX_dx1km_600x600km_conserve.nc
```

This file was generated with first-order conservative remapping
(`ESMF_regrid_method = First-order Conservative`) from the DP-SCREAM RCE
600 × 600 km, 1 km resolution mesh (160 000 columns) to a regular 600 × 600
destination grid (360 000 points, 813 600 non-zero weights).

---
Files prepared by Naser
grid generation, plotting, etc. should be here: 
`/pscratch/sd/m/mahf708/scmlib/DPxx_SCREAM_SCRIPTS/regrid_utilities`

script to run: `/pscratch/sd/m/mahf708/scmlib/DPxx_SCREAM_SCRIPTS/run_dpxx_scream_RCE.csh`

case (with multiple realizations, etc.): `/pscratch/sd/m/mahf708/e3sm-scratch/doublyperiodicremap/scream_dpxx_RCE_300K/`


---

## Dependencies

No new external packages are required beyond what was already used.
`scipy.sparse` is part of the `scipy` package already imported by the script.
