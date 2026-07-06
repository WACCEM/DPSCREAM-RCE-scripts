#!/bin/bash 

pydir="/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/python_DP-SCREAM"
pyscript="calc_havg_col_DPSCREAM.py"

python ${pydir}/${pyscript} --varname $1 \
        --icase $2 \
        --infile $3 \
        --ifreq $4  \
        --stats_type $5

#for testing
# icase="RCE10_dx3km_gpu"
# in_dir="/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/RCE10_dx3km_gpu/run"
# python ${pydir}/${pyscript} --varname "T_mid" \
#         --icase ${icase} \
#         --infile "${in_dir}/${icase}.hist.INSTANT.nhours_x1.2000-01-02-03600.nc" \
#         --ifreq "nhours_x1" 