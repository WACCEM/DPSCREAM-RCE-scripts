# DP-SCREAM: Doubly-Periodic SCREAM — Radiative-Convective Equilibrium

Scripts, notebooks, and configuration files for running and post-processing
**DP-SCREAM** (Doubly-Periodic Simple Cloud-Resolving E3SM Atmosphere Model)
simulations of idealized **Radiative-Convective Equilibrium (RCE)** cases.

---

## Table of Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Requirements](#requirements)
- [Usage](#usage)
  - [Running Simulations](#running-simulations)
  - [Post-Processing](#post-processing)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [Contact](#contact)

---

## Overview

This repository provides tools to:

- Launch DP-SCREAM RCE simulations on HPC systems (CPU and GPU)
- Configure model output via YAML files
- Concatenate, regrid, and horizontally average model output
- Analyse and visualise the results via Jupyter notebooks

---

## Repository Structure

```
DP-SCREAM/
├── python_DP-SCREAM/     # Python scripts and Jupyter notebooks for post-processing
│   ├── remap/            # Horizontal remapping weights and regridding scripts
│   └── *.py / *.ipynb
├── run_scripts/          # Bash job-submission scripts for HPC
│   └── yaml_files/       # SCREAM output YAML configuration files
├── theory/               # (external / not tracked) Notes and LaTeX write-ups
└── scmlib/               # (external / not tracked) SCM/DP utility library
```

---

## Requirements

| Dependency | Purpose |
|------------|---------|
| Python ≥ 3.9 | Post-processing and analysis |
| `xarray`, `numpy`, `scipy` | Data manipulation |
| `matplotlib`, `cartopy` | Visualisation |
| `xesmf` | Regridding |
| `netCDF4` / `h5py` | NetCDF I/O |
| E3SM / SCREAM source code | Running simulations |

---

## Usage

### Running Simulations

Job scripts are located in `run_scripts/`. Edit the relevant script for your
allocation and paths, then submit:

```bash
# Example — GPU run
sbatch run_scripts/run_gpu_dpxx_scream_RCE_dx1km.sh
```

See `run_scripts/RCE_configuration.md` for a description of the RCE case setup.

### Post-Processing

```bash
# Concatenate output files
python python_DP-SCREAM/concat_DPSCREAM.py

# Horizontal average
python python_DP-SCREAM/horiz_avg_DPSCREAM.py

# Regrid to unstructured grid
python python_DP-SCREAM/remap/regrid_dpxx_output.py
```

Or open the Jupyter notebooks in `python_DP-SCREAM/` for interactive analysis.

---

## Configuration

Model output variables and frequency are controlled by YAML files in
`run_scripts/yaml_files/`. See `run_scripts/RCE_configuration.md` for details.

---

## Contributing

1. Fork the repository and create a feature branch.
2. Follow existing code style (PEP 8 for Python, ShellCheck-clean for bash).
3. Open a pull request with a clear description of the changes.

---

## Contact

| Name | Institution | Email |
|------|-------------|-------|
| TODO | TODO | TODO |
