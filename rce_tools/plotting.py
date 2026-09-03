import os
import sys
import shutil
import subprocess
import numpy as np
import pandas as pd
from matplotlib.ticker import AutoMinorLocator

def _find_working_ffmpeg():
    """Return path to a ffmpeg binary that can encode h264, or None."""
    candidates = []
    # imageio-ffmpeg bundles a complete, working ffmpeg binary; try it first.
    try:
        import imageio_ffmpeg
        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except ImportError:
        pass
    candidates += [
        os.path.join(os.path.dirname(sys.executable), "ffmpeg"),  # conda env
        shutil.which("ffmpeg"),                                     # PATH
        "/usr/bin/ffmpeg",                                          # system
    ]
    for path in candidates:
        if not path or not os.path.isfile(path):
            continue
        try:
            # Quick smoke-test: can the binary run at all?
            result = subprocess.run(
                [path, "-encoders"],
                capture_output=True, timeout=10)
            if result.returncode == 0 and b"libx264" in result.stdout:
                return path
        except Exception:
            continue
    return None


def get_2d_slice(da, tidx, lev_index=None, vfactor=1.0, vshift=0.0):
    """Return a scaled 2-D (ny, nx) numpy array from a DataArray.

    Parameters
    ----------
    da         : xr.DataArray  – (time, [lev,] lat, lon)
    tidx       : int           – time index
    lev_index  : int or None   – level index (for 3-D fields only)
    vfactor    : float         - scale factor for data values
    vshift     : float         - shift added to data values

    Scaling by vfactor and vshift is applied here so callers always receive plot-ready values.
    """
    arr = da.isel(time=tidx)
    if 'lev' in arr.dims:
        if lev_index is None:
            raise ValueError("lev_index must be specified for 3-D variables.")
        arr = arr.isel(lev=lev_index)
    return arr.values.astype(float) * vfactor + vshift


def get_2d_timemean(da, lev_index=None, vfactor=1.0, vshift=0.0):
    """Return the scaled time-mean 2-D (ny, nx) numpy array.

    Parameters
    ----------
    da         : xr.DataArray  – (time, [lev,] lat, lon)
    lev_index  : int or None   – level index (for 3-D fields only)
    vfactor    : float         - scale factor for data values
    vshift     : float         - shift added to data values

    Scaling by vfactor and vshift is applied here so callers always receive plot-ready values.
    """
    arr = da.mean(dim='time')
    if 'lev' in arr.dims:
        if lev_index is None:
            raise ValueError("lev_index must be specified for 3-D variables.")
        arr = arr.isel(lev=lev_index)
    return arr.values.astype(float) * vfactor + vshift


def noleap_days_since(t_val, t0):
    """Elapsed fractional days from t0 to t_val under noleap calendar.

    Gregorian arithmetic counts Feb 29 as a real day; noleap does not.
    This function subtracts one day for every Feb 29 that falls strictly
    between t0 and t_val so the result matches the model's internal day
    counter, which uses a 365-day year.
    """
    total_sec = (t_val - t0).total_seconds()
    t_lo, t_hi = (t0, t_val) if total_sec >= 0 else (t_val, t0)
    leap_days = sum(
        1 for y in range(t_lo.year, t_hi.year + 1)
        if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))  # Gregorian leap year
        and t_lo < pd.Timestamp(y, 2, 29) <= t_hi
    )
    correction = leap_days if total_sec >= 0 else -leap_days
    return total_sec / 86400.0 - correction


def plot_2d_field(ax, field_2d, X, Y, method, n_lev, cmap_name,
                  vmin=None, vmax=None):
    """Plot a 2-D field on the given axes using contourf or pcolormesh.

    Parameters
    ----------
    ax        : matplotlib Axes
    field_2d  : (ny, nx) ndarray
    X, Y      : (ny, nx) coordinate meshes (km)
    method    : "contourf" or "pcolormesh"
    n_lev     : int – number of contour levels
    cmap_name : str – matplotlib colormap name
    vmin/vmax : optional colour limits

    Returns
    -------
    im : the mappable object (for colorbar)
    """
    if vmin is None:
        vmin = np.nanpercentile(field_2d, 2)
    if vmax is None:
        vmax = np.nanpercentile(field_2d, 98)

    if method == "contourf":
        levels = np.linspace(vmin, vmax, n_lev + 1)
        im = ax.contourf(X, Y, field_2d, levels=levels,
                         cmap=cmap_name, extend="both")
    else:  # pcolormesh
        im = ax.pcolormesh(X, Y, field_2d,
                           cmap=cmap_name, vmin=vmin, vmax=vmax,
                           shading="nearest")

    ax.set_aspect("equal")
    ax.set_xlabel("X [km]", fontsize=10)
    ax.set_ylabel("Y [km]", fontsize=10)
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    return im
