# -*- coding: utf-8 -*-
"""
Plot output from the original DPxx structured grid alongside the same fields
on the remapped unstructured (200-point) grid.

Produces one PNG per variable listed in VARS_2D and one for the 3-D profile
comparison.  Output is saved to the directory where this script lives.

Usage:
    python plot_original_vs_remapped.py
"""

import os
import numpy as np
import netCDF4 as nc4
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as tri

# -----------------------------------------------------------------------
# User settings
# -----------------------------------------------------------------------
RUNDIR = (
    "/pscratch/sd/m/mahf708/e3sm-scratch/doublyperiodicremap/"
    "scream_dpxx_RCE_300K/run/"
)
FILE_ORIG    = RUNDIR + "scream_dpxx_RCE_300K.fullfield.AVERAGE.nhours_x1.2000-01-01-00000.nc"
FILE_REMAP   = RUNDIR + "scream_dpxx_RCE_300K.fullfield_denser_remap.AVERAGE.nhours_x1.2000-01-01-00000.nc"

OUTDIR = os.path.dirname(os.path.abspath(__file__))

# Domain size in metres — used to set axis limits (should match your run script)
domain_size_x = 500000
domain_size_y = 500000

# 2-D (ncol) variables to map
VARS_2D = ["LiqWaterPath", "IceWaterPath", "T_2m", "pbl_height", "precip_liq_surf_mass_flux"]

# 3-D (ncol × lev) variable for vertical profile comparison
VAR_3D = "T_mid"

# Time index to use from each file (0-based)
TIDX_ORIG  = 0   # original has only 1 time step
TIDX_REMAP = 0   # use the first hourly snapshot of the remapped file
# -----------------------------------------------------------------------


def km(metres):
    return metres / 1000.0


def load_coords(f):
    """Return x, y in km from a NetCDF dataset that uses lon/lat in metres."""
    x = km(f.variables["lon"][:])
    y = km(f.variables["lat"][:])
    return x, y


def try_reshape(x, y, field):
    """
    Try to arrange a flat (ncol,) field onto a 2-D regular grid.
    Returns (ux, uy, 2d_array) if the column layout is regular,
    or (None, None, None) if the grid is truly unstructured.
    """
    ux = np.unique(x)
    uy = np.unique(y)
    nx, ny = len(ux), len(uy)
    if nx * ny != len(x):          # not a regular grid
        return None, None, None
    xi = np.searchsorted(ux, x)
    yi = np.searchsorted(uy, y)
    arr = np.full((ny, nx), np.nan)
    arr[yi, xi] = field
    return ux, uy, arr


# -----------------------------------------------------------------------
# Open files
# -----------------------------------------------------------------------
fo  = nc4.Dataset(FILE_ORIG,  "r")
fr  = nc4.Dataset(FILE_REMAP, "r")

xo, yo = load_coords(fo)
xr, yr = load_coords(fr)

lev_o = fo.variables["lev"][:]


# -----------------------------------------------------------------------
# 1.  Side-by-side 2-D maps for each variable
# -----------------------------------------------------------------------
for varname in VARS_2D:
    if varname not in fo.variables:
        print(f"Skipping {varname}: not found in original file")
        continue

    data_o = np.array(fo.variables[varname][TIDX_ORIG,  :])   # (ncol_orig,)
    data_r = np.array(fr.variables[varname][TIDX_REMAP, :])   # (ncol_remap,)

    # --- convert units for prettier labels
    label = varname
    units = ""
    try:
        units = fo.variables[varname].units
    except AttributeError:
        pass

    ux_o, uy_o, grid_o = try_reshape(xo, yo, data_o)
    ux_r, uy_r, grid_r = try_reshape(xr, yr, data_r)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    fig.suptitle(f"{varname}  [{units}]", fontsize=13)

    # Left: original structured grid
    ax = axes[0]
    pc = ax.pcolormesh(ux_o, uy_o, grid_o, cmap="viridis", shading="nearest")
    fig.colorbar(pc, ax=ax, shrink=0.85)
    ax.set_title(f"Original structured grid  (ncol={len(xo)})", fontsize=10)
    ax.set_xlabel("x  [km]")
    ax.set_ylabel("y  [km]")
    ax.set_aspect("equal")

    # Right: remapped grid — auto-detect regular vs unstructured
    ax = axes[1]
    if grid_r is not None:
        # Regular grid: use pcolormesh for crisp rendering
        pc2 = ax.pcolormesh(ux_r, uy_r, grid_r, cmap="viridis", shading="nearest")
        fig.colorbar(pc2, ax=ax, shrink=0.85)
        remap_label = "Remapped regular grid"
    else:
        # True unstructured grid: triangulate and filled-contour
        # Only overlay sample-point markers for sparse grids (< 500 pts)
        try:
            triang = tri.Triangulation(xr, yr)
            tc = ax.tricontourf(triang, data_r, levels=256, cmap="viridis")
            fig.colorbar(tc, ax=ax, shrink=0.85)
        except Exception:
            sc = ax.scatter(xr, yr, c=data_r, cmap="viridis", s=30)
            fig.colorbar(sc, ax=ax, shrink=0.85)
        if len(xr) < 500:
            ax.scatter(xr, yr, s=20, c="white", edgecolors="k",
                       linewidths=0.4, zorder=5, label="sample points")
            ax.legend(fontsize=8, loc="upper right")
        remap_label = "Remapped unstructured grid"

    ax.set_title(f"{remap_label}  (ncol={len(xr)})", fontsize=10)
    ax.set_xlabel("x  [km]")
    ax.set_ylabel("y  [km]")
    ax.set_aspect("equal")
    ax.set_xlim(0, km(domain_size_x))
    ax.set_ylim(0, km(domain_size_y))

    outfile = os.path.join(OUTDIR, f"compare_{varname}.png")
    fig.savefig(outfile, dpi=150)
    plt.close(fig)
    print(f"Saved: {outfile}")


# -----------------------------------------------------------------------
# 2.  Vertical profile comparison  (domain-mean vs remapped-mean)
# -----------------------------------------------------------------------
if VAR_3D in fo.variables:
    prof_o = np.array(fo.variables[VAR_3D][TIDX_ORIG,  :, :])   # (ncol_orig,  lev)
    prof_r = np.array(fr.variables[VAR_3D][TIDX_REMAP, :, :])   # (ncol_remap, lev)

    mean_o = prof_o.mean(axis=0)   # (lev,)
    mean_r = prof_r.mean(axis=0)   # (lev,)

    fig, ax = plt.subplots(figsize=(5, 8), constrained_layout=True)
    ax.plot(mean_o, lev_o, color="steelblue",  lw=2,   label=f"Original (n={len(xo)} cols)")
    ax.plot(mean_r, lev_o, color="darkorange", lw=2, ls="--", label=f"Remapped (n={len(xr)} pts)")
    ax.invert_yaxis()
    ax.set_xlabel(f"{VAR_3D} [K]", fontsize=11)
    ax.set_ylabel("Pressure  [hPa]", fontsize=11)
    ax.set_title(f"Domain-mean vertical profile: {VAR_3D}", fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)

    outfile = os.path.join(OUTDIR, f"compare_profile_{VAR_3D}.png")
    fig.savefig(outfile, dpi=150)
    plt.close(fig)
    print(f"Saved: {outfile}")

fo.close()
fr.close()
print("Done.")
