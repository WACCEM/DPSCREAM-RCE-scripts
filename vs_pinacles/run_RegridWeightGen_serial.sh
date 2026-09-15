#!/bin/bash
set -e

installdir="/global/common/software/m1867/ESMF"
blddir="/global/cfs/cdirs/wcm_code/shared_tools/ESMF/bld"
workdir="/pscratch/sd/k/ksa/sharing/esmf"

tgtsys="pm"
tgtconf="netcdf" #"netcdf-mpi" or "netcdf" or "pnetcdf"
version="v8.1.1"

#Modules --------------------------------------------------------------------
modversion="2024-03"  #use year of major update that module (default) are introduced (INC0182147)
source ${blddir}/load_modules_ESMF_${modversion}.sh

#my binaries --------------------------------------------------------------------
ESMFBIN_PATH=${installdir}/${version}/${tgtsys}-${tgtconf}/bin

export HDF5_USE_FILE_LOCKING=FALSE

#-----------
cd $workdir

pwd

rm -rf PET*.RegridWeightGen.Log


#inres="flextrkr_tropics"
#outres="ERA5_mcs"
#this combination does not work with conserve remapping, no matter what options are provided
#try making and remapping with bilinear -> does not work; successfully finish but weight file is empty

#mapdir="/global/cfs/cdirs/wcm_code/ksa/E3SM/datafiles"
#mapdir="/global/cfs/cdirs/m1867/ksa/wgtFiles"
#mapdir="/global/cfs/cdirs/wcm_shr/ksa/CPTP/regrid"
mapdir="/global/cfs/cdirs/wcm_shr/DP-SCREAM/remap"
#mapdir="/global/cfs/cdirs/m1867/MPASinput/ESMFremapping"


inres="DPSCREAM_RCE_dx1km_600x600km"
outres="PINACLES_YX_dx1km_600x600km"
remap_method="patch"
#remap_method:  bilinear | patch | nearestdtos | neareststod | conserve | conserve2nd

srcfile="${mapdir}/scrip_${inres}.nc"

dstfile="/global/cfs/cdirs/wcm_code/PINACLES/share/remap/scrip_${outres}.nc"

mapfile=${mapdir}/${inres}_to_${outres}_${remap_method}.nc

#capture starting time for log file name
idate=$(date "+%Y-%m-%d-%H%M")

#options="--64bit_offset --check -r " #-> does not work, although the texts are identical
 # --no_log
# -r : specifying that BOTH the source and destination grids are regional grids.  
#      If the argument is not given, the grids are assumed to be global.                
# --src_regional: specifying that the source is a regional grid and the destination is a global grid.
# --dst_regional: specifying that the destination is a regional grid and the source is a global grid.
# --ignore_unmapped :ignore unmapped destination points. 
#If not specified the default is to stop with an error if an unmapped point is found.
#--ignore_degenerate - ignore degenerate cells in the input grids. If not specified the default is to stop with an 
#   error if an degenerate cell is found.
#--extrap_method   - an optional argument specifying which extrapolation method is used to handle unmapped destination locations.
#not supported with conservative remapping
#The value can be one of the following: none, neareststod, nearestidavg, creep
                            # --extrap_method neareststod
#https://earthsystemmodeling.org/docs/release/ESMF_8_0_1/ESMF_refdoc/node3.html#SECTION03020000000000000000
##--ignore_unmapped added to avoid failure due to 
#There exist destination cells (e.g. id=1) which don't overlap with any source cell
#see https://github.com/CDAT/cdms/issues/110    

#echo "${options}"

#generate mapping file
echo "running  $ESMFBIN_PATH/ESMF_RegridWeightGen"

#$ESMFBIN_PATH/ESMF_RegridWeightGen --ignore_unmapped -s $srcfile -d $dstfile -w $mapfile -m $remap_method 

$ESMFBIN_PATH/ESMF_RegridWeightGen -s $srcfile -d $dstfile -w $mapfile -m $remap_method  \
     --src_regional --dst_regional --extrap_method neareststod #--ignore_unmapped

#$ESMFBIN_PATH/ESMF_RegridWeightGen --ignore_unmapped -s $srcfile -d $dstfile -w $mapfile -m $remap_method  \
#    --src_regional --dst_regional --src_loc center --dst_loc center 
#--src_loc center --dst_loc center --src_type ESMF --dst_type SCRIP --ignore_degenerate 
#--dst_regional