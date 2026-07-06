#!/bin/bash
set -e
#create symlinks for output files across different slurm jobs, since PINACLES creates new directories for each job

icase="RCE00_dx1km_600x600km"
icase_prefix="RCE_600x600_1km"
tgtoutput="fields2d"

indir_root="/pscratch/sd/k/ksa/simulation/PINACLES/rce/1km/${icase}"
#indir_root="/pscratch/sd/k/ksa/simulation/PINACLES/rce/test_runs2"
#indir_root="/pscratch/sd/p/paccini/test_runs"
#indir_root="/pscratch/sd/w/wcmca1/PINACLES/rce/${icase}"

outdir="/pscratch/sd/w/wcmca1/PINACLES/rce/${icase}/simlinks/${tgtoutput}"

mkdir -p ${outdir}


#cd ${indir_root}/${icase}_root
cd ${indir_root}
pwd

for rundir in $(ls -d ${icase_prefix}*/); do
    echo "processing ${rundir}"
    ln -sf ${indir_root}/${rundir}/${tgtoutput}/*h5 ${outdir}/

    #pwd
    # for file in $(ls *.h5); do
    #     ln -sf ${file} ${outdir}/${file}
    # done
done
