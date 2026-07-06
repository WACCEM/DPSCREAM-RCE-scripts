import xarray as xr
import numpy as np
import glob

f1 = glob.glob("/pscratch/sd/w/wcmca1/DP-SCREAM/RCE09_dx3km_gpu/havg/RCE09_dx3km_gpu.T_mid.havg.AVERAGE.*.nc")[0]
f2 = glob.glob("/pscratch/sd/w/wcmca1/DP-SCREAM/RCE10_dx3km_gpu/havg/RCE10_dx3km_gpu.T_mid.havg.AVERAGE.*.nc")[0]

ds1 = xr.open_dataset(f1)
ds2 = xr.open_dataset(f2)

diff = np.abs(ds1['T_mid'].values - ds2['T_mid'].values).max()
print("Max T_mid difference:", diff)

f1_r = glob.glob("/pscratch/sd/w/wcmca1/DP-SCREAM/RCE09_dx3km_gpu/havg/RCE09_dx3km_gpu.rrtmgp_T_mid_tend.havg.AVERAGE.*.nc")[0]
f2_r = glob.glob("/pscratch/sd/w/wcmca1/DP-SCREAM/RCE10_dx3km_gpu/havg/RCE10_dx3km_gpu.rrtmgp_T_mid_tend.havg.AVERAGE.*.nc")[0]

ds1_r = xr.open_dataset(f1_r)
ds2_r = xr.open_dataset(f2_r)

diff_r = np.abs(ds1_r['rrtmgp_T_mid_tend'].values - ds2_r['rrtmgp_T_mid_tend'].values).max()
print("Max rrtmgp_T_mid_tend difference:", diff_r)
