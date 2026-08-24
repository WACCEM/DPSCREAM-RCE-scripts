#!/bin/bash 
#SBATCH -N 1
##SBATCH -q regular
##SBATCH -t 02:00:00
#SBATCH -q debug
#SBATCH -t 00:30:00
#SBATCH -J havgcol
#SBATCH --exclusive
#SBATCH -A m1867
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=Koichi.Sakaguchi@pnnl.gov
##SBATCH -L SCRATCH,project
#SBATCH -C cpu

date

module load python
conda activate dpscream_analysis

pydir="/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/python_DP-SCREAM"

icase="dx1km_L150km_RCE02_gpu"
ifreq="nhours_x1"
indir="/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/${icase}/run"
istat="INSTANT"  #need to add the --stats_type=$istat option for the AVERAGE history file (default is INSTANT)
varname="qc"  #"RelativeHumidity"  #"T_mid"
#istat="AVERAGE"  #need to add the --stats_type=$istat option for the AVERAGE history file (default is INSTANT)
#varname="rrtmgp_T_mid_tend"
ihist="hist.${istat}.${ifreq}"

# Define output time range
iyear=2000
stmon=1
stday=1

edmon=4
edday=30

stmonp=$(printf "%02d" $stmon)
stdayp=$(printf "%02d" $stday)
edmonp=$(printf "%02d" $edmon)
eddayp=$(printf "%02d" $edday)

runscript="run_py_havg_col.sh"

#strip the file extension from runscript for naming input and log files
inputfile="${runscript%.*}_${icase}_${stmonp}${stdayp}-${edmonp}${eddayp}.txt"
logfile="${runscript%.*}_${icase}_${stmonp}${stdayp}-${edmonp}${eddayp}.log"

rm -rf $inputfile

echo "starting"

# Days per month — noleap calendar (no leap year needed)
days_in_month=(0 31 28 31 30 31 30 31 31 30 31 30 31)

for imon in $(seq $stmon $edmon); do
    last_day=${days_in_month[$imon]}

    if [ $imon -eq $stmon ] && [ $imon -eq $edmon ]; then
        day_start=$stday
        day_end=$edday
    elif [ $imon -eq $stmon ]; then
        day_start=$stday
        day_end=$last_day
    elif [ $imon -eq $edmon ]; then
        day_start=1
        day_end=$edday
    else
        day_start=1
        day_end=$last_day
    fi

    for iday in $(seq $day_start $day_end); do
        imonp=$(printf "%02d" $imon)
        idayp=$(printf "%02d" $iday)
        for f in ${indir}/${icase}.${ihist}.${iyear}-${imonp}-${idayp}*.nc; do
            echo "${varname} ${icase} ${f} ${ifreq} ${istat}" >> ${inputfile}
        done
    done
done

echo "${inputfile} created"
#more ${inputfile}

echo "starting parallel processing"
# --jobs 32: memory-limited by calc_imse peak RSS (~17 GB/job) on a 512 GB --exclusive node.
# floor(512 GB / 17 GB) = 30; use 28 to leave headroom for OS and NumPy buffers.
# Do NOT raise above 32 on 512 GB nodes or above 4 for interactive login-node testing.
parallel --jobs 12 --colsep ' ' -a ${inputfile} ${pydir}/${runscript} {1} {2} {3} {4} {5} > ${logfile} 2>&1

echo "done"
echo "Parallel processing logs saved to: ${logfile}"
date

# salloc --nodes 1 --qos interactive --time 00:30:00 --constraint cpu --account m1867
