#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
change_freq.py

Reads concatenated DP-SCREAM output produced by concat_DPSCREAM.py (one
NetCDF file per day, e.g. at 5-minute frequency) and resamples every
variable in the file to a lower output frequency (e.g. hourly), writing
one output file per input file.

Three resampling methods are supported:
  select  – extract input time steps whose timestamps exactly match the
             target output times (e.g. the top-of-hour sample that is
             already present in 5-minute data).  A warning is raised for
             any target time not found within the configured tolerance.
  interp  – linearly interpolate the input to the target output times
             (handles the rare case where the input does not contain the
             exact target timestamps).
  mean    – average all input samples that fall within each output time
             bin (e.g. average every 5-minute sample in each hour).

Output file names follow the E3SM/EAMxx convention with the frequency tag
replaced (e.g. "nmins_x5" -> "nhours_x1").

Both bottleneck and flox are used when available:
  bottleneck – accelerates xarray nanmean/nansum/nanstd operations
  flox       – fast groupby/resample engine (especially for large ncol grids)

Usage (after loading the environment):
  module load python
  conda activate dpscream_analysis
  python change_freq.py
"""
# %%
import os
import sys
import re
import warnings
import glob
import numpy as np
import pandas as pd
import xarray as xr
import cftime

# Enable bottleneck (faster nanmean/nansum/etc.) and flox (faster
# groupby/resample) when both packages are installed.
try:
    import bottleneck  # noqa: F401  – xarray detects and uses it automatically
    _has_bottleneck = True
except ImportError:
    _has_bottleneck = False
    warnings.warn("bottleneck not found; xarray will use slower numpy reductions.",
                  ImportWarning, stacklevel=1)

try:
    import flox  # noqa: F401  – used via xr.set_options below
    _has_flox = True
except ImportError:
    _has_flox = False
    warnings.warn("flox not found; xarray will use its default resample engine.",
                  ImportWarning, stacklevel=1)

# Activate both engines globally for this session.
xr.set_options(
    use_bottleneck=_has_bottleneck,
    use_flox=_has_flox,
)

# %%
# ---------------------------------------------------------------------------
# User configuration
# ---------------------------------------------------------------------------
icase      = "scream_cpu_dpxx_RCE_dx1km"
varname    = "imse"

# File naming parameters (must match the concatenated input files)
stats_type  = "INSTANT"
file_type   = "proc"   # "raw"  – direct model output (hist stream, all vars in one file)
                       # "proc" – post-processed, one variable per file (e.g. calc_imse output)
                       # "cp"   – cold-pool diagnostics (cp_depth, cp_base, etc.)

in_freq_tag = "nmins_x5"   # E3SM frequency tag used in the input file names
                            # e.g. "nmins_x5" (5-minute), "nhours_x1" (hourly)

in_dir  = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/cat_raw"

# Output directory (created if it does not already exist)
out_dir = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase}/freq_change"

# Date-range timestamps (inclusive, YYYY-MM-DD) to process.
# Must match the date stamps embedded in the input file names.
ts_start = "2000-01-01"
ts_end   = "2000-02-16"

# ---------------------------------------------------------------------------
# Output frequency settings
# ---------------------------------------------------------------------------
# out_freq_tag : E3SM/EAMxx frequency tag written into the output file name.
#   e.g. "nhours_x1"  ->  hourly
#        "nhours_x3"  ->  3-hourly
#        "ndays_x1"   ->  daily
out_freq_tag = "nhours_x1"

# out_freq_pd : pandas offset alias consistent with out_freq_tag above.
#   Used to generate target times and for xarray .resample().
#   e.g. "1h"  for hourly
#        "3h"  for 3-hourly
#        "1D"  for daily
out_freq_pd = "1h"

# ---------------------------------------------------------------------------
# Resampling method
# ---------------------------------------------------------------------------
# "select" – select input time steps that exactly match the target times.
#            Works when the top-of-hour (or other target) sample is already
#            present in the high-frequency input, which is the common case
#            for 5-minute data (00:00, 01:00, 02:00, ... are always present).
#
# "interp" – linearly interpolate from the input time grid to the target
#            times.  Use when the input does not contain the exact target
#            timestamps (e.g. a 7-minute stream starting at 00:03).
#
# "mean"   – temporal average of all input samples within each output bin
#            (e.g. mean of the 12 × 5-min samples in each hour).
resample_method = "select"   # "select" | "interp" | "mean"

# Tolerance for the "select" method: maximum allowed time offset between an
# input sample and the nearest target time for a match to be accepted.
# Expressed as a pandas Timedelta string (e.g. "30s", "2min30s").
select_tolerance = "30s"

# ---------------------------------------------------------------------------
# End user configuration
# ---------------------------------------------------------------------------

# %%
# ---------------------------------------------------------------------------
# Derived file-naming parameters
# ---------------------------------------------------------------------------
styear  = int(ts_start[:4]);  stmonth = int(ts_start[5:7]);  stday = int(ts_start[8:10])
edyear  = int(ts_end[:4]);    edmonth = int(ts_end[5:7]);    edday = int(ts_end[8:10])

start_date = np.datetime64(f"{styear:04d}-{stmonth:02d}-{stday:02d}")
end_date   = np.datetime64(f"{edyear:04d}-{edmonth:02d}-{edday:02d}")
date_range = np.arange(start_date, end_date + np.timedelta64(1, 'D'),
                       dtype='datetime64[D]')

if file_type == "raw":
    file_prefix = f"{icase}.hist.{stats_type}.{in_freq_tag}."
elif file_type == "cp":
    file_prefix = f"{icase}.cp.{stats_type}.{in_freq_tag}."
else:
    file_prefix = f"{icase}.{varname}.{stats_type}.{in_freq_tag}."
file_suffix = ".nc"

date_strs = {str(d) for d in date_range}
infiles = [
    f for f in sorted(glob.glob(os.path.join(in_dir, f"{file_prefix}*.nc")))
    if os.path.basename(f)[len(file_prefix):len(file_prefix) + 10] in date_strs
]

print(f"Period      : {ts_start}  to  {ts_end}")
print(f"Method      : {resample_method}")
print(f"Input  freq : {in_freq_tag}")
print(f"Output freq : {out_freq_tag}  (pandas alias: {out_freq_pd})")
print(f"\nFound {len(infiles)} input file(s):")
for fp in infiles:
    print(f"  {fp}")

if len(infiles) == 0:
    raise FileNotFoundError(
        f"No input files found in:\n  {in_dir}\n"
        f"matching pattern '{file_prefix}*.nc' for the requested date range.\n"
        f"Check icase, varname, stats_type, in_freq_tag, and ts_start/ts_end."
    )

os.makedirs(out_dir, exist_ok=True)

# %%
# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def cftime_to_datetime64(times):
    """Convert an array of cftime objects to numpy datetime64[ns].

    Parameters
    ----------
    times : array-like of cftime.datetime

    Returns
    -------
    numpy.ndarray of dtype datetime64[ns]
    """
    return np.array([
        np.datetime64(
            f"{t.year:04d}-{t.month:02d}-{t.day:02d}"
            f"T{t.hour:02d}:{t.minute:02d}:{t.second:02d}", 'ns')
        for t in times
    ])


def ensure_datetime64_time(ds):
    """Return *ds* with its time coordinate converted to datetime64[ns].

    If the coordinate is already datetime64, *ds* is returned unchanged.
    If it contains cftime objects it is re-assigned via assign_coords.

    Parameters
    ----------
    ds : xarray.Dataset

    Returns
    -------
    xarray.Dataset with a numpy datetime64 time coordinate
    """
    raw = ds['time'].values
    if isinstance(raw[0], cftime.datetime):
        return ds.assign_coords(time=cftime_to_datetime64(raw))
    # Cast to ns precision for consistency
    return ds.assign_coords(time=raw.astype('datetime64[ns]'))


def get_target_times(times_dt64, out_freq):
    """Generate target output times at *out_freq* spanning *times_dt64*.

    The first target is the smallest whole-period boundary >= times_dt64[0],
    and the last is the largest whole-period boundary <= times_dt64[-1].

    Parameters
    ----------
    times_dt64 : numpy array of datetime64
    out_freq   : str – pandas offset alias (e.g. "1h", "3h", "1D")

    Returns
    -------
    numpy.ndarray of datetime64[ns]
    """
    t0 = pd.Timestamp(times_dt64[0]).ceil(out_freq)
    t1 = pd.Timestamp(times_dt64[-1]).floor(out_freq)
    if t0 > t1:
        return np.array([], dtype='datetime64[ns]')
    target = pd.date_range(t0, t1, freq=out_freq)
    # Keep only times strictly within the input range
    t_lo = pd.Timestamp(times_dt64[0])
    t_hi = pd.Timestamp(times_dt64[-1])
    target = target[(target >= t_lo) & (target <= t_hi)]
    return target.values.astype('datetime64[ns]')


def resample_select(ds, target_times, tolerance):
    """Select input time steps nearest to *target_times* within *tolerance*.

    For each target time the closest input time step is found.  If the
    distance exceeds *tolerance* a UserWarning is emitted and that target
    is skipped.

    Parameters
    ----------
    ds           : xarray.Dataset  (time coord must be datetime64[ns])
    target_times : array of datetime64[ns]
    tolerance    : str – pandas Timedelta string (e.g. "30s", "2min30s")

    Returns
    -------
    xarray.Dataset subset at the matching time steps
    """
    tol_ns   = pd.Timedelta(tolerance).value           # nanoseconds (int)
    times_ns = ds['time'].values.astype('int64')        # ns since epoch

    selected_idxs = []
    missing       = []
    for tt in target_times:
        tt_ns = int(np.datetime64(tt, 'ns').astype('int64'))
        diffs = np.abs(times_ns - tt_ns)
        idx   = int(np.argmin(diffs))
        if diffs[idx] <= tol_ns:
            selected_idxs.append(idx)
        else:
            missing.append(pd.Timestamp(tt))

    if missing:
        warnings.warn(
            f"  [select] {len(missing)} target time(s) not found within "
            f"tolerance '{tolerance}':\n" +
            "\n".join(f"    {t}" for t in missing[:5]) +
            ("\n    ..." if len(missing) > 5 else ""),
            UserWarning, stacklevel=2,
        )

    if not selected_idxs:
        raise ValueError(
            "No input time steps matched any target time.  "
            "Consider using method='interp' or widening select_tolerance."
        )

    return ds.isel(time=selected_idxs)


def resample_interp(ds, target_times):
    """Linearly interpolate all data variables to *target_times*.

    Parameters
    ----------
    ds           : xarray.Dataset  (time coord must be datetime64[ns])
    target_times : array of datetime64[ns]

    Returns
    -------
    xarray.Dataset interpolated at *target_times*
    """
    # xarray converts datetime64 time coords to float for scipy.interp1d.
    # bounds_error=False / fill_value=NaN avoids hard failures when a target
    # time is marginally outside the input range due to floating-point round-off.
    return ds.interp(
        time=target_times,
        method='linear',
        kwargs={'bounds_error': False, 'fill_value': np.nan},
    )


def resample_mean(ds, out_freq):
    """Average all input samples within each output time bin.

    Parameters
    ----------
    ds       : xarray.Dataset  (time coord must be datetime64[ns])
    out_freq : str – pandas offset alias (e.g. "1h", "3h", "1D")

    Returns
    -------
    xarray.Dataset with one time step per output bin
    """
    # label='left' places the output timestamp at the start of each bin
    # (i.e. 00:00 represents the average of 00:00-00:55 for hourly bins).
    # flox is used as the resample engine when available (set via
    # xr.set_options above), which is significantly faster for large ncol grids.
    return ds.resample(time=out_freq, label='left', closed='left').mean(
        skipna=True
    )


# %%
# ---------------------------------------------------------------------------
# Loop over input files – one output file per input file
# ---------------------------------------------------------------------------
for infile in infiles:
    # Extract the YYYY-MM-DD date stamp from the filename using a regex.
    # This is robust to variations in prefix structure and extra fields that
    # post-processed files may have after the date (e.g. time offsets).
    _m = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(infile))
    if _m is None:
        print(f"  WARNING: cannot find a YYYY-MM-DD date in '{os.path.basename(infile)}', skipping.")
        continue
    date_str = _m.group(1)

    print(f"\n{'='*60}")
    print(f"Processing : {os.path.basename(infile)}  (date: {date_str})")

    ds = xr.open_dataset(infile)

    # Sanity-check: variable present (only enforced for proc/cp file types)
    if file_type not in ("raw",) and varname not in ds:
        print(f"  WARNING: '{varname}' not found in {infile}, skipping.")
        ds.close()
        continue

    # ------------------------------------------------------------------
    # Convert time coordinate to numpy datetime64[ns]
    # ------------------------------------------------------------------
    ds_work = ensure_datetime64_time(ds)
    times_dt64 = ds_work['time'].values

    print(f"  Input  n timesteps : {len(times_dt64)}")
    print(f"  Input  time range  : {pd.Timestamp(times_dt64[0])}  –  "
          f"{pd.Timestamp(times_dt64[-1])}")

    # ------------------------------------------------------------------
    # Apply the chosen resampling method
    # ------------------------------------------------------------------
    if resample_method == "select":
        target_times = get_target_times(times_dt64, out_freq_pd)
        if len(target_times) == 0:
            print("  WARNING: no target times fall within the input range, "
                  "skipping.")
            ds.close()
            continue
        ds_out = resample_select(ds_work, target_times, select_tolerance)

    elif resample_method == "interp":
        target_times = get_target_times(times_dt64, out_freq_pd)
        if len(target_times) == 0:
            print("  WARNING: no target times fall within the input range, "
                  "skipping.")
            ds.close()
            continue
        ds_out = resample_interp(ds_work, target_times)

    elif resample_method == "mean":
        ds_out = resample_mean(ds_work, out_freq_pd)

    else:
        raise ValueError(
            f"Unknown resample_method '{resample_method}'. "
            "Choose 'select', 'interp', or 'mean'."
        )

    print(f"  Output n timesteps : {ds_out.sizes['time']}")
    if ds_out.sizes['time'] > 0:
        print(f"  Output time range  : "
              f"{pd.Timestamp(ds_out['time'].values[0])}  –  "
              f"{pd.Timestamp(ds_out['time'].values[-1])}")

    # ------------------------------------------------------------------
    # Update global attributes to document the processing
    # ------------------------------------------------------------------
    ds_out.attrs.update({
        'source_file'     : infile,
        'resample_method' : resample_method,
        'input_frequency' : in_freq_tag,
        'output_frequency': out_freq_tag,
        'processing'      : (
            f"Time-frequency changed from {in_freq_tag} to {out_freq_tag} "
            f"using method='{resample_method}'"
        ),
    })

    # ------------------------------------------------------------------
    # Construct output file name (frequency tag replaced)
    # ------------------------------------------------------------------
    if file_type == "raw":
        out_prefix = f"{icase}.hist.{stats_type}.{out_freq_tag}."
    elif file_type == "cp":
        out_prefix = f"{icase}.cp.{stats_type}.{out_freq_tag}."
    else:
        out_prefix = f"{icase}.{varname}.{stats_type}.{out_freq_tag}."

    out_file = os.path.join(out_dir, f"{out_prefix}{date_str}.nc")

    # Preserve dtype and fill-value encoding from the source file where
    # available, to avoid unintentional precision changes.
    encoding = {}
    for vname in ds_out.data_vars:
        enc = {}
        src_enc = ds[vname].encoding if vname in ds else {}
        if '_FillValue' in src_enc:
            enc['_FillValue'] = src_enc['_FillValue']
        if 'dtype' in src_enc:
            enc['dtype'] = src_enc['dtype']
        if enc:
            encoding[vname] = enc

    # Always suppress the spurious _FillValue that xarray adds to the
    # time coordinate by default.
    encoding['time'] = {'_FillValue': None}

    ds_out.to_netcdf(out_file, encoding=encoding)
    print(f"  Saved  : {out_file}")

    ds.close()
    del ds_out, ds_work

print(f"\n{'='*60}")
print("Done.")

# %%
