#!/bin/bash

module load python
conda activate ncl


inres="DPSCREAM_RCE_dx1km_600x600km"  
outres="PINACLES_YX_dx1km_600x600km"
remap="patch"
inres_col=true # true for unstructured grids with column dimension


mapdir="/global/cfs/cdirs/wcm_shr/DP-SCREAM/remap"

indir="/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/scream_cpu_dpxx_RCE_dx1km/processed"
outdir=$indir
#outdir="/global/cscratch1/sd/ksa/simulation/MPAS/$pcase/$outres"

infile="scream_cpu_dpxx_RCE_dx1km.cp.INSTANT.nmins_x5.2000-02-01-00000.nc"
outfile="scream_cpu_dpxx_RCE_dx1km.cp.INSTANT.nmins_x5_remap.2000-02-01-00000.nc"
mapfile=${mapdir}/${inres}_to_${outres}_${remap}.nc

mkdir -p ${outdir}

cd ${indir}

pwd

#ncks -O -6 --map=$mapfile $infile $outfile
if [[ "$inres_col" == true ]]; then
    echo ncks -O --rgr col_nm=ncol --map=$mapfile $infile ${outdir}/$outfile
else
    echo ncks -O --map=$mapfile $infile ${outdir}/$outfile
fi
#option -6  forces output to the legacy 64-bit offset format, but causing an error

echo "done"
