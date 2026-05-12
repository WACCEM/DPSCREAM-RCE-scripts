#!/usr/bin/env python3
"""Helper utility to check which SCREAM output stream contains a given variable."""

import warnings
import re
import yaml
from pathlib import Path

# Default paths to the output YAML files
_YAML_DIR = Path(__file__).parent.parent / "run_scripts" / "yaml_files"
_AVG_YAML  = _YAML_DIR / "scream_new_output_avg_5min.yaml"
_INST_YAML = _YAML_DIR / "scream_new_output_inst_5min.yaml"


def _get_field_names(yaml_path):
    """Return the set of active (non-commented) field names from a SCREAM output YAML."""
    with open(yaml_path, "r") as fh:
        config = yaml.safe_load(fh)
    names = set()
    fields = config.get("fields", {})
    for section in fields.values():
        for name in section.get("field_names", []):
            names.add(name)
    return names


def get_output_stream(varname, avg_yaml=_AVG_YAML, inst_yaml=_INST_YAML):
    """
    Check which SCREAM output stream contains *varname*.

    Parameters
    ----------
    varname : str
        Variable name to look up.
    avg_yaml : path-like, optional
        Path to the average-output YAML file.
    inst_yaml : path-like, optional
        Path to the instant-output YAML file.

    Returns
    -------
    str
        "AVERAGE"  - found only in the average output file.
        "INSTANT"  - found only (or also) in the instant output file.
        "NONE"     - not found in either file.
    """
    avg_vars  = _get_field_names(avg_yaml)
    inst_vars = _get_field_names(inst_yaml)

    # First try an exact match; if not found, strip the height-interpolated
    # suffix "_YYYm" (2-5 digits) added by zinterp_concat_DPSCREAM.py,
    # e.g. "T_mid_200m" -> "T_mid".  Exact match takes priority so that
    # variables like "T_2m", "qv_2m", "wind_speed_10m" are found as-is.
    if varname in avg_vars or varname in inst_vars:
        lookup = varname
    else:
        lookup = re.sub(r"_\d{2,5}m$", "", varname)

    in_avg  = lookup in avg_vars
    in_inst = lookup in inst_vars

    if in_avg and in_inst:
        warnings.warn(
            f"the variable {varname} is found in both output streams",
            stacklevel=2,
        )
        return "INSTANT"
    elif in_inst:
        return "INSTANT"
    elif in_avg:
        return "AVERAGE"
    else:
        return "NONE"


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python check_output_stream.py <varname>")
        sys.exit(1)
    result = get_output_stream(sys.argv[1])
    print(result)
