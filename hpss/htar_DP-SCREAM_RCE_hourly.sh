#! /bin/bash
# exit when any command fails
#set -e
#https://intoli.com/blog/exit-on-errors-in-bash-scripts/

#use tmux session "hpss_dpscream" to run this script
#tmux new -s hpss_dpscream
#Ctrl+b, then d  #detach
#tmux ls
#tmux attach -t hpss_dpscream

icase="RCE02_dx1km_gpu"  #experiment case name

indir="/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/${icase}/run" 
archdir="/home/projects/m1867/RCE/DP-SCREAM/${icase}"
#archdir="/home/projects/m1867/RCE/DP-SCREAM/testruns/${icase}"

testdir="/pscratch/sd/k/ksa/temp/htar_checksum"
logdir="/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/hpss/htar_log"
scripts_dir="/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/${icase}/case_scripts"

#control boolean variables
save_inst=true

save_avg=true

save_restart=true

save_script=true

#save_havg=false  #not yet implemented in this script.

iyear=2000
months=(01 02 03)

echo "Creating HPSS archive directory if it doesn't exist..."
hsi "mkdir -p ${archdir}"

#inst history files  -----------------------------------------------------------
if [ "$save_inst" = true ]; then
    cd $indir 

    for imo in "${months[@]}"
    do
        # Skip months if all matching files are symbolic links
        files=(./${icase}.hist.INSTANT.*.${iyear}-${imo}*.nc)
        all_symlinks=true
        for f in "${files[@]}"; do
            if [ -f "$f" ] && [ ! -L "$f" ]; then
                all_symlinks=false
                break
            fi
        done
        if [ "$all_symlinks" = true ]; then
            echo "skipping ${iyear}-${imo}: all files are symbolic links or no files found"
            continue
        fi

        echo "archiving inst history files for ${iyear}-${imo}"    
        archname="${icase}_${iyear}-${imo}_hist_inst.tar" 
        htar -Hcrc -cf ${archdir}/${archname} ./${icase}.hist.INSTANT.*.${iyear}-${imo}*.nc \
        >| ${logdir}/htar_${archname}.log

        errcode=$?
        if [ "$errcode" -ne 0 ]; then
            echo "htar failed for ${archname}"
            exit 20
        else
            echo "htar success for ${archname}"
        fi  
    done          
            
else
    echo "skipping inst files"
    
fi

#avg history files -----------------------------------------------------------
if [ "$save_avg" = true ]; then
    cd $indir 

    for imo in "${months[@]}"
    do
        # Skip months if all matching files are symbolic links
        files=(./${icase}.hist.AVERAGE.*.${iyear}-${imo}*.nc)
        all_symlinks=true
        for f in "${files[@]}"; do
            if [ -f "$f" ] && [ ! -L "$f" ]; then
                all_symlinks=false
                break
            fi
        done
        if [ "$all_symlinks" = true ]; then
            echo "skipping ${iyear}-${imo}: all files are symbolic links or no files found"
            continue
        fi

        echo "archiving avg history files for ${iyear}-${imo}"    
        archname="${icase}_${iyear}-${imo}_hist_avg.tar" 
        htar -Hcrc -cf ${archdir}/${archname} ./${icase}.hist.AVERAGE.*.${iyear}-${imo}*.nc \
        >| ${logdir}/htar_${archname}.log

        errcode=$?
        if [ "$errcode" -ne 0 ]; then
            echo "htar failed for ${archname}"
            exit 20
        else
            echo "htar success for ${archname}"
        fi  
    done
            
else
    echo "skipping avg files"
    
fi

#restart files -----------------------------------------------------------
if [ "$save_restart" = true ]; then
    echo "archiving restart files"
    cd $indir
    for imo in "${months[@]}"
    do
        for interval in "01 10" "11 20" "21 31"; do
            start_day=${interval% *}
            end_day=${interval#* }
            selected_day=""
            
            for (( d=10#$start_day; d<=10#$end_day; d++ )); do
                iday=$(printf "%02d" $d)
                for f in ./${icase}.cpl.r.${iyear}-${imo}-${iday}*.nc; do
                    if [ -e "$f" ]; then
                        selected_day=$iday
                        break 2
                    fi
                done
            done
            
            if [ -n "$selected_day" ]; then
                iday=$selected_day
                archname="${icase}_${iyear}-${imo}-${iday}_restart.tar" 
                echo "archiving restart files for ${iyear}-${imo}-${iday}"
                htar -Hcrc -cf ${archdir}/${archname} ./${icase}.cpl.r.${iyear}-${imo}-${iday}*.nc \
                     ./${icase}.docn.rs1.${iyear}-${imo}-${iday}*.bin  \
                     ./${icase}.hist.rhist.AVERAGE.*.${iyear}-${imo}-${iday}*.nc \
                     ./${icase}.hist.rhist.INSTANT.*.${iyear}-${imo}-${iday}*.nc \
                     ./${icase}.scream.r.INSTANT.*.${iyear}-${imo}-${iday}*.nc \
                     ./rpointer* # >| ${logdir}/htar_${archname}.log
            else
                echo "No restart files found for ${iyear}-${imo} between days ${start_day} and ${end_day}"
            fi
        done
    done
else
    echo "skipping restart files"
        
fi

#case scripts -----------------------------------------------------------
if [ "$save_script" = true ]; then
    echo "archiving case scripts"

    cd "$(dirname "$scripts_dir")"
    archname="${icase}_case_scripts.tar"
    htar -Hcrc -cf "${archdir}/${archname}" case_scripts >| "${logdir}/htar_${archname}.log"

    errcode=$?
    if [ "$errcode" -ne 0 ]; then
        echo "htar failed for ${archname}"
    else
        echo "htar success for ${archname}"
    fi
else
    echo "skipping case scripts"
fi

echo "done"
