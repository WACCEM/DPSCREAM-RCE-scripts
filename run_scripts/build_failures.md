# DP-SCREAM Build Failure Notes

## E3SM Source Code Information

| Item | Value |
|------|-------|
| Source path | `/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM` |
| Git branch | `ksa/uvwinds` (also pushed to `waccem/ksa/uvwinds`) |
| Base version tag | `v3.0.2-76-g584f836960` (76 commits ahead of v3.0.2) |
| HEAD commit | `584f836960` — *Fix output manager crash on restart when last output file is full* (2026-03-16) |
| Origin remote | `git@github.com:E3SM-Project/E3SM.git` |

The `ksa/uvwinds` branch is a local development branch adding `HorizWindsAtHeight` and `FieldHorizAvg` diagnostics on top of E3SM v3.0.2.

---

## Prerequisites for Running CIME Build Scripts

**Neither the E3SM unified environment nor a Python module needs to be loaded before running the CIME build scripts.**

### E3SM unified environment — do NOT load it for building

Sourcing `/global/common/software/e3sm/anaconda_envs/load_latest_e3sm_unified_pm-cpu.sh` will
**break** the build. That script intentionally sets:

```bash
export CIME_MODEL="ENVIRONMENT_RUNNING_E3SM_UNIFIED_USE_ANOTHER_TERMINAL"
```

This overrides the required `export CIME_MODEL=e3sm` and causes CIME to fail immediately.
The unified environment is intended only for post-processing and analysis tools (NCO,
`e3sm_diags`, etc.) — not for compiling the model. The run script comment at line 4 is
correct: source it **outside** this script in a separate terminal if needed for analysis.

### Python module — not needed

All CIME scripts (`case.build`, `case.setup`, `atmchange`, `create_newcase`, etc.) use
`#!/usr/bin/env python3`, which resolves to the system `/usr/bin/python3` (Python 3.6.15
on Perlmutter). This is sufficient:

- `case.build --help` and `atmchange --help` both run correctly with no Python module loaded.
- CIME uses f-strings (available since Python 3.6) but no Python 3.8+ syntax.
- `import CIME` succeeds under Python 3.6.15.

Loading a Python module (e.g. `python/3.13-26.1.0` or `cray-python/3.11.7`) is unnecessary
and may introduce unexpected environment changes. Simply run the build script with the
default Perlmutter login environment (plus the `cmake/3.30.2` fix described below).

---

## Build Failure: `CUDA::cudart_static_deps` not found during CMake Generate

**Date**: 2026-04-14  
**Machine**: Perlmutter GPU (`pm-gpu`), NERSC  
**Compiler setting**: `gnugpu`  
**Run script**: `run_RCE01_dx1km_gpu_branch.sh`

### Symptom

The CMake Generate step failed with the following error in
`/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE01_dx1km_gpu_branch/build/e3sm.bldlog.*`:

```
CMake Error at .../KokkosConfig.cmake:41 (SET_TARGET_PROPERTIES):
  The link interface of target "CUDA::cudart" contains:
    CUDA::cudart_static_deps
  but the target was not found.
...
CMake Generate step failed.  Build files cannot be regenerated correctly.
```

This failure occurred every time, even with a clean build (`case.build --clean-all`).

### Root Cause (two-level)

**Level 1 — Wrong CMake version used for the main E3SM build**

The `config_machines.xml` for `pm-gpu` specifies `cmake/3.30.2`, but the build
was actually using `/usr/bin/cmake` (version 3.28.3).

In CMake ≥ 3.30, `FindCUDAToolkit` creates CUDA imported targets (including
`CUDA::cudart_static_deps`) as **GLOBAL** targets, visible across all CMake
subdirectory scopes.  In CMake 3.28, those targets are **directory-scoped**,
so when `KokkosConfig.cmake` references `CUDA::cudart_static_deps` at the
top-level Generate step, the target is not visible — causing the error.

(Note: Kokkos itself was built correctly with cmake 3.30.2 via its own
`buildlib.kokkos` script, which is why its `KokkosConfig.cmake` exports a
reference to `CUDA::cudart_static_deps` in the first place.)

**Level 2 — Why `cmake/3.30.2` was not loaded (the actual bug)**

CIME's Python module loader (`env_mach_specific.py`, method
`_load_module_modules`) batches all consecutive `load` commands from all
`<modules>` blocks into a single `lmod python load` call, for efficiency.
The final batch for `pm-gpu`/`gnugpu` was:

```
lmod python load  cray-libsci/24.07.0  craype/2.7.32  cray-mpich/8.1.30 \
                  cray-hdf5-parallel/1.12.2.9  cray-netcdf-hdf5parallel/4.9.0.9 \
                  cray-parallel-netcdf/1.12.3.9  cmake/3.30.2
```

When the default login environment has `cpe/25.09` loaded, the earlier
`module unload cpe` step fails to cleanly restore system defaults (as lmod
itself warns: *"Unloading the cpe module is insufficient to restore the system
defaults"*). As a result, `cray-hdf5` remains loaded, and loading
`cray-hdf5-parallel/1.12.2.9` in the same batch raises a conflict error.
When **any** module in a batch fails, **lmod returns no output** (0 useful
bytes of Python code), so `os.environ['PATH']` is never updated for the entire
batch — including `cmake/3.30.2`. The build process then falls back to
`/usr/bin/cmake` (3.28.3).

This can be confirmed:
```bash
# Returns ~16 KB of Python code (PATH updated correctly):
/usr/share/lmod/lmod/libexec/lmod python load cmake/3.30.2 | wc -c

# Returns only ~18 bytes (no PATH update — batch silently failed):
/usr/share/lmod/lmod/libexec/lmod python load cray-hdf5-parallel/1.12.2.9 cmake/3.30.2 | wc -c
```

### Fix

Move `cmake/3.30.2` into its own isolated `<modules>` block in
`config_machines.xml`, separated by an `unload cmake` command. Since CIME
cannot batch an `unload` together with a `load`, cmake is forced into an
independent `lmod python` call that succeeds regardless of other module
conflicts.

**File changed**: `/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM/cime_config/machines/config_machines.xml`

```xml
<!-- BEFORE (cmake batched with potentially failing modules): -->
<modules>
  <command name="load">cray-libsci/24.07.0</command>
  <command name="load">craype/2.7.32</command>
  <command name="load">cray-mpich/8.1.30</command>
  <command name="load">cray-hdf5-parallel/1.12.2.9</command>
  <command name="load">cray-netcdf-hdf5parallel/4.9.0.9</command>
  <command name="load">cray-parallel-netcdf/1.12.3.9</command>
  <command name="load">cmake/3.30.2</command>
</modules>

<!-- AFTER (cmake isolated in its own block): -->
<modules>
  <command name="load">cray-libsci/24.07.0</command>
  <command name="load">craype/2.7.32</command>
  <command name="load">cray-mpich/8.1.30</command>
  <command name="load">cray-hdf5-parallel/1.12.2.9</command>
  <command name="load">cray-netcdf-hdf5parallel/4.9.0.9</command>
  <command name="load">cray-parallel-netcdf/1.12.3.9</command>
</modules>
<modules>
  <command name="unload">cmake</command>
  <command name="load">cmake/3.30.2</command>
</modules>
```

The same change was also applied to the case-level
`env_mach_specific.xml` (which is regenerated from `config_machines.xml`
by `case.setup`), so an existing case can be fixed without recreating it:

**File changed**: `/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE01_dx1km_gpu_branch/case_scripts/env_mach_specific.xml`

After editing, run `./case.setup` from the case scripts directory to regenerate
`.env_mach_specific.sh`. Verify the fix:

```bash
grep "cmake" /pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE01_dx1km_gpu_branch/case_scripts/.env_mach_specific.sh
# Expected output:
# module unload cmake
# module load cmake/3.30.2
```

### Notes

- This issue is specific to the `cpe/25.09` environment on Perlmutter (active
  as of April 2026). Earlier CPE versions did not leave `cray-hdf5` in a
  conflicting state after unloading `cpe`.
- The fix in `config_machines.xml` is permanent for all future cases created
  with this E3SM checkout. Any existing cases need their `env_mach_specific.xml`
  patched separately (or regenerated via `case.setup`).
- Kokkos itself was not the source of the error — it was built correctly with
  cmake 3.30.2 (via its own dedicated `buildlib.kokkos` script that uses the
  full cmake path, not `PATH`-resolved cmake).

---

## Build Failure: `CUDA::cudart_static_deps` not found — second occurrence (different root cause)

**Date**: 2026-04-16  
**Same symptom as above**, but `CMakeCache.txt` now confirmed cmake 3.30.2 was
actually being used. The cmake version fix was working — this was a different bug.

### Root Cause

`find_dep_packages.cmake` calls `find_package(Kokkos REQUIRED)` at line 31.
`KokkosConfig.cmake` (the pre-built Kokkos export file) unconditionally creates
`CUDA::cudart` as an imported target and sets:

```cmake
INTERFACE_LINK_LIBRARIES "CUDA::cudart_static_deps"
```

`CUDA::cudart_static_deps` is an interface target defined by `FindCUDAToolkit.cmake`.
However, `find_package(CUDAToolkit)` was only called later, deep inside a
subdirectory (e.g., `eamxx/src/physics/rrtmgp/CMakeLists.txt`). At CMake Generate
time, cmake validates all link interface targets globally and fails because
`CUDA::cudart_static_deps` was never created at the top-level scope before
`find_package(Kokkos)` ran.

Verified from `CMakeCache.txt`:
```
CMAKE_COMMAND:INTERNAL=/global/common/software/nersc9/cmake/3.30.2-.../bin/cmake
```

### Fix

Add `find_package(CUDAToolkit REQUIRED)` before `find_package(Kokkos REQUIRED)` in
`find_dep_packages.cmake`. This ensures all `CUDA::*` targets (including
`CUDA::cudart_static_deps`) are defined as global targets before Kokkos reads them.
As a side effect, `KokkosConfig.cmake`'s `IF(NOT TARGET CUDA::cudart)` block is
skipped entirely (since `CUDA::cudart` already exists), eliminating the problematic
reference.

**File changed**: `/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM/components/cmake/find_dep_packages.cmake`

```cmake
elseif (USE_KOKKOS)
  if (NOT DEFINED ENV{Kokkos_ROOT})
    set(ENV{Kokkos_ROOT} ${INSTALL_SHAREDPATH})
  endif()
  # Find CUDAToolkit before Kokkos so that CUDA:: targets (including
  # CUDA::cudart_static_deps) are defined globally before KokkosConfig.cmake
  # references them in INTERFACE_LINK_LIBRARIES, avoiding a CMake generate error.
  if (USE_CUDA)
    find_package(CUDAToolkit REQUIRED)
  endif()
  find_package(Kokkos REQUIRED)
endif()
```

After applying this fix, also delete the stale cmake build directory:
```bash
rm -rf /pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE01_dx1km_gpu_branch/build/cmake-bld
```
Then re-run `./case.build` from the case scripts directory.

---

## Build Failure: `rrtmgp_constants` members undefined in device code

**Date**: 2026-04-16  
**Machine**: Perlmutter GPU (`pm-gpu`), NERSC  
**Error** (in `e3sm.bldlog.260416-114712`):

```
mo_gas_optics_rrtmgp.h(1142): error: identifier "rrtmgp_constants<double> ::m_dry" is undefined in device code
mo_gas_optics_rrtmgp.h(1131): error: identifier "rrtmgp_constants<double> ::grav" is undefined in device code
2 errors in compilation of ".../eam/src/physics/rrtmgp/external/cpp/examples/mo_load_coefficients.cpp"
```

### Root Cause

In `mo_gas_optics_rrtmgp.h`, the function `get_col_dry` uses `YAKL_SCOPE` to
capture `rrtmgp_constants<real>::grav` and `rrtmgp_constants<real>::m_dry` for use
inside GPU kernels:

```cpp
YAKL_SCOPE( grav , const_t::grav );
// ...kernel using grav...
YAKL_SCOPE( m_dry , const_t::m_dry );
```

`YAKL_SCOPE(a,b)` expands to `auto &a = b` — a **reference**. `grav` and `m_dry`
are declared as `static inline RealT` (non-`constexpr`) members of the struct, so
they live in host memory. CUDA 12.4 (HPC SDK 24.5) refuses to capture a reference
to a host-side static variable in device (GPU) code. The `constexpr` members `m_h2o`,
`avogad`, etc. work correctly because they are inlined by the compiler.

Note: An equivalent template specialization of the same function (lines ~2301/2309)
already used a value-copy pattern (`const auto grav = const_t::grav`) correctly.

### Fix

Replace the two `YAKL_SCOPE` calls with `const auto` value copies, matching the
working template-version pattern:

**File changed**: `/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM/components/eam/src/physics/rrtmgp/external/cpp/rrtmgp/mo_gas_optics_rrtmgp.h`

```cpp
// BEFORE:
YAKL_SCOPE( grav , const_t::grav );
// ...
YAKL_SCOPE( m_dry , const_t::m_dry );

// AFTER:
const auto grav = const_t::grav;
// ...
const auto m_dry = const_t::m_dry;
```

No cmake cache invalidation is required — only the one translation unit
(`mo_load_coefficients.cpp.o`) needs to recompile.

---

## Build Failure: extended lambda in protected member function (GPU build)

**Date**: 2026-04-16  
**Machine**: Perlmutter GPU (`pm-gpu`), NERSC  
**Error** (in `e3sm.bldlog.260416-121201`):

```
field_horiz_avg.cpp(74): error: The enclosing parent function ("compute_diagnostic_impl")
for an extended __host__ __device__ lambda cannot have private or protected access
within its class
```

### Root Cause

`KOKKOS_LAMBDA` expands to a `__host__ __device__` extended lambda when compiling for
CUDA (with `-extended-lambda`). CUDA requires that any function containing such a
lambda must have **public** access in its class. `compute_diagnostic_impl` is declared
in the `protected` section of both `AtmosphereDiagnostic` (base class) and
`FieldHorizAvgDiagnostic` (derived class), which CUDA rejects.

This is a known SCREAM pattern: the identical issue was already solved in the
companion `HorizWindsAtHeight` diagnostic (also in the `ksa/uvwinds` branch) by
using a `#ifdef KOKKOS_ENABLE_CUDA` guard.

### Fix

Add the `#ifdef KOKKOS_ENABLE_CUDA / public:` guard in the `FieldHorizAvgDiagnostic`
header, exactly matching the pattern used in `horiz_winds_at_height.hpp`:

**File changed**: `/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM/components/eamxx/src/diagnostics/field_horiz_avg.hpp`

```cpp
// BEFORE:
protected:
  void initialize_impl (const RunType run_type);
  void compute_diagnostic_impl ();

// AFTER:
protected:
  void initialize_impl (const RunType run_type);
#ifdef KOKKOS_ENABLE_CUDA
public:
#endif
  void compute_diagnostic_impl ();
protected:
```

This promotes `compute_diagnostic_impl` to `public` only in GPU (CUDA) builds,
satisfying the CUDA extended-lambda restriction while keeping the intended
`protected` access in CPU-only builds.

---

## Summary of all fixes required for a successful GPU build (as of 2026-04-16)

| # | File | Change | Reason |
|---|------|--------|--------|
| 1 | `cime_config/machines/config_machines.xml` | Split `cmake/3.30.2` into isolated `<modules>` block with preceding `unload cmake` | lmod batch failure silently dropped the entire load batch including cmake |
| 2 | `cime_config/machines/config_machines.xml` | Added `<env name="PATH">/global/common/software/nersc9/cmake/3.30.2/bin:$ENV{PATH}</env>` in `gnugpu` environment block | Belt-and-suspenders: directly prepend cmake 3.30.2 to PATH regardless of module loading |
| 3 | `components/cmake/find_dep_packages.cmake` | Added `find_package(CUDAToolkit REQUIRED)` before `find_package(Kokkos REQUIRED)` (inside `USE_KOKKOS` + `USE_CUDA` block) | `KokkosConfig.cmake` references `CUDA::cudart_static_deps` which only exists after `FindCUDAToolkit` runs |
| 4 | `components/eam/src/physics/rrtmgp/external/cpp/rrtmgp/mo_gas_optics_rrtmgp.h` | Replaced `YAKL_SCOPE(grav, …)` and `YAKL_SCOPE(m_dry, …)` with `const auto` value copies | `YAKL_SCOPE` creates a reference; `static inline` non-`constexpr` host members cannot be referenced in CUDA device code |
| 5 | `components/eamxx/src/diagnostics/field_horiz_avg.hpp` | Added `#ifdef KOKKOS_ENABLE_CUDA / public:` guard around `compute_diagnostic_impl` | CUDA extended lambdas (`KOKKOS_LAMBDA`) cannot be inside `protected` member functions |

Files 1–2 are in the CIME machine config (persistent for all future cases from this checkout).  
Files 3–5 are in the E3SM/SCREAM source tree on branch `ksa/uvwinds`.

---

## EAMxx Output YAML File Syntax Change Between v3.0.2 and v3.1.0-alpha

**Date**: 2026-05-12  
**Older code**: `/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM` (branch `ksa/uvwinds`, based on `v3.0.2`)  
**Newer code**: `/global/cfs/cdirs/wcm_code/ksa/E3SM/code_tests/8426cb31c7_clone` (commit `8426cb31c7`, tag `v3.1.0-alpha-3683-g8426cb31c7`)

### Background

The output YAML files passed to EAMxx via `atmchange output_yaml_files=...` use
keys that the CIME build script (`eamxx_buildnml.py`) reads directly as Python
dictionary keys. Between v3.0.2 and v3.1.0-alpha the expected key names changed
from Title Case with spaces to lowercase with underscores. Using the old-style
keys with the new code causes a `KeyError` during `case.build` (in
`do_cime_vars_on_yaml_output_files`).

### Key Name Changes

| Old syntax (v3.0.2) | New syntax (v3.1.0-alpha) |
|---------------------|--------------------------|
| `Averaging Type: Average` | `averaging_type: average` |
| `Averaging Type: Instant` | `averaging_type: instant` |
| `Max Snapshots Per File: N` | `max_snapshots_per_file: N` |
| `Fields:` | `fields:` |
| `Physics PG2:` | `physics_pg2:` |
| `Field Names:` | `field_names:` |
| `Frequency: N` (under `output_control`) | `frequency: N` |

The `filename_prefix`, `output_control`, and `frequency_units` keys are
unchanged between versions.

### Convention for YAML Files in This Repository

YAML files in `run_scripts/yaml_files/` are named to indicate the target version:

- Files **without** a version qualifier (e.g., `scream_output_avg_1hour.yaml`,
  `scream_test_output_avg_1hour.yaml`) use the **old Title Case syntax** and are
  intended for the v3.0.2-based code in `/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM`.
- Files prefixed with `scream_new_` or `scream_test2_` (e.g.,
  `scream_new_output_avg_5min.yaml`, `scream_test2_output_avg_1hour.yaml`,
  `scream_test2_output_inst_1hour.yaml`) use the **new lowercase syntax** and are
  intended for the v3.1.0-alpha code in
  `/global/cfs/cdirs/wcm_code/ksa/E3SM/code_tests/8426cb31c7_clone`.

### Error Triggered by Mismatch

Using old-style `Frequency:` (capital F) with the v3.1.0-alpha `buildnml` produces:

```
KeyError: 'frequency'
  File ".../eamxx_buildnml.py", line 1149, in do_cime_vars_on_yaml_output_files
    freq  = content['output_control']['frequency']
```

This appears during `case.build` when generating namelists, before any compilation
begins.
