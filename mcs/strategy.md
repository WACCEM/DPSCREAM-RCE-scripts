# Strategy: Combining PyFLEXTRKR Lagrangian Tracking with Convective Organization Indices in RCE

## 1. Will PyFLEXTRKR Output Be Useful for Studying Convective Self-Organization in RCE?

**Yes—very much so, provided we interpret the tracked objects as "organized precipitating cold-cloud clusters (CCSs)" rather than classic shear-driven continental squall lines, and provided we account for the relaxed configuration thresholds.**

Here is why PyFLEXTRKR adds unique value on top of the four static Eulerian indices ($\text{Var}(MSE)$, $I_{org}$, $dL_{org}$, and $OIDRA$), along with a critical note about the configuration:

1. **Why the RCE vs. Real-World MCS distinction does not invalidate PyFLEXTRKR here:**
   - As summarized in [`docs/MCS_Circulations_in_RCE_Simulations.pdf`](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/docs/MCS_Circulations_in_RCE_Simulations.pdf), non-rotating, un-sheared RCE lacks the kinematic ingredients (RKW cold-pool/shear balance and Coriolis rotation) that produce Rear Inflow Jets or Mesoscale Convective Vortices.
   - **However, the PyFLEXTRKR setup ([`config_ccs_olr_DPSCREAM.yml`](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/mcs/config/config_ccs_olr_DPSCREAM.yml) / [`config_ccs_olr_PINACLES.yml`](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/mcs/config/config_ccs_olr_PINACLES.yml)) has already been intentionally adapted for RCE!** Specifically, instead of enforcing the strict real-world MCS thresholds ($A_{CCS} > 40,000\text{ km}^2$, duration $> 4\text{ h}$, $L_{PF} > 100\text{ km}$), the configuration uses relaxed thresholds:
     - Cold core $T_b < 225\text{ K}$, cold anvil $T_b < 241\text{ K}$, warm anvil $T_b < 281\text{ K}$
     - `mcs_tb_area_thresh: 100` ($\text{km}^2$), `mcs_tb_duration_thresh: 2` ($\text{h}$)
     - `mcs_pf_majoraxis_thresh: 0` ($\text{km}$), `mcs_pf_durationthresh: 0.5` ($\text{h}$), `mcs_min_rainvol_thresh: 100` ($\text{km}^2\text{ mm h}^{-1}$)
   - Because of this, PyFLEXTRKR is not filtering for $100\text{+ km}$ squall lines; it is tracking **the population of precipitating deep convective clusters ($> 100\text{ km}^2$, $\ge 2\text{ h}$) across all scales** as the RCE domain transitions from random popcorn convection (`RCE00` IC) or pre-aggregated states (`RCE01`/`RCE02`/`RCE03` EQ ICs).

   | Parameter | Config Key | Standard Real-World MCS (Feng et al., 2021 / MCSMIP) | RCE-Tailored CCS Setup (`config_ccs_olr_*.yml`) | Physical Effect of RCE Relaxation |
   | :--- | :--- | :--- | :--- | :--- |
   | **Cold Core $T_b$** | `cloudtb_core` | $225.0\text{ K}$ | $225.0\text{ K}$ | Same deep convective core threshold |
   | **Cold Anvil $T_b$** | `cloudtb_cold` | $241.0\text{ K}$ | $241.0\text{ K}$ | Same cold anvil threshold |
   | **Warm Anvil / Cloud $T_b$** | `cloudtb_warm` / `cloudtb_cloud` | $261.0\text{ K}$ | $281.0\text{ K}$ | Expands outer cloud shield to include warmer anvil edges |
   | **Min Cold Core Size** | `mincoldcorepix` / `area_thresh` | $\sim 4\text{ pixels}$ ($\ge 64\text{--}400\text{ km}^2$) | $4\text{ pixels}$ ($9\text{ km}^2$ min cloud area at $\Delta x = 1\text{ km}$) | Resolves individual $1\text{ km}$ convective updraft cores |
   | **MCS $T_b$ Area Threshold** | `mcs_tb_area_thresh` | $40,000\text{ km}^2$ | $100\text{ km}^2$ | Retains both small ($10\times 10\text{ km}$) and large ($>10^4\text{ km}^2$) clusters |
   | **MCS $T_b$ Duration Threshold** | `mcs_tb_duration_thresh` | $4\text{ h}$ | $2\text{ h}$ | Captures shorter-lived multi-cell clusters during spin-up |
   | **PF Major Axis Length** | `mcs_pf_majoraxis_thresh` | $100\text{ km}$ | $0\text{ km}$ ($10\text{ km}$ for `pf_lifetime`) | Removes the $100\text{ km}$ linear squall-line requirement |
   | **PF Duration Threshold** | `mcs_pf_durationthresh` | $4\text{ h}$ | $0.5\text{ h}$ | Retains clusters with brief intense precipitation phases |
   | **PF Rain Rate Threshold** | `pf_rr_thres` / `heavy_rainrate_thresh` | $1.0\text{--}2.0\text{ mm h}^{-1}$ / $10.0\text{ mm h}^{-1}$ | $1.0\text{ mm h}^{-1}$ / $8.0\text{ mm h}^{-1}$ | Slightly relaxed heavy rain rate threshold ($8\text{ mm h}^{-1}$) |
   | **Min Volumetric Rain** | `mcs_min_rainvol_thresh` | $20,000\text{ km}^2\text{ mm h}^{-1}$ ($100\times 100\text{ km}\times 2\text{ mm h}^{-1}$) | $100\text{ km}^2\text{ mm h}^{-1}$ (for $\ge 1\text{ h}$) | Scaled down by $200\times$ to match the $100\text{ km}^2$ area threshold |
   | **Boundary Conditions** | `pbc_direction` | `none` (or `x` for global) | `both` (doubly periodic) | Tracks clusters seamlessly across $600\times 600\text{ km}$ periodic edges |

2. **How PyFLEXTRKR directly resolves the limitations of $I_{org}$, $dL_{org}$, $OIDRA$, and $\text{Var}(MSE)$ identified in the literature:**

   - **Non-monotonicity of $\text{Var}(MSE)$ ([Biagioli & Tompkins, 2023](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/docs/Biagioli_and_Tompkins_-_2023_-_Measuring_Convective_Organization.pdf), p. 2771):**

        Once aggregation is established, further consolidation can actually *reduce* $\text{Var}(MSE)$ due to domain-wide drying, making it non-monotonic across models (like DP-SCREAM vs. PINACLES).

   - **Scale blindness & size insensitivity of $I_{org}$ and $dL_{org}$ ([Biagioli & Tompkins, 2023](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/docs/Biagioli_and_Tompkins_-_2023_-_Measuring_Convective_Organization.pdf); [Mandorli & Stubenrauch, 2024](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/docs/Mandorli_and_Stubenrauch_-_2024_-_Assessment_of_object-based_indices_to_identify_convective_organization.pdf), Condition 4):** 
   
       Both $I_{org}$ and $dL_{org}$ treat convective objects as zero-area points and are completely insensitive to object size ($\Delta p = 0$ when an object grows). Furthermore, when two close objects merge by 1 pixel (Mandorli & Stubenrauch Condition 2), $I_{org}$ and $dL_{org}$ *decrease* (falsely indicating *less* organization because the closest-neighbor pair disappears!).

   - **Size vs. Number Tradeoff in $OIDRA$ ([Mandorli & Stubenrauch, 2024](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/docs/Mandorli_and_Stubenrauch_-_2024_-_Assessment_of_object-based_indices_to_identify_convective_organization.pdf), Fig. 7d & Sect. 5):** 
   
       $OIDRA$ weights relative areas squared ($A_i^2 / A_T^2$), making it noise-safe and resolution-robust, **but it is a static snapshot index**. It cannot tell *how* a large $A_i$ formed (did one cluster grow in-situ, or did 10 smaller clusters merge?) or *how long* it persists.
   - **PyFLEXTRKR bridges this gap** by providing the **Lagrangian mechanism** behind changes in $I_{org}$, $dL_{org}$, and $OIDRA$: explicit merger/split rates, cluster lifetimes, cold-core vs. anvil expansion, and volumetric rainfall efficiency.

---

## 2. What Variables to Examine in PyFLEXTRKR Output (`mcs_tracks_final_*.nc` and `mcstracking/`)

In `/pscratch/sd/w/wcmca1/PINACLES/RCE00_dx1km_600x600km/mcstrack/stats/mcs_tracks_final_*.nc` (and the corresponding DP-SCREAM files), variables have dimensions `(tracks, times)` or `(tracks, times, nmaxpf)`. They can be analyzed both **along the storm lifecycle** (as a function of relative `times` since initiation) and **as domain-mean/summed time series** (by grouping `base_time` across all active tracks at each simulation hour $t$ to compare directly against hourly $\text{Var}(MSE)$, $I_{org}$, $dL_{org}$, and $OIDRA$).

Below are the most insightful PyFLEXTRKR variables to examine, grouped by the physical questions in [`docs/main.pdf`](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/docs/main.pdf):

### A. Cluster Count & Size Partitioning (To Compare Directly with $OIDRA$, $I_{org}$, and $dL_{org}$)
In Mandorli & Stubenrauch (2024, Table 1), object-based indices are governed by three fundamental macroscopic quantities: **number of objects ($N$)**, **mean object size ($\overline{A}$)**, and **total convective area ($\sum A_i$)**. From `mcs_tracks_final_*.nc`, we can extract:
- **`area`** `(tracks, times)` $[\text{km}^2]$: Total cold-cloud shield area ($T_b < 281\text{ K}$).
- **`core_area`** `(tracks, times)` $[\text{km}^2]$: Coldest convective core area ($T_b < 225\text{ K}$).
- **`cold_area`** `(tracks, times)` $[\text{km}^2]$: Cold anvil area ($225\text{ K} \le T_b < 241\text{ K}$).
- **`pf_area`** `(tracks, times, nmaxpf)` $[\text{km}^2]$ and **`pf_majoraxis`** $[\text{km}]$: Area and major-axis length of the precipitation features ($P > 1\text{ mm h}^{-1}$), where index `0` in `nmaxpf` is the largest PF.
- **`pf_npf`** `(tracks, times)`: Number of distinct precipitation features embedded inside a single cold-cloud shield.
- **What to compare:**
  - At each simulation hour $t$, count the number of active tracks $N_{\text{MCS}}(t)$, mean cluster area $\overline{A}(t)$, and largest cluster area fraction $\max(A_i) / \sum A_i$ (which directly mirrors the first term $\sum A_i^2 / A_T^2$ of $OIDRA$!).
  - **Core-to-Anvil Area Ratio (`core_area / area`)** or **PF-to-CCS Area Ratio (`pf_area.sum(dim='nmaxpf') / area`)**: Since the organization indices (`compute_orgind_generic.py`) use a binary threshold of $\text{OLR} < 173\text{ W m}^{-2}$ ($\approx 235\text{ K}$), they include anvil clouds. Comparing `core_area` vs. `area` and `pf_npf` shows whether high $OIDRA$ / $dL_{org}$ comes from a single expanding stratiform anvil shield connecting multiple cores (`pf_npf` increasing) or genuine coalescence of convective cores.

### B. Merging and Splitting Dynamics (Testing the Aggregation Mechanism)
As drafted in Section 3.1.5 of [`docs/main.pdf`](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/docs/main.pdf), static indices cannot tell whether self-aggregation occurs via **mergers of smaller satellite cells** or **in-situ growth**.
- **`merge_tracknumbers`** `(tracks, times)` and **`split_tracknumbers`** `(tracks, times)`: Track numbers that merge into or split from a given track at each time step.
- **`merge_cloudnumber`** `(tracks, times, nmaxlinks)` and **`split_cloudnumber`** `(tracks, times, nmaxlinks)`: Number of constituent cloud objects merging/splitting at each step (`np.sum(merge_cloudnumber > 0, axis=-1)` gives the instantaneous merger count!).
- **`start_split_tracknumber`** `(tracks)` and **`end_merge_tracknumber`** `(tracks)`: Indicates whether a track was born by splitting off an existing MCS (`start_split_tracknumber > 0`) or died by merging into a larger MCS (`end_merge_tracknumber > 0`).
- **What to compare:**
  - Plot the **hourly merger rate** and **fraction of tracks terminating in a merger** alongside the time series of $\text{Var}(MSE)$, $dL_{org}$, and $OIDRA$ (especially in `RCE00_dx1km_600x600km` as it aggregates from random IC).
  - Does the rapid jump in $I_{org}$ and $dL_{org}$ during spin-up coincide with a spike in `merge_cloudnumber` counts? This directly explains Mandorli & Stubenrauch's Condition (2) (where object merging causes jumps in $I_{org}$/$dL_{org}$).

### C. Lifecycles, Persistence, and Propagation Speed (Resolving Temporal Autocorrelation)
Mandorli & Stubenrauch (2024, Fig. 12) showed that $I_{org}$ and $L_{org}$ decorrelate in $< 1\text{ h}$, whereas $OIDRA$ and $ROME$ decorrelate over several hours. PyFLEXTRKR directly measures this persistence:
- **`track_duration`** `(tracks)` and **`mcs_duration`** `(tracks)` $[\text{hours}]$: Total lifetime of each track.
- **`pf_lifetime`** `(tracks)` $[\text{hours}]$: Lifetime during which a significant PF ($> 10\text{ km}$) is present.
- **`movement_speed`** `(tracks, times)` $[\text{m s}^{-1}]$ and **`movement_distance`** $[\text{km}]$: Propagation speed of the precipitation feature (via 2D phase correlation).
- **What to compare:**
  - Stratify `track_duration` and `movement_speed` by aggregation regime (e.g., low vs. high $dL_{org}$ / $OIDRA$, or early vs. late in `RCE00`).
  - In unaggregated RCE (`RCE00` early days), cold pools trigger new short-lived cells that propagate away (`movement_speed` higher, `track_duration` short). In aggregated RCE (`RCE01`/`RCE02`/`RCE03`), convection locks into a quasi-stationary moist patch (`movement_speed` decreases, `track_duration` and `pf_lifetime` increase dramatically).

### D. Precipitation Intensity, Volumetric Rain, and Morphology (Connecting to Extreme Rain)
- **`total_volrain`** `(tracks, times)` $[\text{km}^2\text{ mm h}^{-1}]$ and **`total_heavyvolrain`** (for $P > 8\text{ mm h}^{-1}$): Total volumetric rainfall and heavy volumetric rainfall produced by the system.
- **`pf_maxrainrate`** `(tracks, times, nmaxpf)` $[\text{mm h}^{-1}]$, **`rainrate_p95`** `(tracks, times)` $[\text{mm h}^{-1}]$, and **`pf_skewness`**: Peak intensity and skewness of the rainfall distribution inside the cluster.
- **`pf_eccentricity`** and **`pf_aspectratio`** `(tracks, times, nmaxpf)`: Shape/linearity of the precipitation features (analogous to $I_{\text{shape}}$ in `organization_indices`, but for individual tracked PFs).
- **What to compare:**
  - Compare the **Heavy Rain Volume Ratio (`total_heavyvolrain / total_volrain`)**, **`rainrate_p95`**, and **`total_volrain`** against $OIDRA$, $dL_{org}$, and $\text{Var}(MSE)$.
  - This tests whether models with higher $OIDRA$ / $dL_{org}$ (DP-SCREAM vs. PINACLES) produce more rain through **larger cluster area (`pf_area`)**, **longer duration (`track_duration`)**, or **higher local intensity (`pf_maxrainrate`, `rainrate_p95`)**.

### E. Pixel-Level Masks (`mcstracking/20000101.0000_20000315.0000/mcstrack_*.nc`)
Each hourly pixel file contains 2D fields on the $(600 \times 600\text{ km})$ grid:
- **`cloudtracknumber`** (full CCS mask labeled by track ID), **`pcptracknumber`** (PF mask labeled by track ID), **`cloudtracknumber_nomergesplit`**, **`feature_number`**, **`tb`**, and **`precipitation`**.
- **How to use it with the organization indices:**
  - Overlay convective initiation points (`times == 0` locations from `meanlon`, `meanlat` or `pf_lon_maxrainrate`, `pf_lat_maxrainrate`) on top of the previous hour's `pcptracknumber` boundaries to directly test the **Cold Pool Triggering / Convective Initiation** hypothesis in [`docs/main.pdf`](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/docs/main.pdf) (measuring distance from new track initiation to existing PF edges!).

---

## 3. Summary Table of Recommended Comparisons for the Manuscript (`docs/main.pdf`)

| Physical Question in `docs/main.pdf` | Static Eulerian Indices | PyFLEXTRKR Variables to Compare (`mcs_tracks_final_*.nc`) |
| :--- | :--- | :--- |
| **1. Degree of Multi-Scale Clustering & Consolidation** | $I_{org}$ (meso-$\beta$), $dL_{org}$ (all-scale), $OIDRA$ (area-weighted) | Active track count $N_{\text{MCS}}(t)$, `area`, `pf_area`, `pf_npf` (multi-core vs. single-core clusters), largest cluster fraction $\max(A_i)/\sum A_i$ |
| **2. Merging & Splitting vs. In-Situ Growth** | Jumps/tails in $I_{org}$, $dL_{org}$, $OIDRA$ | `merge_cloudnumber` count, `split_cloudnumber` count, fraction of tracks with `end_merge_tracknumber > 0` |
| **3. Storm Lifecycles & Quasi-Stationarity** | Autocorrelation time of $I_{org}$, $dL_{org}$, $OIDRA$; $\text{Var}(MSE)$ | `track_duration`, `mcs_duration`, `pf_lifetime`, `movement_speed` |
| **4. Precipitation Efficiency & Extremes** | $\text{Var}(MSE)$, $OIDRA$, $dL_{org}$ | `total_volrain`, `total_heavyvolrain / total_volrain`, `pf_maxrainrate`, `rainrate_p95`, `core_area / area` |

> [!NOTE]
> **Manuscript Consistency Note (`docs/main.pdf`):**
> Lines 106–115 of `docs/main.pdf` currently mention tracking vertical velocity $w > 1\text{ m s}^{-1}$ and outputting maximum updraft velocity $w$ in PyFLEXTRKR. Since the actual PyFLEXTRKR runs use `feature_type: tb_pf` on OLR-converted $T_b$ and surface `rain_rate`, consider updating that paragraph in `docs/main.tex` to describe the OLR-derived $T_b$ thresholds $[225, 241, 281]\text{ K}$ and `rain_rate` $> 1\text{ mm h}^{-1}$ PF matching.

---

## 4. Simulation-Time Series Plotting in `mcs/analysis/plot_mcs_stats.py`

### How It Works
- The third plot section in [`mcs/analysis/plot_mcs_stats.py`](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/mcs/analysis/plot_mcs_stats.py#L171-L261) flattens the `(tracks, times)` arrays using `base_time`, groups all active MCS tracks at each simulation hour $t$, and aggregates them using `agg_method` (`"mean"`, `"sum"`, or `"max"`).
- It supports optional temporal smoothing (`resample_freq = "6h"`, `"1D"`, or `None`), matching the formatting and dual time axes (`add_dual_time_axes` from [`rce_tools/plotting.py`](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/rce_tools/plotting.py#L163-L197)) used in [`organization_indices/plot_orgind.py`](file:///global/cfs/cdirs/wcm_code/ksa/DP-SCREAM/organization_indices/plot_orgind.py#L70-L103) for direct comparison with $I_{org}$, $dL_{org}$, and $OIDRA$.

### Which Variables in `mcs_tracks_final_*.nc` Can Be Plotted This Way?

Any variable with `(tracks, times)` or `(tracks, times, nmaxpf)` dimensions (plus three built-in derived counts in the script) can be set via `plotvar`:

#### 1. Cloud Shield & Core Size (`(tracks, times)`)
| `plotvar` | Units | Recommended `agg_method` | Physical Meaning / Comparison to Org Indices |
| :--- | :--- | :--- | :--- |
| **`"area"`** | $\text{km}^2$ | `"mean"`, `"sum"`, or `"max"` | Total cold-cloud shield area ($T_b < 281\text{ K}$). `"mean"` compares to $ROME$; `"sum"` gives total domain MCS cloud cover; `"max"` tracks the primary aggregated cluster. |
| **`"core_area"`** | $\text{km}^2$ | `"mean"` or `"sum"` | Deep convective core area ($T_b < 225\text{ K}$). |
| **`"cold_area"`** | $\text{km}^2$ | `"mean"` or `"sum"` | Cold anvil area ($225 \le T_b < 241\text{ K}$). |
| **`"mintb"`** | $\text{K}$ | `"mean"` | Minimum brightness temperature (cloud-top height proxy). |

#### 2. Precipitation & Extreme Rain (`(tracks, times)`)
| `plotvar` | Units | Recommended `agg_method` | Physical Meaning |
| :--- | :--- | :--- | :--- |
| **`"total_volrain"`** | $\text{km}^2\text{ mm h}^{-1}$ | `"sum"` or `"mean"` | Volumetric rainfall within MCS shield. |
| **`"total_heavyvolrain"`** | $\text{km}^2\text{ mm h}^{-1}$ | `"sum"` or `"mean"` | Heavy volumetric rainfall ($P > 8\text{ mm h}^{-1}$). |
| **`"total_rain"`** | $\text{mm h}^{-1}$ | `"sum"` or `"mean"` | Summed rain rate across pixels in the MCS shield. |
| **`"rainrate_heavyrain"`** | $\text{mm h}^{-1}$ | `"mean"` | Conditional mean rain rate of heavy-rain pixels ($P > 8\text{ mm h}^{-1}$). |
| **`"rainrate_p95"`** | $\text{mm h}^{-1}$ | `"mean"` or `"max"` | 95th percentile rain rate within each MCS. |
| **`"pf_npf"`** | count | `"mean"` | Number of distinct precipitation features per cold-cloud shield (multi-core vs. single-core structure). |

#### 3. Individual Precipitation Feature (PF) Properties (`(tracks, times, nmaxpf)` — script automatically selects largest PF `nmaxpf=0`)
| `plotvar` | Units | Recommended `agg_method` | Physical Meaning |
| :--- | :--- | :--- | :--- |
| **`"pf_area"`** | $\text{km}^2$ | `"mean"` or `"max"` | Area of the primary precipitation feature ($P > 1\text{ mm h}^{-1}$). |
| **`"pf_majoraxis"`** | $\text{km}$ | `"mean"` or `"max"` | Major axis length of the primary PF. |
| **`"pf_maxrainrate"`** | $\text{mm h}^{-1}$ | `"mean"` or `"max"` | Peak rain rate inside the primary PF. |
| **`"pf_rainrate"`** | $\text{mm h}^{-1}$ | `"mean"` | Mean rain rate of the primary PF. |
| **`"pf_skewness"`** | unitless | `"mean"` | Rain rate skewness inside the primary PF. |
| **`"pf_eccentricity"`** / **`"pf_aspectratio"`** | unitless | `"mean"` | Linearity / elongation of the primary PF. |

#### 4. Kinematics & Built-in Derived Population Metrics
| `plotvar` | Units | Recommended `agg_method` | Physical Meaning |
| :--- | :--- | :--- | :--- |
| **`"movement_speed"`** | $\text{m s}^{-1}$ | `"mean"` | Propagation speed of tracked PFs (tests whether aggregated clusters become quasi-stationary). |
| **`"active_mcs_count"`** | count | *(auto `"sum"`)* | Number of active MCS tracks present in the domain at each hour $t$ (comparable to $N$ in $SCAI$/$MCAI$). |
| **`"merger_count"`** | count | *(auto `"sum"`)* | Total number of cloud mergers (`merge_cloudnumber > 0`) occurring at each hour $t$. |
| **`"split_count"`** | count | *(auto `"sum"`)* | Total number of cloud splits (`split_cloudnumber > 0`) occurring at each hour $t$. |

