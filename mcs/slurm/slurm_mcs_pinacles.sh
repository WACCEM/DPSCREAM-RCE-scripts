#!/bin/bash
#SBATCH -A m1867
#SBATCH -J mcs_PINACLES
#SBATCH -t 00:30:00
#SBATCH -q debug
#SBATCH -C cpu
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=128
#SBATCH --exclusive
#SBATCH --output=slurm_mcs_%j.out
#SBATCH --mail-type=END
#SBATCH --mail-user=Koichi.Sakaguchi@pnnl.gov

config_file="/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/mcs/config/config_ccs_olr_PINACLES.yml"
# Extract databasename from config file and strip trailing '.mcstrack.' or '.'
db_name=$(awk -F': *' '/^databasename:/ {print $2}' "${config_file}" | sed -e 's/[[:space:]]*#.*//' -e 's/\.mcstrack\.*$//' -e 's/\.$//')
log_file="log_mcs_${db_name}.log"

# Redirect all stdout and stderr to the case-specific log file
exec > "${log_file}" 2>&1

date

module load python
conda activate flextrkr

# Run Python
script_path="/global/cfs/cdirs/wcm_code/ksa/MCS/PyFLEXTRKR/runscripts"

python ${script_path}/run_mcs_tbpf_saag.py ${config_file}

date

# salloc --nodes 1 --qos interactive --time 00:30:00 --constraint cpu --account m1867
