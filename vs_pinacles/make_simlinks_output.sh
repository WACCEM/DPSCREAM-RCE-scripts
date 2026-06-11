#!/bin/bash
set -e
#create symlinks for output files across different slurm jobs, since PINACLES creates new directories for each job

icase="RCE03_150x150_1km"
icase_prefix="RCE03_150x150_1km"
tgtoutput="fields2d"

indir_root="/pscratch/sd/k/ksa/simulation/PINACLES/rce/test_runs2"
#indir_root="/pscratch/sd/p/paccini/test_runs"

outdir="/pscratch/sd/w/wcmca1/PINACLES/rce/${icase}/simlinks/${tgtoutput}"

mkdir -p ${outdir}


#cd ${indir_root}/${icase}_root
cd ${indir_root}/${icase}
pwd

for rundir in $(ls -d ${icase_prefix}*/); do
    echo "processing ${rundir}"
    ln -sf ${indir_root}/${icase}/${rundir}/${tgtoutput}/*h5 ${outdir}/

    #pwd
    # for file in $(ls *.h5); do
    #     ln -sf ${file} ${outdir}/${file}
    # done
done
