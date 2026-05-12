#!/bin/bash
set -e
#need to use e3sm unified environment, and 
#source /global/common/software/e3sm/anaconda_envs/load_latest_e3sm_unified_pm-cpu.sh
#better run the above line outside of this script to avoid issues
#e.g., /global/homes/p/paullric/ncvis/export: Permission denied.
#######################################################################
#######################################################################
#######  Script to run SCREAMv1 in doubly periodic (DP) mode (DP-EAMxx)
#######  RCE_300K
#######  Radiative Convective Equilibrium (RCEMIP1 configuration; Wing et al. 2018)
#######  Can run with SSTs set to 295, 300 (default), or 305 K.
#######  To change, modify the IOP file name and sst_val accordingly (in case specific settings).
#######  It is possible to run with other SST values, but will take longer for simulation to equilibrate.
#######
#######  Script Author: P. Bogenschutz (bogenschutz1@llnl.gov)
#######
#######  IMPORTANT:
#######    - You should now be using E3SM master.  The SCREAM and E3SM repos
#######      have merged and here-on-out all SCREAM development will take place
#######      on the E3SM master.
#######

#######################################################
#######  BEGIN USER DEFINED SETTINGS
####### NOTE: beyond this section you will need to configure your
#######  ouput yaml file(s).  Please do a search for "yamlpath" and you will
#######  be brought to the correct locations.
####### See the example yaml file in the DPxx_SCREAM_SCRIPTS/yaml_file_example
#######  of the scmlib repo to get you started.
export CIME_MODEL=e3sm
# Set the name of your case here
export casename=RCE01_dx3km_gpu

# Set the case directory here
export casedirectory=/pscratch/sd/k/ksa/simulation/DP-SCREAM/cases

# Directory where code lives
export code_dir=/global/cfs/cdirs/wcm_code/ksa/E3SM/model/

# Code tag name
export code_tag=E3SM

# Name of machine you are running on (i.e. pm-cpu, anvil, etc)
export machine=pm-gpu

# Compiler (pm-cpu should use "gnu"; pm-gpu should use "gnugpu"; LC should use "intel";
#           frontier should use "craycray-mphipcc")
#   more machine compiler defaults will be added as they are tested/validated.
export compiler=gnugpu

# Name of project to run on, if submitting to queue
export projectname=m1867

# Path where output YAML files are located (i.e. where you specify your output streams)
#  See example files in DPxx_SCREAM_SCRIPTS/yaml_file_example to get you started.
# NOTE, you will likely need to edit the section of the script where the yaml files
#  are appended to your case.  Do a search for "yamlpath" to find this location.
export yamlpath=/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/run_scripts/yaml_files


# Set to debug queue?
# - Some cases are small enough to run on debug queues
# - Setting to true only supported for NERSC and Livermore Computing,
#   else user will need to modify script to submit to debug queue
export debug_queue=true

# Set number of processors to use, should be less than or equal
#   to the total number of elements in your domain.  Note that if you are running
#   on pm-gpu you will want to set this to either "4" or "8" if running the standard
#   domain size and resolution (RCE excluded).
num_procs=16
# based on the table "supported PECOUNTS", the value for ne30pg2_ne30pg2
#https://e3sm.atlassian.net/wiki/spaces/DOC/pages/3386015745/How+To+Run+EAMxx+SCREAMv1

stop_option=ndays
stop_n=5

# set walltime
walltime='00:30:00'

## SET DOMAIN SIZE AND DYNAMICS RESOLUTION:
# - Note that these scripts are set to run with dx=dy=3.33 km
# which is the default SCREAM resolution.

# To estimate dx (analogous for dy):
# dx = domain_size_x / (num_ne_x * 3)
# (there are 3x3 unique dynamics columns per element, hence the "3" factor)

# Set number of elements in the x&y directions
num_ne_x=60
num_ne_y=60

# Set domain length [m] in x&y direction
domain_size_x=600000
domain_size_y=600000

# BELOW SETS RESOLUTION DEPENDENT SETTINGS
# (Note that all default values below are appropriate for dx=dy=3.33 km and do not
#  need to be modified if you are not changing the resolution)

# SET MODEL TIME STEPS
#  -NOTE that if you change the model resolution,
#  it is likely the physics and dynamics time steps will need to be adjusted.
#  See below for guidance on how to adjust both.

# model/physics time step [s]:
#  As a rule, a factor of 2 increase in resolution should equate to a factor of 2
#  decrease of the model/physics step.  This needs to be an integer number.
model_dtime=100

# dynamics time step [s]:
#  should divide evenly into model_dtime.  As a general rule of thumb, divide
#   model_dtime by 12 to get your dynamics time step.
dyn_dtime=8.3333333333333

# SET SECOND ORDER VISCOSITY NEAR MODEL TOP
#  NOTE that if you decrease resolution you will also need to reduce
#  the value of "nu_top" (second-order viscosity applied only near model top).
#  Rule of thumb is that a factor of 2 increase in resolution should equate to a
#  factor of 2 decrease for this value

# second order visocosity near model top [m2/s]
nu_top_dyn=1e4

submitter_email="Koichi.Sakaguchi@pnnl.gov"

#-switches to run/not to run CESM scripts  -----------------------------------
run_setup=false        #case.setup 
clean_setup=false


run_build=false       #./case.build
clean_build=false

edit_output=true
#./atmchange to edit output options (e.g., compute tendencies for output, add yaml output files, etc)

edit_build=false
edit_domain=false
edit_jobconf=false
edit_atmconf=false

do_continue_run=TRUE
 # whether to continue a run by writing CONTINUE_RUN=TRUE in env_run.xml.  If true, also need to set the number of model time steps to run (ncpl) below.
num_resubmit=25
#-submit a job
run_job=true

####### END (mandatory) USER DEFINED SETTINGS, but see above about output
###########################################################################
###########################################################################
###########################################################################

# Case specific information kept here
  lat=0.0 # latitude
  lon=0.0 # longitude
  do_iop_srf_prop=false # Use surface fluxes in IOP file?
  do_iop_nudge_tq=false # Relax T&Q to observations?
  do_iop_nudge_uv=false # Relax U&V to observations?
  do_iop_nudge_coriolis=false # Nudge to geostrophic winds?
  do_iop_subsidence=true # compute LS vertical transport?

  startdate=2000-01-01 # Start date in IOP file
  start_in_sec=0 # start time in seconds in IOP file


  sst_val=300 # set constant SST value (ONLY valid for RCE case)
  iop_file=RCE_300K_iopfile_4scam.nc #IOP file name
  do_turnoff_swrad=false # Turn off SW calculation (if false, keep false)

# End Case specific stuff here

  # Location of IOP file
  iop_path=atm/cam/scam/iop

  PROJECT=$projectname
  E3SMROOT=${code_dir}/${code_tag}
  echo "E3SM root: $E3SMROOT"

  # Verify the required branch is checked out before proceeding
  required_branch="ksa/uvwinds"
  current_branch=$(git -C "${E3SMROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null)
  if [[ "${current_branch}" != "${required_branch}" ]]; then
      echo "ERROR: E3SM source code is on branch '${current_branch}'," \
           "but '${required_branch}' is required."
      echo "       Run: git -C ${E3SMROOT} checkout ${required_branch}"
      exit 1
  fi
  echo "Confirmed E3SM branch: ${current_branch}"

  compset=FRCE-SCREAMv1-DP

  # Note that in DP-SCREAM the grid is set ONLY to initialize
  #  the model from these files
  grid=ne30pg2_ne30pg2

  CASEID=$casename

  CASEDIR=${casedirectory}/$CASEID

  run_root_dir=$CASEDIR
  case_scripts_dir=$run_root_dir/case_scripts
  case_build_dir=$run_root_dir/build
  case_run_dir=$run_root_dir/run

if [[ ! -d $case_scripts_dir ]]; then   # Create new case
    echo "changing into E3SM cime scripts directory to create case"
    cd $E3SMROOT/cime/scripts
    pwd
echo "Create new case"
    ./create_newcase -case $casename --script-root $case_scripts_dir -mach $machine -project $PROJECT -compset $compset -res $grid --compiler $compiler
fi

echo "changing into case scriptdirectory to edit settings"
cd $case_scripts_dir

echo "Editing xml files"

  
if [[ $edit_build == 'true' ]]; then
  ./xmlchange SCREAM_CMAKE_OPTIONS="$(./xmlquery -value SCREAM_CMAKE_OPTIONS | sed 's/SCREAM_NUM_VERTICAL_LEV [0-9][0-9]*/SCREAM_NUM_VERTICAL_LEV 128/')"  

# Define executable and run directories
  ./xmlchange --id EXEROOT --val "${case_build_dir}"
  ./xmlchange --id RUNDIR --val "${case_run_dir}"
  ./xmlchange --id DEBUG --val FALSE

fi

# Set queue to debug, only on certain machines
  if [[ $debug_queue == 'true' ]]; then
    if [[ $machine == pm* ]]; then
      ./xmlchange --id JOB_QUEUE --val 'debug'
    fi

    if [[ $machine == 'quartz' || $machine == 'syrah' || $machine == 'ruby' ]]; then
      ./xmlchange --id JOB_QUEUE --val 'pdebug'
    fi

else
    ./xmlchange --id JOB_QUEUE --val 'regular'

  fi

if [[ $edit_jobconf == 'true' ]]; then
# need to use single thread
  npes=$num_procs
  for component in ATM LND ICE OCN CPL GLC ROF WAV; do
    ./xmlchange  NTASKS_$component=$npes,NTHRDS_$component=1,ROOTPE_$component=0
  done

# Compute maximum allowable number for processes (number of elements)
    dyn_pes_nxny=$((num_ne_x * num_ne_y)) #not used (?) KSA
fi


if [[ $edit_domain == 'true' ]]; then
# Compute number of columns needed for component model initialization
  comp_mods_nx=$((num_ne_x * num_ne_y * 4))

# Modify the latitude and longitude for the particular case
  ./xmlchange PTS_MULTCOLS_MODE="TRUE",PTS_MODE="TRUE",PTS_LAT="$lat",PTS_LON="$lon"
  ./xmlchange MASK_GRID="USGS",PTS_NX="${comp_mods_nx}",PTS_NY=1
  ./xmlchange ICE_NX="${comp_mods_nx}",ICE_NY=1

  ./xmlchange DOCN_AQPCONST_VALUE=$sst_val
fi


# Modify the run start and duration parameters for the desired case
#always edit

# ./xmlchange RUN_TYPE="branch"

# ./xmlchange RUN_REFCASE="$refcase"

# ./xmlchange RUN_REFDATE="$refdate"

./xmlchange RUN_STARTDATE="$startdate"

./xmlchange START_TOD="$start_in_sec"

./xmlchange STOP_OPTION="$stop_option"

./xmlchange STOP_N="$stop_n"

./xmlchange CONTINUE_RUN=$do_continue_run

./xmlchange RESUBMIT=$num_resubmit

./xmlchange JOB_WALLCLOCK_TIME=$walltime

# Set model timesteps
  ncpl=$((86400 / model_dtime))
  ./xmlchange ATM_NCPL=$ncpl


# Get local input data directory path
  input_data_dir=$(./xmlquery DIN_LOC_ROOT -value)

# Run case.setup if explicitly requested (run_setup=true), or if env_mach_specific.xml
# is missing (e.g. after a previous case.setup --clean left no xml for xmlchange to read).
# Hardware / MPI layout must be configured before case.setup is called.
if [ "$run_setup" = true ] || [[ ! -f env_mach_specific.xml ]]; then
    if [ "$run_setup" = true ] && [ "$clean_setup" = true ]; then
        ./case.setup --clean
    fi

    ./case.setup

fi

# Set relevant namelist modifications  
if [ "$edit_atmconf" = true ]; then
  ./atmchange se_ne_x=$num_ne_x
  ./atmchange se_ne_y=$num_ne_y
  ./atmchange se_lx=$domain_size_x
  ./atmchange se_ly=$domain_size_y
  ./atmchange dt_remap_factor=2
  ./atmchange cubed_sphere_map=2
  ./atmchange target_latitude=$lat
  ./atmchange target_longitude=$lon
  ./atmchange iop_file=$input_data_dir/$iop_path/$iop_file
  ./atmchange nu=0.216784
  ./atmchange nu_top=$nu_top_dyn
  ./atmchange se_ftype=2
  ./atmchange se_tstep=$dyn_dtime
  ./atmchange rad_frequency=3
  ./atmchange iop_srf_prop=$do_iop_srf_prop
  ./atmchange iop_dosubsidence=$do_iop_subsidence
  ./atmchange iop_coriolis=$do_iop_nudge_coriolis
  ./atmchange extra_shoc_diags=true
  ./atmchange iop_nudge_uv=$do_iop_nudge_uv
  ./atmchange iop_nudge_tq=$do_iop_nudge_tq
fi

if [ "$edit_output" = true ]; then

# Allow for the computation of tendencies for output purposes
  ./atmchange physics::mac_aero_mic::shoc::compute_tendencies=T_mid,qv
  ./atmchange physics::mac_aero_mic::p3::compute_tendencies=T_mid,qv
  ./atmchange physics::rrtmgp::compute_tendencies=T_mid
  ./atmchange homme::compute_tendencies=T_mid,qv
    #./atmchange physics::iop_forcing::compute_tendencies=T_mid,qv  #comment out due to an error
    # ERROR: physics::iop_forcing::compute_tendencies did not match any items
  
 # configure yaml output
 # See the example yaml files in the DPxx_SCREAM_SCRIPTS/yaml_file_example
 # Note that you can have as many output streams (yaml files) as you want!

    yamlfile1=scream_test_output_avg_1hour.yaml
    yamlfile2=scream_test_output_inst_1hour.yaml
    #yamlfile2=scream_horiz_avg_output_5min.yaml

    # ./atmchange output_yaml_files="./scream_horiz_avg_output_5min.yaml"
    # ./atmchange output_yaml_files+="./scream_output_avg_5min.yaml"

    [ ! -L ${yamlfile1} ] && ln -s ${yamlpath}/${yamlfile1}
    [ ! -L ${yamlfile2} ] && ln -s ${yamlpath}/${yamlfile2}
    #[ ! -L ${yamlfile3} ] && ln -s ${yamlpath}/${yamlfile3}
    ./atmchange output_yaml_files="./${yamlfile1}"
    ./atmchange output_yaml_files+="./${yamlfile2}"
    #./atmchange output_yaml_files+="./${yamlfile3}"

    # model I/O settings
    ./xmlchange PIO_TYPENAME="pnetcdf"

fi

# avoid the monthly cice file from writing as this
#   appears to be currently broken for SCM
cat <<EOF >> user_nl_cice
  histfreq='y','x','x','x','x'
EOF

# Turn on UofA surface flux scheme
cat <<EOF>> user_nl_cpl
  ocn_surface_flux_scheme = 2
EOF

if [[ $do_turnoff_swrad == 'true' ]]; then
  solar_angle=180 # turns off incoming solar radiation
else
  solar_angle=-1 # Interactive SW radiation
fi

# Note that this call will be disabled for RCE
cat <<EOF>> user_nl_cpl
EOF

#run cesm scripts --------------------------------------------
cd $case_scripts_dir

# Write restart files at the end of model simulation

# Build the case
if [ "$run_build" = true ]; then
    if [ "$clean_build" = true ]; then
        ./case.build --clean-all
    fi

    ./case.build 

    lfs setstripe -c 16 -S 16M ${case_run_dir}
fi

# Submit the case
if [ "$run_job" = true ]; then
    
    ./case.submit --mail-user $submitter_email --mail-type all

fi