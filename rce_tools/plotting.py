import os
import sys
import shutil
import subprocess
import numpy as np
import pandas as pd
from matplotlib.ticker import AutoMinorLocator

case_info = {
    "RCE02_dx1km_gpu": {
        "model": "DP-SCREAM",
        "desc": "DP EQ IC",
        "color": "Blue"
    },
     "RCE00_dx1km_600x600km": {
        "model": "PINACLES",
        "desc": "RCEMIP IC",
        "color": "lightgreen"
    },
    "RCE01_dx1km_600x600km": {
        "model": "PINACLES",
        "desc": "PINACLES EQ IC",
        "color": "green"
    },
}

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


def add_dual_time_axes(ax, base_date="2000-01-01", bottom_label=None):
    """
    Configure a time-series plot with dual x-axes:
    - Primary (bottom) axis: Days since base_date
    - Secondary (top) axis: MM-DD dates

    Parameters
    ----------
    ax : matplotlib Axes
        The axes object containing time-series data plotted against pandas timestamps
    base_date : str or pd.Timestamp
        The reference date for the primary axis (default: "2000-01-01")
    bottom_label : str
        Label for the bottom axis (default: "Days since {base_date}")
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import pandas as pd
    
    base_dt = pd.to_datetime(base_date)
    
    if bottom_label is None:
        bottom_label = f"Days since {base_dt.strftime('%Y-%m-%d')}"

    def days_since_formatter(x, pos):
        dt = mdates.num2date(x).replace(tzinfo=None)
        days = (dt - base_dt).total_seconds() / 86400.0
        return f"{int(days)}"

    ax.xaxis.set_major_formatter(plt.FuncFormatter(days_since_formatter))
    ax.set_xlabel(bottom_label, fontsize=11)

    secax = ax.secondary_xaxis('top')
    secax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    return secax


def get_case_info(case_name):
    """
    Returns the simulation type, OLR variable name, input NetCDF file path, 
    and output Pickle file path for a given case.
    """
    import glob
    
    if case_name not in case_info:
        raise KeyError(f"Case {case_name} not found in case_info dictionary.")
        
    info = case_info[case_name]
    sim_type = info["model"]
    date_range = info.get("date_range", "*")

    if sim_type == "DP-SCREAM":
        olr_var = "LW_flux_up_at_model_top"
    elif sim_type == "PINACLES":
        olr_var = "toa_lw_up"
    else:
        raise ValueError(f"Unknown sim type '{sim_type}' for case: {case_name}")

    in_dir = f'/pscratch/sd/w/wcmca1/{sim_type}/{case_name}/org_ind'
    
    # Locate NetCDF file
    nc_file = f'{in_dir}/{case_name}_{olr_var}_{date_range}.nc'
    if '*' in nc_file:
        matches = glob.glob(nc_file)
        if matches:
            nc_file = matches[0]

    # Expected Pickle file path
    pkl_file = f'/global/cfs/cdirs/m1867/RCE/org_ind/df_{sim_type}_{case_name}_periodic_hourly.pkl'
    
    return sim_type, olr_var, nc_file, pkl_file


def get_horiz_stats_file(case_name, vname, stats_type="INSTANT"):
    """
    Returns the path to the horizontal statistics NetCDF file for a given case.
    Uses glob to find the file dynamically without needing hardcoded date ranges.
    """
    import glob
    
    if case_name not in case_info:
        raise KeyError(f"Case {case_name} not found in case_info dictionary.")
        
    sim_type = case_info[case_name]["model"]
    in_dir = f"/pscratch/sd/w/wcmca1/{sim_type}/{case_name}/havg"
    
    if sim_type == "DP-SCREAM":
        pattern = f"{in_dir}/{case_name}.{vname}.havg.{stats_type}.*.nc"
    elif sim_type == "PINACLES":
        pattern = f"{in_dir}/{case_name}.{vname}.havg.*.nc"
    else:
        raise ValueError(f"Unknown sim type '{sim_type}'")
        
    matches = glob.glob(pattern)
    if not matches:
        return None
    return matches[0]


def to_pandas_series(ds, field, freq=None):
    """Return a pandas Series with a DatetimeIndex, optionally resampled.

    Uses xarray's resample (cftime-aware) before converting to a standard
    pandas DatetimeIndex so that matplotlib date formatters work correctly
    even when the file uses a non-standard calendar (e.g. noleap).
    """
    import pandas as pd
    da = ds[field]
    if freq is not None:
        da = da.resample(time=freq).mean()
    # Convert cftime (or numpy datetime64) time values to pandas Timestamps
    times = pd.DatetimeIndex([
        pd.Timestamp(t.year, t.month, t.day, t.hour, t.minute, t.second)
        for t in da['time'].values
    ])
    return pd.Series(da.values, index=times)
