# Online Horizontal Remapping in EAMxx

## Original documentation in model_configuration.md on "Remapped output"

"The following options can be used to to save fields on a different grid from
the one they are computed on.

- `horiz_remap_file`: a path to a map file (as produced by `ncremap`) between
the grid where the fields are defined and a coarser grid.
      - EAMxx will use this to remap fields on the fly, allowing to reduce
      the size of the output file.
          - **Note:** with this feature, the user can only specify fields
          from a single grid."

## Question
Is the option for the EAMxx component, `horiz_remap_file` (set in an input yaml file), fully functional in the `v3.0.2` version of the code (`/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM/components/eamxx`)? How is the file specified by the `horiz_remap_file` option being used?

## Answer
Based on a detailed check of the EAMxx source code in `/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM/components/eamxx` (the `ksa/uvwinds` branch), the `horiz_remap_file` option is technically implemented but **not fully functional** for standard workflows because it outputs a flattened 1D array instead of a 2D lat/lon grid.

Here is exactly how the file specified by `horiz_remap_file` is currently being parsed and used:

1. **Parameter Parsing:** In `src/share/io/scorpio_output.cpp`, the code reads the `horiz_remap_file` option from the YAML file and instantiates a `CoarseningRemapper`.
2. **Reading the Map File:** In `src/share/grid/remap/horiz_interp_remapper_data.cpp`, the code uses Scorpio (the IO library) to open the map file (which is expected to be an `ncremap` generated mapping file) and reads the sparse matrix triplets:
   - `"col"` (source grid indices)
   - `"row"` (target grid indices)
   - `"S"` (the interpolation weights)
3. **The Flaw (Why it's not fully functional):** When building the target "coarse" grid to hold the remapped data, the code hardcodes the instantiation of a `PointGrid`:
   ```cpp
   // From horiz_interp_remapper_data.cpp
   coarse_grid = std::make_shared<PointGrid>("coarse_grid",num_gids,0,comm);
   ```
   A `PointGrid` is a 1D unstructured grid. So while the code successfully performs the sparse matrix-vector multiplication to mathematically remap the data to the new grid points, it treats the resulting coarse grid as a flat list of points (`ncol` dimension). 
4. **The Result:** The output netCDF file will contain the remapped data, but it will be structured with a 1D horizontal dimension (like `ncol = 1036800`) instead of the expected 2D structured layout (like `lat x lon`). This makes it extremely difficult to plot or analyze with standard tools that expect regular gridded data.

**Why `ksa/regrid_fix` was created:**
In the simulation directory's `ksa/regrid_fix` branch, new files named `structured_column_grid.cpp` and `.hpp` were introduced, along with modifications to `coarsening_remapper.cpp`. This confirms that the `regrid_fix` branch was specifically created to fix this exact issue—allowing the remapper to understand that the target grid is a 2D structured lat/lon grid rather than a 1D `PointGrid`, so that the output files have the correct `lat` and `lon` dimensions.

## Investigation of Newer Version (`8426cb31c7_clone`)

A subsequent investigation was carried out on the code located in `/global/cfs/cdirs/wcm_code/ksa/E3SM/code_tests/8426cb31c7_clone/components/eamxx/`. 

The implementation in this slightly newer clone behaves **exactly the same** as the `v3.0.2` baseline. 
- It still parses `horiz_remap_file` and extracts the `"row"`, `"col"`, and `"S"` variables.
- In `src/share/grid/remap/horiz_interp_remapper_data.cpp`, the `create_coarse_grids` function still hardcodes the instantiation of the target grid as a `PointGrid`.
- Consequently, this version suffers from the exact same limitation: it will perform the mathematical remapping successfully but will output the data flattened into a 1D `ncol` dimension rather than a proper 2D `lat x lon` grid.

It does **not** include the `structured_column_grid` enhancements found in the `ksa/regrid_fix` branch, meaning it remains not fully functional for generating standard 2D gridded output.

## Does `io_latlon.cpp` output on a 2D grid?

Based on a review of the `io_latlon.cpp` test file from the E3SM master branch (`components/eamxx/src/share/io/tests/io_latlon.cpp`), **no, this currently available code still does not output on a 2D grid.**

Here is what that specific test file is actually doing:

1. **It still uses a 1D PointGrid:** The test calls `create_point_grid(name, ncols, 1, comm, 1);`. This explicitly creates a 1D unstructured grid of length `ncols`.
2. **What the test is actually checking:** The test creates two fake variables called `f_lat` and `f_lon` (populated using the `lat` and `lon` coordinates from the mapping file) and tests if the `horiz_remap_file` feature can successfully remap these fields from the fine grid to the coarse grid. 
3. **The output structure:** Because the target grid is still hardcoded as a `PointGrid`, the variables written to the resulting NetCDF file will still have the dimensions `(time, ncol, lev)`. It does not construct a `(lat, lon)` structured grid.

So while the test file is named `io_latlon.cpp`, it is not outputting a structured 2D lat/lon grid. It is simply testing the remapper's ability to interpolate variables (which happen to be latitude and longitude values in this specific test) onto a coarser 1D unstructured `PointGrid`. 

To get true 2D structured output `(time, lat, lon, lev)`, the modifications introduced in the `ksa/regrid_fix` branch (specifically the `structured_column_grid` classes) are still absolutely necessary.
