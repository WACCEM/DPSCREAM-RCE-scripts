# DP-SCREAM Failure: `horiz_remap_file` in Output YAML Crashes at Init

**Date:** 2026-03-13  
**Job ID:** 50033719  
**Case:** `debug_regrid_cpu_dpxx_RCE_dx1km`  
**Run dir:** `/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/debug_regrid_cpu_dpxx_RCE_dx1km/run`  

---

## Symptom

All 1024 MPI ranks crash simultaneously with `SIGSEGV` during model initialization,
before any time steps are taken. The log `e3sm.log.50033719.260313-114651` shows no
explicit error message — only `Program received signal SIGSEGV: Segmentation fault -
invalid memory reference` prefixed by every rank.

---

## Root Cause

### Triggering configuration

The output YAML file `scream_output_inst_5min_debug.yaml` contains:

```yaml
horiz_remap_file: "/global/cfs/cdirs/wcm_shr/DP-SCREAM/remap/DPSCREAM_RCE_dx1km_600x600km_to_PINACLES_YX_dx1km_600x600km_conserve.nc"
```

This causes SCREAM to construct a `CoarseningRemapper` during output manager
initialization (`initialize_output_managers`).

### Call chain (from rank 3 backtrace)

```
scream_init_atm  (scream_cxx_f90_interface.cpp:249)
  → AtmosphereDriver::initialize_output_managers  (atmosphere_driver.cpp:748)
    → OutputManager::setup  (scream_output_manager.cpp:110)
      → AtmosphereOutput::AtmosphereOutput  (scorpio_output.cpp:286)
        → make_shared<CoarseningRemapper>(io_grid, horiz_remap_file, true)
          → CoarseningRemapper constructor  (coarsening_remapper.cpp:40)  ← CRASH
```

### What goes wrong

When running in planar (IOP/DP) geometry, `HommeGridsManager` registers a
**0-dimensional scalar** geometry data field called `dx_short` on the Physics PG2
grid:

```cpp
// homme_grids_manager.cpp ~L293
FieldLayout scalar0d({},{});   // empty tags, zero dimensions
phys_grid->create_geometry_data("dx_short", scalar0d, rad);
```

The `CoarseningRemapper` constructor iterates over all geometry data fields of the
source grid and at line 40 does:

```cpp
// coarsening_remapper.cpp:40
if (layout.tags()[0] != COL) {
```

For `dx_short`, `layout.tags()` is an **empty vector**. Accessing `[0]` on an empty
vector is undefined behavior → `SIGSEGV` on every rank.

This is a bug in the SCREAM source: the constructor does not guard against
0-dimensional (scalar) geometry data fields, which only exist in planar/IOP mode.
The bug does not surface in standard spherical-grid runs because no scalar geometry
data is registered there.

---

## Affected Source Files

| File | Line | Description |
|------|------|-------------|
| `components/eamxx/src/share/grid/remap/coarsening_remapper.cpp` | 40 | Missing bounds check on `layout.tags()` |
| `components/eamxx/src/dynamics/homme/homme_grids_manager.cpp` | ~293 | Registers `dx_short` as 0D scalar (IOP/planar mode only) |

---

## Fix Options

### Option A — Source code fix (requires rebuild)

Edit `coarsening_remapper.cpp` line 40 to guard against empty layouts:

```cpp
// Before:
if (layout.tags()[0] != COL) {

// After:
if (layout.tags().empty() || layout.tags()[0] != COL) {
```

For a 0D scalar like `dx_short`, this takes the "not a field to remap" branch and
simply copies the scalar to the target grid — which is the correct behavior.

### Option B — Immediate workaround (no rebuild needed)

Remove (or comment out) the `horiz_remap_file` line from the output YAML file.
This skips the `CoarseningRemapper` entirely and writes output on the native model
grid.

```yaml
# horiz_remap_file: "..."   ← comment out or delete
```

Note: with this workaround, output fields will be on the native DP-SCREAM PG2 grid
rather than the remapped target grid.

---

## Notes

- The remap file itself (`DPSCREAM_RCE_dx1km_600x600km_to_PINACLES_YX_dx1km_600x600km_conserve.nc`, 63 MB) is valid and readable — the crash occurs before it is even opened.
- This bug is specific to planar/IOP geometry runs; it does not affect standard global SCREAM simulations.
- A related first failure (`nminutes` vs `nmins` unit mismatch) was also encountered in this testing and is a separate issue — see the comments in the run script.

---

---

# Issue 2: Regridded Output Has `ncol` Instead of `lat`/`lon` Dimensions

**Date:** 2026-03-15  
**Job ID:** 50040352  
**Case:** `debug02_regrid_cpu_dpxx_RCE_dx1km`  
**Run dir:** `/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/debug02_regrid_cpu_dpxx_RCE_dx1km/run`  
**Branch:** `ksa/regrid_fix` (commit `dc86c9a`)  
**Run script:** `debug02_cpu_dpxx_scream_RCE_dx1km.sh`  

---

## Symptom

After applying the Issue 1 fix (the `.empty()` guard in `coarsening_remapper.cpp`),
the simulation completes successfully and produces output file:

```
debug02_regrid_cpu_dpxx_RCE_dx1km.hist.INSTANT.nmins_x5.2000-01-01-00000.nc
```

However, all output variables have the spatial dimension `ncol = 360000` instead of
the expected structured `lat = 600, lon = 600` dimensions found in the post-processed
reference file:

```
scream_gpu_dpxx_RCE_dx1km.fullfield.AVERAGE.nhours_x1.2000-01-01-00000_PINACLES_YX_dx1km_600x600km.nc
```

The remap file encodes a 2D destination grid (`dst_grid_rank=2`, `dst_grid_dims=600,600`),
but the model output is flat 1D (`ncol`).

---

## Root Cause

The Issue 1 fix is correct and the remapping computation itself works: field values
are correctly interpolated onto the 360,000 PINACLES target points (`n_b = 360000`
in the remap file). But there is a **second, independent bug**: the `CoarseningRemapper`
always constructs its target grid as a `PointGrid`, which is an unstructured 1D grid
whose only spatial dimension is `COL` (written as `"ncol"` in NetCDF output).

### The remap file contains 2D target grid metadata — which is never read

The remap weights file holds:
```
dst_grid_rank = 2
dst_grid_dims = 600, 600     ← PINACLES 600×600 lat/lon grid
```

This is written by ESMF/TempestRemap and is the same information that `ncks` uses
when post-processing to produce `lat=600, lon=600` output dimensions. **SCREAM's
remapper never reads these variables.**

### Call chain

In `scorpio_output.cpp` (~line 286):
```cpp
m_horiz_remapper = std::make_shared<CoarseningRemapper>(io_grid, horiz_remap_file, true);
io_grid = m_horiz_remapper->get_tgt_grid();   // ← always a PointGrid
set_grid(io_grid);
```

`get_tgt_grid()` returns the `coarse_grid` built in `HorizRemapperData::create_coarse_grids()`
(`horiz_interp_remapper_data.cpp`, ~line 195):
```cpp
coarse_grid = std::make_shared<PointGrid>("coarse_grid", num_gids, 0, comm);
```

`PointGrid::get_2d_scalar_layout()` always returns `FieldLayout({COL}, {num_local_dofs})`.
The output writer then uses this layout for all field dimensions, producing `(time, ncol)`
regardless of the true 2D structure of the target grid.

---

## Affected Source Files

| File | Line | Description |
|------|------|-------------|
| `components/eamxx/src/share/grid/remap/horiz_interp_remapper_data.cpp` | ~195 | `create_coarse_grids()` always constructs a flat `PointGrid`, ignoring `dst_grid_dims` |
| `components/eamxx/src/share/grid/point_grid.cpp` | ~50 | `get_2d_scalar_layout()` always returns `{COL}` layout |

---

## What a Fix Would Require

`HorizRemapperData::create_coarse_grids()` (or `get_my_triplets()`) in
`horiz_interp_remapper_data.cpp` would need to:

1. Read `dst_grid_rank` and `dst_grid_dims` from the remap file when
   `type == InterpType::Coarsen`.
2. If `dst_grid_rank == 2`, either:
   - Set **special tag names** on the `coarse_grid` so that the `COL` dimension is
     renamed to `"lat"` × `"lon"` in output (using `m_special_tag_names` in `PointGrid`), or
   - Construct a dedicated structured 2D grid subclass.

Without this change, the online coarsening remapper will always produce flat-`ncol`
output for any target grid, including a regular lat/lon grid.

---

## Workaround

Continue post-processing with `ncks` (as done for the reference file). Online
regridding in SCREAM currently produces correct *values* on the target points but
does not reshape the output into the 2D lat/lon structure. The `ncks`-based workflow
correctly reads `dst_grid_dims` and produces `(lat=600, lon=600)` output.

