#!/usr/bin/env python3
"""
To run this script:
module load python
conda activate pinacles_share
python compare_PINACLES_RCE_IC.py
"""

# %%

import os
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt

# %%

# Constants from PINACLES parameters.py
G = np.double(9.80665)  # Gravitational Acceleration
RD = np.double(287.15)  # Dry air gas constant

# Profile configurations
#solid lines for equilibrium state
#dashed lines for anlytical RCEMIP 
#dot-dashed for unknown source (SCREAM default IC)
#greenish colors for PINACLES, blueish colors for DP-SCREAM
profiles = [
    {
        'name': 'scream',
        'path': '/global/cfs/cdirs/wcm_code/PINACLES/share/data/profile_from_SCREAM_linear.nc',
        'label': 'SCREAM IC for PINACLES',
        'color': 'gray',
        'linestyle': '-.',
        'is_scream_format': False,
        'plot': False
    },
    {
        'name': 'PIN150km_rce03_eq',
        'path': '/global/cfs/cdirs/wcm_code/PINACLES/share/data/profile_from_RCE03_150x150_1km.nc',
        'label': 'PINACLES dx1km 150km EQ',
        'color': 'lightgreen',
        'linestyle': '-',
        'is_scream_format': False,
        'plot': True
    },
    {
        'name': 'PIN600km_rce00_eq',
        'path': '/global/cfs/cdirs/wcm_code/PINACLES/share/data/profile_from_RCE00_dx1km_600x600.nc',
        'label': 'PINACLES dx1km 600km EQ',
        'color': 'g',
        'linestyle': '-',
        'is_scream_format': False,
        'plot': True
    },
    {
        'name': 'DP_scam',
        'path': '/global/cfs/cdirs/e3sm/inputdata/atm/cam/scam/iop/RCE_300K_iopfile_4scam.nc',
        'label': 'SCREAM default IC',
        'color': 'black',
        'linestyle': '-.',
        'is_scream_format': True,
        'plot': True
    },
    {
        'name': 'DPdx3km_eq',
        'path': '/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/RCE09_dx3km_gpu_equilibrium_300K_profile.nc',
        'label': 'SCREAM dx3km 600km EQ',
        'color': 'blue',
        'linestyle': '-',
        'is_scream_format': True,
        'plot': True
    },
    {
        'name': 'PINrce03_DP',
        'path': '/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/PINACLES_RCE03_150x150_1km_profile_4scam.nc',
        'label': 'PINACLES dx1km 150km EQ for DP-SCREAM',
        'color': 'lightgreen',
        'linestyle': '-.',
        'is_scream_format': True,
        'plot': True
    },
     {
        'name': 'RCEMIP_DP',
        'path': '/global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/input/RCEMIP_analytical_profile_4scam.nc',
        'label': 'RCEMIP IC for DP-SCREAM',
        'color': 'yellow',
        'linestyle': '--',
        'is_scream_format': True,
        'plot': False
    },

]

lwide = 3

# %%
# Process each profile
for p in profiles:
    print(f"Reading {p['name']} IC file: {p['path']}")
    ds = xr.open_dataset(p['path'])
    p['ds'] = ds  # Store dataset to close it later
    
    if p['is_scream_format']:
        lev = ds['lev'].values
        T = ds['T'].mean(dim='time').squeeze().values
        q = ds['q'].mean(dim='time').squeeze().values
        Z = np.zeros_like(lev)
        Z[-1] = 0.0
        for i in range(len(lev)-2, -1, -1):
            Z[i] = Z[i+1] + (RD * 0.5 * (T[i] + T[i+1]) / G) * np.log(lev[i+1]/lev[i])
        p['T'] = T
        p['Z'] = Z
        p['p'] = lev
        p['qv'] = q
    else:
        p['T'] = ds['T']
        p['Z'] = ds['Z']
        p['p'] = ds['p']
        p['qv'] = ds['qv']

# %%
# Analytical profile as in CaseRCE.py
print("Calculating analytical profile...")
T0 = 300.0       
p0 = 1014.8 * 100.0
qv0 = 18.65/1000.0
qt = 1e-11 / 1000.0
Tv0 = T0 * (1.0 +  0.608 * qv0)

Z = np.linspace(0.0, 35000, 500) 
gamma_z = 0.0067
zt = 15000.0 
Tvt = Tv0 - gamma_z * zt 

zq1 = 4000.0
zq2 = 7500.0

qz = qv0 * np.exp(-Z/zq1)*np.exp(-(Z/zq2)**2.0)
qz[Z > zt] = qt

Tvz = Tv0 - gamma_z * Z
Tvz[Z > zt] = Tvt

T = Tvz/(1.0 + 0.608 * qz)

pz = p0 * ((Tv0 - gamma_z * Z)/Tv0)**(G/(RD * gamma_z))
pt = p0 * (Tvt/Tv0)**(G/(RD * gamma_z))

pz[Z > zt] = pt * np.exp((-(G * (Z[Z > zt] - zt)/(RD * Tvt))))


# %%

# Plotting
print("Plotting comparison between profiles...")
fig, axes = plt.subplots(1, 3, figsize=(15, 6))
yscale = 'linear'

# Plot analytical
_=axes[0].plot(T, Z, label='Analytical (RCEMIP)', color='r')
_=axes[1].plot(pz, Z, label='Analytical (RCEMIP)', color='r')
_=axes[2].plot(qz, Z, label='Analytical (RCEMIP)', color='r')

# Plot profiles
for p in profiles:
    if not p.get('plot', True):
        continue
    _=axes[0].plot(p['T'], p['Z'], label=p['label'], color=p['color'], linestyle=p['linestyle'], linewidth=lwide)
    _=axes[1].plot(p['p'], p['Z'], label=p['label'], color=p['color'], linestyle=p['linestyle'], linewidth=lwide)
    _=axes[2].plot(p['qv'], p['Z'], label=p['label'], color=p['color'], linestyle=p['linestyle'], linewidth=lwide)

# Plot T formatting
_=axes[0].set_xlabel("T [K]")
_=axes[0].set_ylabel("Height Z [m]")
_=axes[0].set_title('Temperature Profile')
#_=axes[0].legend()
_=axes[0].grid(True)
_=axes[0].set_yscale(yscale)
_=axes[0].set_ylim(10, 35000)

# Plot p formatting
_=axes[1].set_xlabel("p [Pa]")
_=axes[1].set_title('Pressure Profile')
_=axes[1].legend()
_=axes[1].grid(True)
_=axes[1].set_yscale(yscale)
_=axes[1].set_ylim(10, 35000)

# Plot qv formatting
_=axes[2].set_xlabel("qv [kg/kg]")
_=axes[2].set_title('Water Vapor Profile')
_=axes[2].legend()
_=axes[2].grid(True)
_=axes[2].set_yscale(yscale)
_=axes[2].set_ylim(10, 35000)

plt.tight_layout()
plot_filename = 'IC_comparison_three_profiles.png'
plt.savefig(plot_filename, dpi=300)
print(f"Plot saved to {plot_filename}")

for p in profiles:
    if 'ds' in p:
        p['ds'].close()

print("Done!")

# %%
