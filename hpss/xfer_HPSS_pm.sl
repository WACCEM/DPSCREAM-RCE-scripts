#!/bin/bash
#SBATCH -A m1867
#SBATCH -q xfer
#SBATCH -t 20:00:00
#SBATCH -J htar_mpas
##SBATCH -L SCRATCH  #does not work. Gives an error
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=koichi.sakaguchi@pnnl.gov
##SBATCH --mem=15G
#SBATCH -C cron


pwd

#capture starting time for log file name
idate=$(date "+%Y-%m-%d-%H%M")


#./htar_xf_MPAS_runs.sh >| ./htar_log/htar_${idate}.log

./htar_MPAS_runs_highres_months.sh >| ./htar_log/htar_${idate}.log


#------- loop over different simulations (cases) -------
#caselist=("ctr_v7.3" "cp_wsm6" "cp_ysu" "meso_v7.3")
#caselist=("mcs-la02_v8_0_1")

# for icase in "${caselist[@]}"
# do 
    
#     echo "archiving processed files in ${icase}"

#     ./htar_MPAS_runs_highres_months.sh  >| htar_${icase}_${idate}.log
#     #./htarbatch_MPAS_runs_tropicalchannel_processed.sh ${icase} >| ./logs/htar_processed_${icase}_${idate}.log

#     # use #SBATCH -M escori instead of loading the esslurm module
#     #check job status by this command:
#     #squeue -M escori -u ksa


# done
