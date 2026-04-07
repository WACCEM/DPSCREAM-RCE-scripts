#!/bin/bash
# Run regrid_dpxx_output.py with ESMF weight-based regridding for the test case.
#
# Source data:
#   /pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/
#     test_regrid_cpu_dpxx_RCE_dx1km/run/
#     test_regrid_cpu_dpxx_RCE_dx1km.hist.INSTANT.nmins_x5.2000-01-01-00000.nc
#
# Weight file:
#   /global/cfs/cdirs/wcm_shr/DP-SCREAM/remap/
#     DPSCREAM_RCE_dx1km_600x600km_to_PINACLES_YX_dx1km_600x600km_conserve.nc

set -e

# ---- Load environment ------------------------------------------------
module load python
conda activate mpas_2025-10

# ---- Paths -----------------------------------------------------------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ORIG_SCRIPT="${SCRIPT_DIR}/regrid_dpxx_output.py"
TMP_SCRIPT="/tmp/regrid_dpxx_output_ksa_test.$$.py"

# ---- Patch user-input settings on the fly ----------------------------
# Read the original script, swap the five user-input variables, write a
# temporary copy, execute it, then remove it.
python3 - "${ORIG_SCRIPT}" "${TMP_SCRIPT}" <<'PATCHEOF'
import sys

orig    = sys.argv[1]
patched = sys.argv[2]

replacements = [
    ("casedir='/pscratch/sd/b/bogensch/dp_screamxx/'",
     "casedir='/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/'"),
    ("casename='scream_dpxx_GATEIDEAL.3.2km.003a'",
     "casename='test_regrid_cpu_dpxx_RCE_dx1km'"),
    ("outstream='scream_dpxx_GATEIDEAL.3.2km.003a.scream.hourly.avg.AVERAGE.nhours_x1'",
     "outstream='test_regrid_cpu_dpxx_RCE_dx1km.hist.INSTANT.nmins_x5.2000-01-01-00000'"),
    ("use_esmf_weights = False",
     "use_esmf_weights = True"),
    # Destination grid: PINACLES_YX_dx1km_600x600km -> 600 pts x 1000 m = 600 km
    ("dst_dx = 1500.0",
     "dst_dx = 1000.0"),
]

with open(orig, 'r') as f:
    content = f.read()

for old, new in replacements:
    if old not in content:
        print(f"ERROR: could not find string to replace:\n  {old}", file=sys.stderr)
        sys.exit(1)
    content = content.replace(old, new, 1)

with open(patched, 'w') as f:
    f.write(content)

print(f"Patched script written to: {patched}")
PATCHEOF

# ---- Run the patched script ------------------------------------------
echo "Running regrid with ESMF weights..."
python3 "${TMP_SCRIPT}"

# ---- Clean up --------------------------------------------------------
rm -f "${TMP_SCRIPT}"
echo "Done."
