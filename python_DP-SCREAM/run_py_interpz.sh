#!/bin/bash 

pydir="/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/python_DP-SCREAM"
pyscript="interpz_DPSCREAM.py"

python ${pydir}/${pyscript} --varname $1 \
        --icase $2 \
        --infile $3 \
        --ifreq $4 \
        --target_z $5

#for testing
# icase="RCE08_dx3km_gpu"
# python ${pydir}/${pyscript} --varname "nc_m3" \
#         --icase ${icase} \
#         --infile "${in_dir}/${icase}.hist.INSTANT.nhours_x1.2000-03-01-03600.nc" \
#         --ifreq "nhours_x1" 


#python interpz_DPSCREAM.py --varname "nc_m3" --icase "RCE02_dx3km_gpu" --infile "RCE02_dx3km_gpu.hist.INSTANT.nhours_x1.2000-02-02-03600.nc" --ifreq "nhours_x1" --target_z 2000
