#!/bin/bash
# Wrapper script to run check_ncni_RCEMIP.py

# Load the Python module and activate the dpscream_analysis conda environment
module load python
conda activate dpscream_analysis

pydir="/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/python_DP-SCREAM"
pyscript="check_ncni_RCEMIP.py"

echo "Running script: ${pydir}/${pyscript}"
echo "Note: The script is now configured via the User Configuration section within the Python file itself."
python ${pydir}/${pyscript}
