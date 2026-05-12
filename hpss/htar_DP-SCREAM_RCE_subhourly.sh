#! /bin/bash
# exit when any command fails
#set -e
#https://intoli.com/blog/exit-on-errors-in-bash-scripts/

#use tmux session "hpss_dpscream" to run this script
#tmux new -s hpss_dpscream
#Ctrl+b, then d
#tmux ls
#tmux attach -t hpss_dpscream

icase="scream_cpu_dpxx_RCE_dx1km"  #experiment case name

indir="/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases/${icase}/run" 
archdir="/home/projects/m1867/RCE/DP-SCREAM/${icase}"
testdir="/pscratch/sd/k/ksa/temp/htar_checksum"
logdir="/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/hpss/htar_log"


save_inst=true

save_avg=true

save_havg=false  #not yet implemented in this script.

#default 55 levels 4-32km restart and history files too large for htar command
#hsi "cd ${archdir}; cput -R ${icase}"
save_restart=true

iyear=2000
months=(02) 


#inst history files  -----------------------------------------------------------
if [ "$save_inst" = true ]; then
    cd $indir 

    for imo in "${months[@]}"
    do
        # Determine number of days in month (no leap days)
        case $imo in
            01|03|05|07|08|10|12) ndays=31 ;;
            04|06|09|11)          ndays=30 ;;
            02)                   ndays=28 ;;
        esac

        for iday in $(seq -w 1 $ndays)
        do
            # Skip day if all matching files are symbolic links
            files=(./${icase}.hist.INSTANT.*.${iyear}-${imo}-${iday}*.nc)
            all_symlinks=true
            for f in "${files[@]}"; do
                if [ -f "$f" ] && [ ! -L "$f" ]; then
                    all_symlinks=false
                    break
                fi
            done
            if [ "$all_symlinks" = true ]; then
                echo "skipping ${iyear}-${imo}-${iday}: all files are symbolic links or no files found"
                continue
            fi

            echo "archiving inst history files for ${iyear}-${imo}-${iday}"    
            archname="${icase}_${iyear}-${imo}-${iday}_hist_inst.tar" 
            htar -Hcrc -cf ${archdir}/${archname} ./${icase}.hist.INSTANT.*.${iyear}-${imo}-${iday}*.nc \
            >| ${logdir}/htar_${archname}.log

            errcode=$?
            if [ "$errcode" -ne 0 ]; then
                echo "htar failed for ${archname}"
                exit 20
            else
                echo "htar success for ${archname}"
            fi  
        done
    done          
            
else
    echo "skipping inst files"
    
fi

#avg history files -----------------------------------------------------------
if [ "$save_avg" = true ]; then
    cd $indir 

    for imo in "${months[@]}"
    do
        # Determine number of days in month (no leap days)
        case $imo in
            01|03|05|07|08|10|12) ndays=31 ;;
            04|06|09|11)          ndays=30 ;;
            02)                   ndays=28 ;;
        esac

        for iday in $(seq -w 9 $ndays)
        do
            # Skip day if all matching files are symbolic links
            files=(./${icase}.hist.AVERAGE.*.${iyear}-${imo}-${iday}*.nc)
            all_symlinks=true
            for f in "${files[@]}"; do
                if [ -f "$f" ] && [ ! -L "$f" ]; then
                    all_symlinks=false
                    break
                fi
            done
            if [ "$all_symlinks" = true ]; then
                echo "skipping ${iyear}-${imo}-${iday}: all files are symbolic links or no files found"
                continue
            fi

            echo "archiving avg history files for ${iyear}-${imo}-${iday}"    
            archname="${icase}_${iyear}-${imo}-${iday}_hist_avg.tar" 
            htar -Hcrc -cf ${archdir}/${archname} ./${icase}.hist.AVERAGE.*.${iyear}-${imo}-${iday}*.nc \
            >| ${logdir}/htar_${archname}.log

            errcode=$?
            if [ "$errcode" -ne 0 ]; then
                echo "htar failed for ${archname}"
                exit 20
            else
                echo "htar success for ${archname}"
            fi  
        done
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
        for iday in 01 10 20 30
        do
            archname="${icase}_${iyear}-${imo}-${iday}_restart.tar" 
            echo "archiving restart files for ${iyear}-${imo}-${iday}"
            htar -Hcrc -cf ${archdir}/${archname} ./${icase}.cpl.r.${iyear}-${imo}-${iday}*.nc \
                 ./${icase}.docn.rs1.${iyear}-${imo}-${iday}*.bin  \
                 ./${icase}.hist.rhist.AVERAGE.*.${iyear}-${imo}-${iday}*.nc \
                 ./${icase}.hist.rhist.INSTANT.*.${iyear}-${imo}-${iday}*.nc \
                 ./${icase}.scream.r.INSTANT.*.${iyear}-${imo}-${iday}*.nc \
                 ./rpointer* # >| ${logdir}/htar_${archname}.log
        done
    done
else
    echo "skipping restart files"
        
fi

echo "done"
