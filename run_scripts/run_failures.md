# Simulation Failure Analysis

## Case: `scream_cpu_dpxx_RCE_dx1km` — 2026-03-15

### Crash Summary
The simulation crashed with `SIGABRT` on all 1024 MPI ranks, originating inside `scorpio::release_file` in `scream_scorpio_interface.cpp`:
```
Error! Could not retrieve the file. File not open.
 - filename: scream_cpu_dpxx_RCE_dx1km.hist.AVERAGE.nmins_x5.2000-01-01-39600.nc
```

### Context
This was a **restarted run** starting from `t = 12h (43200 s)`. The output streams write 5-minute AVERAGE and INSTANT history files, each holding 12 snapshots (1 hour of data per file).

The **AVERAGE** output restart file (`rhist`) recorded:
- `last_output_filename = "...nmins_x5.2000-01-01-39600.nc"` — the final AVERAGE file from the first run (hours 11–12)
- `last_output_file_num_snaps = 12` — the file was **completely full** (12/12 snapshots)

### Root Cause: Bug in `scream_output_manager.cpp`

In the history-restart initialization path, the code unconditionally set:
```cpp
m_output_file_specs.is_open = true;  // ← BUG
```
…regardless of whether the previous file still had room for new snapshots. Then it checked whether the file was full before actually opening it in scorpio:
```cpp
if (m_output_file_specs.storage.snapshot_fits(...)) {
    setup_file(m_output_file_specs, m_output_control);  // opens file in scorpio
}
// else: file is full, setup_file NOT called → file not opened in scorpio
//       but is_open = true remains!
```

When the model reached its **first output step** at `t = 43500 s` (step 1450, ≈ 5 min after restart), `setup_output_file` saw `is_open = true` + `snapshot_fits = false` and called `scorpio::release_file` to close the "open" file before creating a new one — but scorpio had never seen this file in the current run, causing the crash.

### The Fix

**File:** `components/eamxx/src/share/io/scream_output_manager.cpp`

- **Removed** the unconditional `m_output_file_specs.is_open = true`
- **Added** an `else` branch to reset `m_resume_output_file = false` when the file is full, so that the first output step correctly opens a brand-new file (including writing grid/geo data to it)

Since `setup_file` already sets `is_open = true` (and `m_resume_output_file = false`) internally, this fix is sufficient for both cases: when the old file has room (resumed) and when it is full (new file required).

```cpp
// Fixed code (around line 232):
if (m_resume_output_file) {
    int num_snaps = scorpio::get_attribute<int>(rhist_file,"GLOBAL","last_output_file_num_snaps");

    m_output_file_specs.filename = last_output_filename;
    m_output_file_specs.storage.num_snapshots_in_file = num_snaps;

    if (m_output_file_specs.storage.snapshot_fits(m_output_control.next_write_ts)) {
        // setup_file sets filespecs.is_open = true and m_resume_output_file = false.
        setup_file(m_output_file_specs, m_output_control);
    } else {
        // File is full — do NOT mark as open, reset flag so a fresh file is created.
        m_resume_output_file = false;
    }
}
```

### Details: `m_resume_output_file` flag

`m_resume_output_file` is a `bool` (declared as `bool m_resume_output_file = false` in `scream_output_manager.hpp`). It is a **one-shot flag** that says: *"on the very next call to `setup_file`, open the existing NetCDF file in **Append** mode instead of creating a new one."* It is set to `true` at most once — during history restart — and is always reset to `false` at the end of `setup_file`.

#### Lifecycle

| Step | What happens |
|------|--------------|
| **History restart init** | If the previous run produced output and `force_new_file` is not set, `m_resume_output_file = true`. The filename and snapshot count are loaded from the `rhist` file. If the file has room, `setup_file` is called immediately (which opens the file in Append mode and resets the flag). |
| **Inside `setup_file`** | `m_resume_output_file` controls **two** behaviors: (1) `scorpio::register_file` receives mode `Append` vs `Write`; (2) if `true`, it skips re-defining time/coordinate variables and re-writing grid/geo data (those are already in the file from the previous run). At the very end of `setup_file`, the flag is always set back to `false`. |
| **Every subsequent call** | `m_resume_output_file` is `false`, so `setup_file` always creates a fresh file. |

#### The bug in context
Before the fix, when the previous file was **full** (`snapshot_fits = false`), the `setup_file` call inside the restart block was **skipped** — meaning the flag was never reset to `false` inside `setup_file`. Meanwhile `m_output_file_specs.is_open` was set to `true`. So at the first real output step:

1. `setup_output_file` saw `is_open = true` + `snapshot_fits = false` → called `scorpio::release_file` to "close" it → **crash**, because scorpio never opened it.
2. Even if the crash hadn't occurred, `m_resume_output_file` would still be `true` — causing `setup_file` to open the full file in Append mode and try to overwrite existing data.

The fix avoids both problems by resetting `m_resume_output_file = false` (and **not** setting `is_open = true`) when the previous file is full, so the first output step cleanly creates a new file.

### Additional Observations
The log also shows many `Qm_prev < -0.5` warnings from the HOMME dynamics tracer limiter across many ranks (tracer q=8, ti=8). These are diagnostic warnings about minor negative tracer mass values and are **unrelated to the crash** — they appeared during the 8 successful steps (1440–1448) before the output step triggered the crash.

### Next Steps
The model needs to be **rebuilt** after this code change before resubmitting:

Then resubmit the job to continue from the existing restart at `2000-01-01-43200`.

---

## Output YAML Key Name Changes: old `ksa/uvwinds` format vs. new `waccem/master` format

When porting output YAML files from the older E3SM/EAMxx codebase (e.g., `ksa/uvwinds`) to the
`waccem/master` branch, the following top-level key names must be updated. The old keys used
title-case with spaces; the new keys use lowercase with underscores.

| Old key (ksa/uvwinds) | New key (waccem/master) |
|-----------------------|-------------------------|
| `Averaging Type: Average` | `averaging_type: average` |
| `Averaging Type: Instant` | `averaging_type: instant` |
| `Max Snapshots Per File: N` | `max_snapshots_per_file: N` |
| `Fields:` | `fields:` |
| `  Physics PG2:` | `  physics_pg2:` |
| `    Field Names:` | `    field_names:` |
| `output_control:`<br>`  Frequency: N` | `output_control:`<br>`  frequency: N` |

The `frequency_units` key was already lowercase in both versions and does not need to change.

### Example: old format
```yaml
%YAML 1.1
---
Averaging Type: Average
Max Snapshots Per File: 12
filename_prefix: ${CASE}.hist
Fields:
  Physics PG2:
    Field Names:
    - T_mid
    - qv
output_control:
  Frequency: 5
  frequency_units: nmins
```

### Example: new format
```yaml
%YAML 1.1
---
averaging_type: average
max_snapshots_per_file: 12
filename_prefix: ${CASE}.hist
fields:
  physics_pg2:
    field_names:
    - T_mid
    - qv
output_control:
  frequency: 5
  frequency_units: nmins
```

The new-format files for the test case are:
- `yaml_files/scream_new_output_avg_5min.yaml` (AVERAGE, 5-minute)
- `yaml_files/scream_new_output_inst_5min.yaml` (INSTANT, 5-minute)

The old-format files (`scream_output_avg_5min.yaml`, `scream_output_inst_5min.yaml`, etc.) are
retained for use with older branches.

---

## Running `xmlquery` interactively: `ERROR: file not found .../ccs_config/machines/config_machines.xml`

### Symptom

Running `xmlquery` directly from an interactive shell in the case directory fails:

```
$ cd /pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/scream_cpu_dpxx_RCE_dx1km/case_scripts
$ ./xmlquery RESUBMIT
ERROR: file not found /global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM/ccs_config/machines/config_machines.xml
```

The same query works fine when run from inside the run script (e.g., `run_cpu_dpxx_scream_RCE_dx1km.sh`).

### Root Cause

CIME resolves config file paths differently depending on the value of `CIME_MODEL`:

| `CIME_MODEL` | Config path used |
|---|---|
| `e3sm` | `$SRCROOT/cime_config/machines/config_machines.xml` ✅ (exists) |
| `cesm` | `$SRCROOT/ccs_config/machines/config_machines.xml` ❌ (does not exist in this E3SM checkout) |

The system default on NERSC (pm-cpu) is `CIME_MODEL=cesm`. The run script sets `export CIME_MODEL=e3sm` early on, which is why it works there. An interactive shell does not have this export, so it falls back to the system default `cesm` and looks for the wrong path.

### Fix: create `~/.cime/config`

The permanent fix is to create `~/.cime/config` so CIME always uses the correct model regardless of the shell environment:

```ini
[main]
CIME_MODEL=e3sm
```

See the next section for a fully annotated version of this file with all supported options.

---

## Useful options in `~/.cime/config`

CIME reads `~/.cime/config` (a Python `configparser` INI file) at the beginning of each tool
invocation — i.e., whenever you run any CIME script such as `./xmlquery`, `./create_newcase`, or
`./case.submit`. There is no persistent CIME process; each tool is a standalone Python script that
reads this file once before processing any arguments or case XML files. This is the canonical place
to set persistent defaults so they do not need to be exported in every shell or repeated in every
run script. CIME raises an error on any unrecognised key, so the lists below are exhaustive.

### `[main]` section — general defaults

```ini
[main]
# REQUIRED for E3SM/SCREAM — fixes the xmlquery error above
CIME_MODEL=e3sm

# Default machine (saves --machine flag on create_newcase / xmlquery)
# machine=pm-cpu

# Default compiler
# compiler=gnu

# Allocation account for job submission
# project=m1867

# Charge account if billing differs from project
# charge_account=m1867

# MPI library (CIME picks the machine default if unset)
# mpilib=openmpi

# Path to E3SM source root (useful when running CIME tools outside the source tree)
# srcroot=/global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM

# Path to shared input data (DIN_LOC_ROOT)
# input_dir=/global/cfs/cdirs/e3sm/inputdata

# CIME coupler driver: "mct" or "nuopc"
# cime_driver=mct

# Email notifications for submitted jobs
# mail_type=all        # none | never | begin | end | fail | all
# mail_user=you@example.com
```

### `[create_test]` section — defaults for the `create_test` workflow

These are only relevant when running the CIME test suite (`create_test`), not for standard DP-SCREAM runs.

```ini
[create_test]
# mail_type=fail
# mail_user=you@example.com
# save_timing=false
# test_root=/path/to/test/cases
# baseline_root=/path/to/baselines
# machine=pm-cpu
# compiler=gnu
# mpilib=openmpi
# walltime=01:00:00
# job_queue=regular
# parallel_jobs=8
```

### Switching between E3SM and CESM interactively

`~/.cime/config` is **overridden by the `CIME_MODEL` environment variable** if it is set. On
NERSC, `~/.bash_profile` sets `CIME_MODEL=cesm` (needed for CESM runs), so the config file value
never applies in a normal login shell.

To switch model contexts within a session, use the aliases defined in `~/.bash_profile`:

```bash
e3sm-mode   # sets CIME_MODEL=e3sm — use before running xmlquery/case tools for E3SM/SCREAM
cesm-mode   # sets CIME_MODEL=cesm — restores the default for CESM runs
```

These are equivalent to `export CIME_MODEL=e3sm` / `export CIME_MODEL=cesm` and last until the
shell session ends or you switch again. The run scripts already set `export CIME_MODEL=e3sm`
internally, so this is only needed for interactive use.

---

## `--mail-type end,fail` in `case.submit` only delivers failure emails — 2026-04-20

### Symptom

`./case.submit --mail-user $submitter_email --mail-type end,fail` is called in the run script, but
email is only received when a job **fails**; no email arrives when the job **ends successfully**.

### Root Cause

CIME's `env_batch.py` generates one `--mail-type` flag **per type** rather than a single
comma-separated flag:

```
# CIME-generated sbatch args:
sbatch --mail-user you@example.com --mail-type end --mail-type fail ...
```

SLURM treats multiple `--mail-type` flags as **last-one-wins**, so only `fail` takes effect.

The relevant code in `env_batch.py` (around line 1051):
```python
submitargs += " {} {}".format(
    mail_type_flag,
    " {} ".format(mail_type_flag).join(mail_type_args),
    # → "--mail-type end --mail-type fail"   (last flag wins in SLURM)
)
```

This can be verified by inspecting the generated batch script — no `#SBATCH --mail-type` line
appears in `.case.run.sh` because the flags are passed directly to `sbatch` on the command line,
and SLURM silently honours only the last one.

### Fix

Use `--mail-type all` instead of `--mail-type end,fail`. This passes a single flag that SLURM
handles correctly:

```bash
# In the run script:
./case.submit --mail-user $submitter_email --mail-type all
```

**Trade-off:** `all` also sends a BEGIN notification when the job starts. If that is unwanted, the
alternative is to patch `env_batch.py` locally to join types with a comma instead of repeating the
flag, but that modifies E3SM source code.

The permanent alternative is to set `mail_type` in `~/.cime/config` (see the section above) and
omit `--mail-type` from the `case.submit` call entirely:

```ini
[main]
mail_type=end,fail
mail_user=Koichi.Sakaguchi@pnnl.gov
```

CIME reads this value through `cime_config.get("main", "MAIL_TYPE")` and also passes it as a
comma-separated string to `mail_type.split(",")`, which then hits the same multi-flag generation
bug. So `~/.cime/config` does **not** work around the issue — use `mail_type=all` there as well.

---

## `TypeError: expected an Element, not _Element` in `xmlchange` / `xmlquery` — 2026-03-17

### Symptom

Running `run_cpu_dpxx_scream_RCE_dx1km.sh` (or any script that calls `xmlchange`) fails immediately after "Editing xml files" with:

```
TypeError: expected an Element, not _Element
```

Full traceback ends in:
```
File ".../nersc-python/lib/python3.13/xml/etree/ElementTree.py", line 527, in __init__
    raise TypeError('expected an Element, not %s' % type(element).__name__)
```

### Root Cause

`xmlchange` uses `#!/usr/bin/env python3`. When the E3SM unified environment is **not** loaded in
the shell, `python3` resolves to **Python 3.13** from the NERSC PE environment. Python 3.13
tightened `xml.etree.ElementTree.ElementTree.__init__()` to reject anything that is not a genuine
`ET.Element` instance.

CIME's `generic_xml.py` wraps all XML nodes in its own `_Element` class (a plain Python object —
**not** a subclass of `ET.Element`). In the new-case creation path it passed this wrapper directly
to `ET.ElementTree()`:

```python
# Before (line ~102 in generic_xml.py):
root = _Element(ET.Element("xml"))
...
self.tree = ET.ElementTree(root)   # root is CIME's wrapper → TypeError on Python 3.13
```

### Fix Applied

**File:** `E3SM/model/E3SM/cime/CIME/XML/generic_xml.py`

Unwrap to the raw `ET.Element` before passing to `ET.ElementTree`:

```python
# After:
self.tree = ET.ElementTree(root.xml_element)   # raw ET.Element → works on all Python versions
```

`self.root` (the CIME `_Element` wrapper) is stored and used separately from `self.tree`, so this
change is fully consistent with how the file-reading path (`read_fd`) already works.

### Also Recommended

Before running any run script, source the E3SM unified environment so CIME tools always use a
tested Python version (the script header already mentions this):

```bash
source /global/common/software/e3sm/anaconda_envs/load_latest_e3sm_unified_pm-cpu.sh
```

---

## CFL violation during DP-SCREAM high-resolution runs — 2026-08-18

case: dx1km_L600km_RCE03_gpu

job id: 57196111

rundir: `/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/dx1km_L600km_RCE03_gpu/run`

### Symptom

The simulation aborts and `srun: error: nidXXXX: task XX: Terminated` is seen in the main `e3sm.log.57196111.260817-234641`. 
Checking the HOMME error log (e.g., `run/hommexx.errlog.64.26`) reveals the following explicit error:

```
label: Vertical remap: Negative (or nan) layer thickness detected, aborting!
```

### Root Cause

A CFL (Courant–Friedrichs–Lewy) violation occurred in the dynamical core. When strong updrafts develop (e.g., deep convection reaching >30 m/s vertical velocities), the high wind speeds combined with a fine grid spacing (like `dx=1km`) cause the default dynamics time step to be too large to maintain numerical stability. This causes the vertical remapping step to calculate negative layer thicknesses.

### Fix

Reduce the dynamics time step (`dyn_dtime`) in your run script to a smaller value that still divides evenly into the `model_dtime`. For a 1 km resolution with `model_dtime=30`, the default `dyn_dtime=2.5` (a divisor of 12) may be too large. Decrease it to `1.5`, `1.25`, or `1.0`.

```diff
# In your run script:
# dynamics time step [s]:
-dyn_dtime=2.5
+dyn_dtime=1.5
```
