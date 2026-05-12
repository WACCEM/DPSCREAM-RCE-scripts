#!/usr/bin/env python
"""
Calculate cold pool (CP) diagnostics from DP-SCREAM output.

Cold pool methodology following PINACLES CaseRCE.py
(see also PINACLES_RCE_note.md § "Cold pool diagnostics"):

Buoyancy is computed using Density Potential Temperature (θ_ρ):

    θ_ρ = θ · (1 + (R_v/R_d)·q_v) / (1 + q_v + q_c + q_i + q_r)

where θ = T·(P0/p)^κ  (= PotentialTemperature in the output).

Unlike PINACLES (anelastic, constant-in-time reference density), DP-SCREAM
uses fully compressible equations of motion.  Therefore the reference state is
the area-weighted horizontal mean of θ_ρ computed at each output time step:

    θ_ρ_ref(t, k) = Σ_col [ θ_ρ(t, col, k) · A_col ] / Σ_col A_col

Buoyancy perturbation:

    b(t, col, k) = G · (θ_ρ(t, col, k) − θ_ρ_ref(t, k)) / θ_ρ_ref(t, k)

Cold pool detection threshold b* = −0.005 m s⁻²:
    A column contains a cold pool if its lowest model level satisfies b < b*.
    Within each qualifying column the first contiguous sub-threshold layer
    (allowing 1-level gaps) is identified and three 2-D diagnostics are
    computed:

    cp_base      height of the bottom of the first cold layer                 [m]
    cp_depth     zz[ktop − kbot]  (height proxy for the layer thickness)      [m]
    cp_intensity sqrt(−2 · ∫ b dz) over the cold layer                       [m s⁻¹]

An additional column-average cold-pool area fraction (cp_area_frac) is also
written as a scalar time series for quick quality checks.

Notes on condensate:
    In SCREAM's P3 microphysics, `qm` is the rime-mass component *within* the
    prognostic ice category `qi`.  It is NOT an additional condensate species
    and must not be added to `qi` when computing total water.  `bm` (bulk rime
    volume, 1/kg) is also diagnostic-only and similarly excluded.

Usage:
    module load python
    conda activate dpscream_analysis
    python calc_cp_DPSCREAM.py [--icase ICASE] [--infile INFILE]
                               [--iyear IYEAR] [--imonth IMONTH]
                               [--iday IDAY] [--isecond ISECOND]
                               [--in_dir IN_DIR] [--threshold THRESHOLD]
"""
# %%

import argparse
import os
import re
import numpy as np
import xarray as xr

# np.trapezoid was introduced in NumPy 2.0; fall back to np.trapz for older installs
_trapz = getattr(np, "trapezoid", np.trapz)

# %%

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
G      = 9.80665    # Gravitational acceleration             [m s⁻²]
RD     = 287.05     # Gas constant, dry air                  [J kg⁻¹ K⁻¹]
RV     = 461.5      # Gas constant, water vapour             [J kg⁻¹ K⁻¹]
RV_RD  = RV / RD   # R_v / R_d ≈ 1.6078                    [dimensionless]
P0     = 100000.0   # Reference pressure                     [Pa]

# Cold pool buoyancy threshold (following PINACLES CaseRCE.py)
CP_THRESHOLD_DEFAULT = -0.005   # [m s⁻²]

# %%

# ---------------------------------------------------------------------------
# Cold pool algorithm (adapted from PINACLES calc_coldpool_intensity)
# ---------------------------------------------------------------------------
def calc_coldpool_diagnostics(buoy_2d, z_2d, threshold=CP_THRESHOLD_DEFAULT):
    """
    Compute cold pool depth, base height, and intensity for one time step.

    Parameters
    ----------
    buoy_2d : ndarray  (ncol, nlev)
        Buoyancy [m s⁻²].  **nlev dimension must run surface→top**
        (index 0 = lowest model level, index nlev−1 = top of atmosphere).
    z_2d : ndarray  (ncol, nlev)
        Height above surface [m], same surface→top ordering.
    threshold : float
        Buoyancy threshold for cold pool detection [m s⁻²].
        Default: −0.005 m s⁻².

    Returns
    -------
    cp_depth, cp_base, cp_intensity : ndarray  (ncol,)
        All initialised to zero; non-zero only in cold-pool columns.
    """
    ncol, nlev = buoy_2d.shape

    cp_depth     = np.zeros(ncol, dtype=np.float64)
    cp_base      = np.zeros(ncol, dtype=np.float64)
    cp_intensity = np.zeros(ncol, dtype=np.float64)

    # Step 1 — identify columns whose lowest level is sub-threshold
    ipool = np.where(buoy_2d[:, 0] < threshold)[0]

    gap = 1  # number of above-threshold levels allowed before declaring
             # a new layer (matching PINACLES calc_coldpool_intensity)

    for i in ipool:
        buoy_profile = buoy_2d[i, :]
        z_profile    = z_2d[i, :]

        # All levels below threshold in this column
        kpool = np.where(buoy_profile < threshold)[0]
        if len(kpool) == 0:
            continue

        # Split into contiguous layers (allow gap of 1 level)
        split_pts = np.where(np.diff(kpool) > gap)[0] + 1
        layers    = np.split(kpool, split_pts)

        if len(layers) == 0 or len(layers[0]) == 0:
            continue

        # Use the first (lowest / surface-rooted) layer
        ktop = int(layers[0][-1])
        kbot = int(layers[0][0])

        # Integrate buoyancy from kbot to ktop using the trapezoidal rule
        integrated_b = _trapz(
            buoy_profile[kbot : ktop + 1],
            z_profile[kbot : ktop + 1],
        )

        # Depth proxy: height at level (ktop − kbot), following PINACLES.
        # For surface-rooted cold pools (kbot = 0), this equals z[ktop],
        # i.e. the height of the top of the cold layer.
        idx_depth = ktop - kbot
        cp_depth[i]     = z_profile[idx_depth]
        cp_base[i]      = z_profile[kbot]
        with np.errstate(invalid="ignore"):
            val = -2.0 * integrated_b
            cp_intensity[i] = np.sqrt(val) if val > 0.0 else 0.0

    return cp_depth, cp_base, cp_intensity


# %%
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(
    description=(
        "Calculate cold pool diagnostics (cp_depth, cp_base, cp_intensity) "
        "from DP-SCREAM output, using density potential temperature buoyancy."
    )
)

# %%

parser.add_argument("--icase",   default="scream_cpu_dpxx_RCE_dx1km",
                    help="Case name (default: scream_cpu_dpxx_RCE_dx1km)")
parser.add_argument("--infile",  default=None,
                    help="Input file name or path "
                         "(overrides --iyear/--imonth/--iday/--isecond)")
parser.add_argument("--iyear",   type=int, default=2000,
                    help="Year component of timestamp (default: 2000)")
parser.add_argument("--imonth",  type=int, default=2,
                    help="Month component of timestamp (default: 2)")
parser.add_argument("--iday",    type=int, default=1,
                    help="Day component of timestamp (default: 1)")
parser.add_argument("--isecond", type=int, default=0,
                    help="Second component of timestamp (default: 0)")
parser.add_argument("--in_dir",  type=str, default=None,
                    help="Input directory (overrides default path)")
parser.add_argument("--ifreq",  type=str, default="nmins_x5",
                    help="Input frequency (overrides default path)")

parser.add_argument("--threshold", type=float, default=CP_THRESHOLD_DEFAULT,
                    help=(
                        "Buoyancy threshold for cold pool detection [m s⁻²] "
                        f"(default: {CP_THRESHOLD_DEFAULT})"
                    ))

# %%

import sys
# When running interactively (Jupyter / IPython), sys.argv contains kernel
# launch flags that confuse argparse.  Pass an empty list so all arguments
# fall back to their defaults; override the variables directly below instead.
_interactive = hasattr(sys, "ps1") or "ipykernel" in sys.modules
args = parser.parse_args([] if _interactive else None)

# %%

icase     = args.icase
infile    = args.infile
iyear     = args.iyear
imonth    = args.imonth
iday      = args.iday
isecond   = args.isecond
in_dir    = args.in_dir
ifreq     = args.ifreq
threshold = args.threshold

if in_dir is None:
    in_dir = f"/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/{icase}/run"
out_dir = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/cat_raw"


# %%

if infile is not None:
    in_basename = infile
    basename    = os.path.basename(infile)
    match       = re.search(r"\d{4}-\d{2}-\d{2}-\d{5}", basename)
    if not match:
        raise ValueError(f"Could not extract timestamp from filename: {basename}")
    timestamp = match.group()
else:
    timestamp   = f"{iyear:04d}-{imonth:02d}-{iday:02d}-{isecond:05d}"
    in_basename = f"{icase}.hist.INSTANT.{ifreq}.{timestamp}.nc"

out_basename = f"{icase}.cp.INSTANT.{ifreq}.{timestamp}.nc"

input_file  = os.path.join(in_dir,  in_basename)
output_file = os.path.join(out_dir, out_basename)

# %%

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print(f"Reading: {input_file}")
ds = xr.open_dataset(input_file)

# 3-D fields  (time, ncol, lev)  — lev runs top→bottom (lev[0]=TOA, lev[-1]=sfc)
theta = ds["PotentialTemperature"].values   # [K]
qv    = ds["qv"].values                     # [kg kg⁻¹]  water vapour
qc    = ds["qc"].values                     # [kg kg⁻¹]  cloud liquid
qi    = ds["qi"].values                     # [kg kg⁻¹]  total cloud ice (P3)
qr    = ds["qr"].values                     # [kg kg⁻¹]  rain
# NOTE: qm (rime mass) is a sub-component of qi in P3.  Do not add separately.
z_mid = ds["z_mid"].values                  # [m]  height above sea level

# 2-D fields  (time, ncol)
# (not needed for buoyancy, but kept for provenance)

# 1-D grid fields
area  = ds["area"].values   # (ncol,)  cell area [m²]
time  = ds["time"]
lat   = ds["lat"]
lon   = ds["lon"]
lev   = ds["lev"]

ntime, ncol, nlev = theta.shape

# %%

# ---------------------------------------------------------------------------
# Density Potential Temperature  θ_ρ  (time, ncol, lev)
#
#   θ_ρ = θ · (1 + (R_v/R_d)·q_v) / (1 + q_v + q_c + q_i + q_r)
#
# This accounts for both the density-reducing effect of water vapour and the
# density-increasing effect of condensed water, making it appropriate for
# buoyancy in the fully compressible DP-SCREAM framework.
#
# NOTE: the dataset fields are float32.  Summing 160,000 float32 values in the
# area-weighted mean causes ~0.2 K precision errors that bias the buoyancy.
# All intermediate computations are promoted to float64 here.
# ---------------------------------------------------------------------------
qt        = (qv + qc + qi + qr).astype(np.float64)   # total water  [kg kg⁻¹]
theta_f64 = theta.astype(np.float64)
qv_f64    = qv.astype(np.float64)
theta_rho = theta_f64 * (1.0 + RV_RD * qv_f64) / (1.0 + qt)   # float64

# %%

# ---------------------------------------------------------------------------
# Area-weighted horizontal mean θ_ρ — used as the reference profile
#   θ_ρ_ref(t, k) = Σ_col [ θ_ρ(t, col, k) · A_col ] / Σ_col A_col
# ---------------------------------------------------------------------------
weights       = area.astype(np.float64) / np.sum(area.astype(np.float64))  # float64 normalised weights
# einsum: sum over ncol (j), preserve time (t) and lev (k)
theta_rho_ref = np.einsum("j,tjk->tk", weights, theta_rho)   # (time, lev) float64

# %%

# ---------------------------------------------------------------------------
# Buoyancy perturbation  b(t, col, k) = G · (θ_ρ - θ_ρ_ref) / θ_ρ_ref
# ---------------------------------------------------------------------------
# Broadcast reference: (time, lev) → (time, 1, lev)
buoyancy = G * (theta_rho - theta_rho_ref[:, np.newaxis, :]) / theta_rho_ref[:, np.newaxis, :]
# buoyancy: (time, ncol, lev)  — lev still top→bottom

# %%

# ---------------------------------------------------------------------------
# Cold pool diagnostics — applied per time step
#
# The cold pool algorithm expects the vertical dimension to run
# surface→top (index 0 = lowest model level).
# DP-SCREAM lev[0] = TOA, lev[-1] ≈ surface  →  flip the lev axis.
# ---------------------------------------------------------------------------
cp_depth_all     = np.zeros((ntime, ncol), dtype=np.float32)
cp_base_all      = np.zeros((ntime, ncol), dtype=np.float32)
cp_intensity_all = np.zeros((ntime, ncol), dtype=np.float32)
buoy_sfc_all     = np.zeros((ntime, ncol), dtype=np.float32)  # surface buoyancy

for it in range(ntime):
    # Flip vertical: surface (lev[-1]) → index 0
    buoy_flip = buoyancy[it, :, ::-1]   # (ncol, nlev),  index 0 = surface
    z_flip    = z_mid[it,   :, ::-1]    # (ncol, nlev),  index 0 = surface

    # Surface buoyancy diagnostic (lowest model level after flip)
    buoy_sfc_all[it, :] = buoy_flip[:, 0]

    cp_d, cp_b, cp_i = calc_coldpool_diagnostics(buoy_flip, z_flip, threshold=threshold)

    cp_depth_all[it,     :] = cp_d.astype(np.float32)
    cp_base_all[it,      :] = cp_b.astype(np.float32)
    cp_intensity_all[it, :] = cp_i.astype(np.float32)

    n_cp = np.sum(buoy_flip[:, 0] < threshold)
    print(f"  t={it:3d}: cold-pool columns = {n_cp:6d} / {ncol:6d} "
          f"({100*n_cp/ncol:.1f}%)")

# %%

# Area-weighted cold pool area fraction  (time,)
cp_mask     = (cp_intensity_all > 0.0).astype(np.float64)           # (time, ncol)
cp_area_frac = np.einsum("j,tj->t", weights, cp_mask)               # (time,)

# %%

# ---------------------------------------------------------------------------
# Save output
# ---------------------------------------------------------------------------
os.makedirs(out_dir, exist_ok=True)

threshold_str = f"{threshold:.4f}"
ref_method    = "area-weighted horizontal mean theta_rho at each output time"

ds_out = xr.Dataset(
    {
        "cp_depth": xr.DataArray(
            cp_depth_all,
            dims=["time", "ncol"],
            attrs={
                "long_name":   "Cold Pool Depth",
                "description": (
                    "Approximate vertical extent of the first sub-threshold "
                    "buoyancy layer: zz[ktop−kbot].  For surface-rooted cold "
                    "pools (kbot=0) this equals the height of the cold pool top."
                ),
                "units":       "m",
                "threshold":   threshold_str,
            },
        ),
        "cp_base": xr.DataArray(
            cp_base_all,
            dims=["time", "ncol"],
            attrs={
                "long_name":   "Cold Pool Base Height",
                "description": "Height of the bottom of the first sub-threshold buoyancy layer.",
                "units":       "m",
                "threshold":   threshold_str,
            },
        ),
        "cp_intensity": xr.DataArray(
            cp_intensity_all,
            dims=["time", "ncol"],
            attrs={
                "long_name":   "Cold Pool Intensity",
                "description": (
                    "sqrt(−2 · ∫ b dz) integrated over the cold layer "
                    "(analogous to the velocity acquired by a negatively "
                    "buoyant parcel traversing the cold pool depth)."
                ),
                "units":       "m s-1",
                "threshold":   threshold_str,
            },
        ),
        "buoy_sfc": xr.DataArray(
            buoy_sfc_all,
            dims=["time", "ncol"],
            attrs={
                "long_name":   "Near-surface Buoyancy",
                "description": "Buoyancy at the lowest model level (lev[-1] ≈ z~13 m).",
                "units":       "m s-2",
                "formula":     "G*(theta_rho - theta_rho_ref)/theta_rho_ref",
            },
        ),
        "cp_area_frac": xr.DataArray(
            cp_area_frac.astype(np.float32),
            dims=["time"],
            attrs={
                "long_name":   "Cold Pool Area Fraction",
                "description": (
                    "Area-weighted fraction of columns with non-zero cp_intensity "
                    "(i.e. columns where the lowest level buoyancy < threshold)."
                ),
                "units":       "1",
                "threshold":   threshold_str,
            },
        ),
        "lat": lat,
        "lon": lon,
    },
    coords={"time": time, "lev": lev},
)

ds_out.attrs.update({
    "source_file": in_basename,
    "script":      os.path.basename(__file__),
    "description": (
        "Cold pool diagnostics from DP-SCREAM output. "
        "Buoyancy computed from Density Potential Temperature (theta_rho = "
        "theta*(1+Rv_Rd*qv)/(1+qv+qc+qi+qr)) relative to the area-weighted "
        "horizontal mean at each output time step. "
        "Cold pool detection threshold: "
        f"b* = {threshold} m s^-2 (PINACLES CaseRCE.py convention). "
        "Vertical integration uses the trapezoidal rule. "
        "Physical constants: G=9.80665, Rd=287.05, Rv=461.5 J kg^-1 K^-1."
    ),
    "reference_state": ref_method,
    "cp_threshold":    threshold_str,
    "RV_RD":           f"{RV_RD:.6f}",
})

print(f"Writing: {output_file}")
ds_out.to_netcdf(output_file, encoding={'time': {'_FillValue': None}})
print("Done.")

ds.close()

# %%
