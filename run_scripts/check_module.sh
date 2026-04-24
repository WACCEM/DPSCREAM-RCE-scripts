#!/bin/bash
set -e

echo "Currently loaded default modules:"
module list

echo "unloading the modules as in the machine file"

module unload cpe
module unload cray-hdf5-parallel
module unload cray-netcdf-hdf5parallel
module unload cray-parallel-netcdf
module unload cray-netcdf
module unload cray-hdf5
module unload PrgEnv-gnu
module unload PrgEnv-intel
module unload PrgEnv-nvidia
module unload PrgEnv-cray
module unload PrgEnv-aocc
module unload gcc-native
module unload intel
module unload intel-oneapi
module unload nvidia
module unload aocc
module unload cudatoolkit
module unload climate-utils
module unload cray-libsci
module unload matlab
module unload craype-accel-nvidia80
module unload craype-accel-host
module unload perftools-base
module unload perftools
module unload darshan


echo "loading modules as in pm-gpu in /global/cfs/cdirs/wcm_code/ksa/E3SM/model/E3SM/cime_config/machines/config_machines.xml"

module load PrgEnv-gnu/8.5.0
module load gcc-native/12.3

module load cudatoolkit/12.4
module load craype-accel-nvidia80

module load cray-libsci/24.07.0
module load craype/2.7.32
module load cray-mpich/8.1.30
module load cray-hdf5-parallel/1.12.2.9
module load cray-netcdf-hdf5parallel/4.9.0.9
module load cray-parallel-netcdf/1.12.3.9
module load cmake/3.30.2

module list
