#!/bin/bash 
#SBATCH -N 1
#SBATCH -q debug
#SBATCH -t 00:30:00
#SBATCH -J orgind_parallel
#SBATCH --exclusive
#SBATCH -C cpu
#SBATCH -A m1867
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=Koichi.Sakaguchi@pnnl.gov

date

module load python
conda activate dpscream_analysis

pydir="/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/organization_indices"
pyscript="compute_orgind_parallel.py"

echo "Running compute_orgind_parallel.py..."
python ${pydir}/${pyscript}

echo "Done"
date

# salloc --nodes 1 --qos interactive --time 00:30:00 --constraint cpu --account m1867
