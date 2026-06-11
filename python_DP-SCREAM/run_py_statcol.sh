#!/bin/bash 

pydir="/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/python_DP-SCREAM"
pyscript="calc_statcol_DPSCREAM.py"

python ${pydir}/${pyscript} --varname $1 \
        --stat_type $2  \
        --icase $3 \
        --infile $4 \
        --ifreq $5 \

#for testing
# icase="RCE08_dx3km_gpu"
# python ${pydir}/${pyscript} --varname "nc_m3" \
#         --stat_type "min"  \
#         --icase ${icase} \
#         --infile "${in_dir}/${icase}.hist.INSTANT.nhours_x1.2000-03-01-03600.nc" \
#         --ifreq "nhours_x1" 