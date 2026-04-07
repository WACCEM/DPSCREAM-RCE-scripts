# HorizWindsAtHeight Diagnostic — Source Code Changes

**Branch:** `ksa/uvwinds`
**Repository:** `/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM`
**Commits:** `95f983f` → `4b16ca9` → `23b7a49` → `4e39211`

---

## Motivation

The DP-SCREAM simulation `testvar_cpu_dpxx_RCE_dx1km` aborted during
initialization with:

    [p0,r0] ERROR: Error! Field 'U_at_10m_above_Z' not found in any grids.

Two bugs were identified:

1. **Invalid reference surface token**: the literal `Z` in `U_at_10m_above_Z`
   is not a valid token. Valid options are `surface` or `sealevel`.

2. **No scalar U or V field exists**: the existing `FieldAtHeight` diagnostic
   works by splitting on `_at_` to obtain the base field name, yielding `"U"`
   or `"V"`. Neither exists as a registered scalar field. Zonal and meridional
   winds are stored together in `horiz_winds (COL, CMP, LEV)` — a 3-D field
   with component index 0 = U (zonal) and 1 = V (meridional). Additionally,
   `FieldAtHeight` is dispatched via `scorpio_output.cpp` using a simple
   `register_product` lookup by name, not a pattern matcher, so it cannot
   intercept the component extraction automatically.

---

## Source Code Changes

### 1. `diagnostics/horiz_winds_at_height.hpp` *(new)*

Declares the `HorizWindsAtHeight` class, a subclass of `AtmosphereDiagnostic`,
following the same pattern as `FieldAtHeight`.

Key members:

| Member        | Type          | Description                                              |
|---------------|---------------|----------------------------------------------------------|
| `m_diag_name` | `std::string` | Full diagnostic name, e.g. `U_at_10m_above_surface`     |
| `m_z_name`    | `std::string` | `"z"` (sealevel) or `"height"` (above surface)          |
| `m_z_suffix`  | `std::string` | `"_mid"` or `"_int"` (set in `initialize_impl`)         |
| `m_comp_idx`  | `int`         | `0` = U (zonal), `1` = V (meridional)                   |
| `m_z`         | `Real`        | Target height in metres                                  |

Methods (overrides of `AtmosphereDiagnostic`):
`HorizWindsAtHeight(comm, params)`, `set_grids`, `initialize_impl`,
`compute_diagnostic_impl`, `finalize_impl` (no-op).

---

### 2. `diagnostics/horiz_winds_at_height.cpp` *(new)*

**Constructor**: reads parameters set by `scorpio_output.cpp`:
- `wind_component` (int): `0` for U, `1` for V
- `surface_reference` (string): `"surface"` or `"sealevel"` →
  sets `m_z_name` to `"height"` or `"z"` respectively
- `vertical_location` (string): e.g. `"10m"` → parsed to `m_z = 10.0`
- Constructs `m_diag_name` as `U_at_10m_above_surface` (matches the
  requested field name so the output manager can find it)

**`set_grids`**: registers `horiz_winds` and both `{z,height}_mid` /
`{z,height}_int` as Required fields (same pattern as `FieldAtHeight`).

**`initialize_impl`**: determines `m_z_suffix` (`"_mid"` or `"_int"`) from
the layout tag of `horiz_winds`; allocates the scalar `(COL)` output field
by stripping the `CMP` and `LEV`/`ILEV` tags from the layout.

**`compute_diagnostic_impl`**: Kokkos parallel loop over columns using the
same `find_first_smaller_z` binary-search helper as `FieldAtHeight`, then
linear interpolation between bracketing levels:

    alpha = (z_tgt - z0) / (z1 - z0)
    out(i) = f0 + alpha * (f1 - f0)

where `f0`, `f1` are `horiz_winds(i, comp, pos-1)` and
`horiz_winds(i, comp, pos)`.

---

### 3. `diagnostics/register_diagnostics.hpp` *(modified)*

- Added `#include "diagnostics/horiz_winds_at_height.hpp"`
- Added `diag_factory.register_product("HorizWindsAtHeight", &create_atmosphere_diagnostic<HorizWindsAtHeight>)`
  inside `register_diagnostics()`, alongside all other diagnostics.

---

### 4. `diagnostics/CMakeLists.txt` *(modified)*

Added `horiz_winds_at_height.cpp` to the `DIAGNOSTIC_SRCS` list.

---

### 5. `share/io/scorpio_output.cpp` *(modified)*

In `AtmosphereOutput::create_diagnostic()`, the `units=="m"` branch that
previously always set `diag_name = "FieldAtHeight"` now branches on `fname`:

```cpp
if (fname=="U" || fname=="V") {
  diag_name = "HorizWindsAtHeight";
  params.set<int>("wind_component", fname=="U" ? 0 : 1);
} else {
  diag_name = "FieldAtHeight";
}
```

This routes `U_at_Ym_above_Z` and `V_at_Ym_above_Z` requests to the new
diagnostic while leaving all other `X_at_Ym_above_Z` requests unchanged.

---

## Build Fixes (commits `23b7a49`, `4e39211`)

Two additional bugs were introduced by the patch scripts and required separate
fixes before the code compiled successfully.

### Bug 1 — `horiz_winds_at_height.cpp`: stale code after `} //namespace scream`

**Commit:** `23b7a49`

The `replace_string_in_file` operation only matched the first few lines of the
old constructor as the search string, so the remainder of the old
implementation (old constructor body + old `set_grids` + old `run_impl` using
the wrong API) was left dangling after the `} //namespace scream` closing brace
on line 146. The compiler saw member assignments (`m_comp_idx = ...`,
`m_height = ...`) at global scope and reported:

    error: 'm_comp_idx' does not name a type
    error: 'HorizWindsAtHeight' has not been declared
    (30+ cascade errors)

**Fix:** truncated the file to line 146, removing all 96 stale trailing lines.

### Bug 2 — `register_diagnostics.hpp`: missing `} // namespace scream` and `#endif`

**Commit:** `4e39211`

The patch that replaced the stale `dm.register_group(...)` block also dropped
the `} // namespace scream` and `#endif // SCREAM_REGISTER_DIAGNOSTICS_HPP`
lines that followed it in the original file, because the replacement string
only included the function closing brace `}`. The compiler reported:

    error: unterminated #ifndef

**Fix:** appended the missing `} // namespace scream` and
`#endif // SCREAM_REGISTER_DIAGNOSTICS_HPP` to the end of the file, and
removed a stray extra `}` that had also been left behind.

---

## YAML Fix

`run_scripts/yaml_files/scream_output_inst_5min_testvar.yaml`:

```yaml
# Before (causes abort — Z is not a valid surface token)
    - U_at_10m_above_Z
    - V_at_10m_above_Z

# After (correct)
    - U_at_10m_above_surface
    - V_at_10m_above_surface
```

---

## Usage

Any height and reference surface combination is supported:

```yaml
Fields:
  Physics PG2:
    Field Names:
    - U_at_10m_above_surface    # zonal wind at 10 m above surface
    - V_at_10m_above_surface    # meridional wind at 10 m above surface
    - U_at_100m_above_surface   # zonal wind at 100 m above surface
    - V_at_500m_above_sealevel  # meridional wind at 500 m above sea level
```

---

## Run-time error fix: `_horiz_avg` suffix not registered

**Commit:** `007cf6f`

### Error

When running the `scream_cpu_dpxx_RCE_dx1km` case (which uses
`scream_horiz_avg_output_5min.yaml`), the simulation crashed immediately with:

```
The key 'DryStaticEnergy_horiz_avg' is not associated to any registered product.
The list of registered product is: AeroComCld, AerosolOpticalDepth550nm, ..., DryStaticEnergy, ...
```

The `maint-3.0` codebase had no handling for the `_horiz_avg` suffix in
`AtmosphereOutput::create_diagnostic()`, so every `<field>_horiz_avg` name fell
through to the catch-all `else` branch and was looked up verbatim in the factory
— which of course has no entry for `"DryStaticEnergy_horiz_avg"`.

### What `_horiz_avg` means

A field with name `<base>_horiz_avg` should contain the horizontal (column)
average of `<base>`, where the average is taken over **all** columns globally
(across all MPI ranks).  The output field keeps the same grid layout as the
input so that it can be written to the standard output netCDF; every column
holds the same global-mean value.

### Solution — new `FieldHorizAvg` diagnostic

Four source files were changed / created:

#### `src/diagnostics/field_horiz_avg.hpp` *(new)*

Declares `FieldHorizAvgDiagnostic : AtmosphereDiagnostic`.  Key members:
- `m_fname` — base field/diagnostic name (stripped of `_horiz_avg`)
- `m_diag_name` — output diagnostic name (`m_fname + "_horiz_avg"`)
- `m_ncols_global` — total column count across all MPI ranks (set in `initialize_impl`)
- `m_col_sum` — 1-D scratch view of length `nlevs` (or 1 for 2-D fields)

#### `src/diagnostics/field_horiz_avg.cpp` *(new)*

- **Constructor** — reads `field_name` from `m_params`.
- **`set_grids`** — calls `add_field<Required>(m_fname, gname)`.  Because
  `scorpio_output.cpp` recursively creates any required sub-diagnostics, this
  works for both native fields (e.g. `T_mid`) and computed diagnostics (e.g.
  `DryStaticEnergy`, `PotentialTemperature`).
- **`initialize_impl`** — detects 2D `(COL)` vs 3D `(COL,LEV)` layout, computes
  `m_ncols_global` via `MPI_Allreduce(MPI_IN_PLACE, &local_ncols, 1, MPI_INT,
  MPI_SUM, ...)`, allocates the output field with the same layout/units as the
  input.
- **`compute_diagnostic_impl`** — for 3D fields: Kokkos parallel sum over local
  columns per level → host copy → `MPI_Allreduce(MPI_IN_PLACE, ...,
  ekat::get_mpi_type<Real>(), MPI_SUM)` → divide by `m_ncols_global` → broadcast
  to all output columns.  For 2D fields: `Kokkos::parallel_reduce` → same MPI
  pattern.

#### `src/diagnostics/CMakeLists.txt` *(modified)*

Added `field_horiz_avg.cpp` to `DIAGNOSTIC_SRCS` after `horiz_winds_at_height.cpp`.

#### `src/diagnostics/register_diagnostics.hpp` *(modified)*

Added:
```cpp
#include "diagnostics/field_horiz_avg.hpp"
...
diag_factory.register_product("FieldHorizAvg",
    &create_atmosphere_diagnostic<FieldHorizAvgDiagnostic>);
```

#### `src/share/io/scorpio_output.cpp` *(modified)*

Added a new branch in `create_diagnostic()` just before the final `else`:

```cpp
} else if (diag_field_name.size() > 10 &&
           diag_field_name.substr(diag_field_name.size()-10) == "_horiz_avg") {
  const auto base_name = diag_field_name.substr(0, diag_field_name.size()-10);
  params.set<std::string>("field_name", base_name);
  params.set<std::string>("grid_name", get_field_manager("sim")->get_grid()->name());
  diag_name = "FieldHorizAvg";
```

This strips the `_horiz_avg` suffix and forwards the base name to the new
diagnostic.  The existing recursive dependency mechanism in `scorpio_output.cpp`
then automatically creates and chains the underlying diagnostic (e.g.
`DryStaticEnergy`) if it is not already a native field in the field manager.
