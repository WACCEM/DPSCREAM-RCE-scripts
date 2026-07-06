import xarray as xr
import numpy as np

icase1 = "RCE09_dx3km_gpu"
icase2 = "RCE10_dx3km_gpu"
dir1 = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase1}/havg"
dir2 = f"/pscratch/sd/w/wcmca1/DP-SCREAM/{icase2}/havg"

# Open the first day or so to check if they differ
f1 = f"{dir1}/{icase1}.T_mid.havg.INSTANT.nhours_x1.2000-01-08-03600.nc"
f2 = f"{dir2}/{icase2}.T_mid.havg.INSTANT.nhours_x1.2000-01-08-03600.nc"

ds1 = xr.open_dataset(f1)
ds2 = xr.open_dataset(f2)

diff = np.abs(ds1['T_mid'].values - ds2['T_mid'].values).max()
print(f"Max T_mid difference on 2000-01-08: {diff}")

f1 = f"{dir1}/{icase1}.rrtmgp_T_mid_tend.havg.INSTANT.nhours_x1.2000-01-08-03600.nc"
f2 = f"{dir2}/{icase2}.rrtmgp_T_mid_tend.havg.INSTANT.nhours_x1.2000-01-08-03600.nc"

ds1 = xr.open_dataset(f1)
ds2 = xr.open_dataset(f2)

diff = np.abs(ds1['rrtmgp_T_mid_tend'].values - ds2['rrtmgp_T_mid_tend'].values).max()
print(f"Max rrtmgp_T_mid_tend difference on 2000-01-08: {diff}")
