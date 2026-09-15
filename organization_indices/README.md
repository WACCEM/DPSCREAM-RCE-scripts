# Convective Organization Indices

This repository contains a modular, Object-Oriented Python suite for computing a comprehensive set of convective organization indices from 2D fields. It was designed to analyze spatial organization in 2D binary masks of convective activity, such as those derived from Radiative-Convective Equilibrium (RCE) simulations (e.g., DP-SCREAM and PINACLES).

## Input Variables

The core routines require a single 2D binary mask (`image`) representing convective and non-convective regions. 

**Required Input Data:**
*   **Convective Mask (`image`)**: A 2D `numpy.ndarray` where `1` represents a convective pixel and `0` represents a non-convective pixel. 
    *   *Derivation*: This mask is typically derived from standard model output variables using specific thresholds. Common choices include:
        *   **Precipitation rate** (e.g., surface precipitation > 1 mm/hr).
        *   **Outgoing Longwave Radiation (OLR)** (e.g., OLR < 170 W/m² or 220 W/m² for deep convection).
        *   **Vertical velocity** (e.g., mid-troposphere $w > 1$ m/s).
        *   **Cloud Water Path / Ice Water Path**.
*   **Grid and Domain Information**: 
    *   The scripts implicitly assume uniform grid spacing. 
    *   `domain_length` and `image_size` are automatically derived from the dimensions of the input `image` array (e.g., `image.shape` and `image.size`). If your grid spacing is not 1 km, you may need to scale these lengths and areas to physical units (kilometers) for the indices to have physically meaningful absolute values, although relative comparisons will still hold.

## Temporal Frequency Requirements

To adequately capture the life cycle, diurnal variation, and spatial evolution of convective organization (such as squall lines or Mesoscale Convective Systems), it is recommended to use:
*   **Minimum Frequency**: **Hourly (1-hour) output**. Hourly frequency is the standard for most RCE and cloud-resolving model studies assessing convective organization, as it effectively captures the statistical properties of cloud cluster growth and aggregation without overwhelming storage requirements.
*   **Higher Frequencies (10-30 minutes)**: Can be used if you intend to perform explicit cloud tracking or if you are analyzing extremely high-resolution domains where convective cells have very short lifespans. However, for bulk spatial organization indices, this is generally unnecessary and computationally expensive.
*   **Lower Frequencies (3-hour to 6-hour)**: Generally **not recommended**, as they fail to resolve the typical lifecycle of individual deep convective cells and mask out the diurnal cycle.

## Computed Indices

The suite calculates the following organization metrics, returning them as a dictionary.

### 1. $I_{org}$ (Organization Index)
*   **Description**: A nearest-neighbor based index. It compares the cumulative distribution function (CDF) of the observed nearest-neighbor distances between cloud centroids to the theoretical Weibull distribution of a completely random (Poisson) point process. Values $>0.5$ indicate aggregation (clustering), $\approx 0.5$ indicates randomness, and $<0.5$ indicates regular dispersion.
*   **Reference**: Tompkins, A. M., & Semie, A. G. (2017). Organization of tropical convection in low vertical wind shears: Role of updraft entrainment. *Journal of Advances in Modeling Earth Systems*, 9(2), 1046-1068. DOI: 10.1002/2016ms000802

### 2. $L_{org}$ 
*   **Description**: Derived from Ripley's K-function and Besag's L-function, this index computes the neighbor density as a function of radius/box size from each cloud centroid. It provides a multi-scale measure of spatial clustering compared to complete spatial randomness (CSR).
*   **Reference**: Biagioli, G., et al. (2023). Measuring Convective Organization. *Journal of the Atmospheric Sciences*, 80(12), 2769-2789. DOI: 10.1175/JAS-D-23-0103.1
*   **Implementation Note**: The Python code in this repository explicitly calculates the discrete $dL_{org}$ (Equation 21 in Biagioli et al., 2023) rather than the continuous $L_{org}$ (Equation 12). This is evidenced by the use of the Chebyshev ($L_\infty$) distance (`size = 2 * np.maximum(...)`), which corresponds to square observation boxes aligned with the discrete grid rather than circular neighborhoods. The code uses a fast numerical approximation of the Riemann sum with 100 linearly spaced bins (`np.linspace`) to calculate the index efficiently while yielding values virtually identical to strict discrete summation over every grid increment.

### 3. ROME (Radar Organization MEtric)
*   **Description**: An area-based metric that accounts for both the size of convective objects and the nearest-edge distance between them (rather than just centroids). It heavily weights larger cloud clusters that are close together.
*   **Reference**: Retsch, M. H., et al. (2020). Assessing Convective Organization in Tropical Radar Observations. *Journal of Geophysical Research: Atmospheres*, 125(7), e2019JD031801. DOI: 10.1029/2019jd031801

### 4. H (Information Entropy)
*   **Description**: Calculates the Shannon information entropy of the 2D binary image. A lower entropy value corresponds to a more structured, aggregated, and less fragmented cloud field.
*   **Reference**: Li, Y., Yano, J.-I., & Lin, Y. (2019). Is atmospheric convection organised?: information entropy analysis. Geophysical & Astrophysical Fluid Dynamics, 113(5–6), 553–573. https://doi.org/10.1080/03091929.2018.1506449


### 5. COP (Convective Organization Potential)
*   **Description**: Measures the potential of clouds to interact based on their equivalent diameters and the centroid-to-centroid distances of all possible pairs of objects in the scene. 
*   **Reference**: White, B. A., et al. (2018). Quantifying the Effects of Horizontal Grid Length and Parameterized Convection on the Degree of Convective Organization Using a Metric of the Potential for Convective Interaction. *Journal of the Atmospheric Sciences*, 75(2), 425-450. DOI: 10.1175/JAS-D-16-0307.1

### 6. ABCOP (Area Based Convective Organization Potential)
*   **Description**: An extension of COP that uses the areas of the objects and the distance between their edges, providing a more robust measure for irregularly shaped and large squall lines compared to assuming circular objects (which COP implicitly does by using equivalent diameter).
*   **Reference**: Jin, D., et al. (2022). A New Organization Metric for Synoptic Scale Tropical Convective Aggregation. *Journal of Geophysical Research: Atmospheres*, 127(21), e2022JD036665. DOI: 10.1029/2022jd036665

### 7. SCAI (Simple Convective Aggregation Metric)
*   **Description**: Combines the number of convective objects with the geometric mean distance between all pairs of objects. Note: The code in this repository returns the *negative* SCAI so that higher values correlate with higher aggregation.
*   **Reference**: Tobin, I., Bony, S., & Roca, R. (2012). Observational Evidence for Relationships between the Degree of Aggregation of Deep Convection, Water Vapor, Surface Fluxes, and Radiation. *Journal of Climate*, 25(20), 6885–6904. DOI: 10.1175/jcli-d-11-00258.1

### 8. MCAI (Modified Convective Aggregation Metric)
*   **Description**: Modifies SCAI by factoring in the size of the objects (using equivalent diameter) to calculate the mean edge-to-edge distance, addressing SCAI's sensitivity to small, unresolved clouds. Note: Returns negative MCAI.
*   **Reference**: Xu, W., et al. (2019). Convective Aggregation and Indices Examined from CERES Cloud Object Data. *Journal of Geophysical Research: Atmospheres*, 124(24), 13604-13624. DOI: 10.1029/2019jd030816

### 9. MICA (Morphological Index of Convective Aggregation)
*   **Description**: Computes the ratio of the total area of convective objects to the area of the smallest bounding box containing all convective objects in the domain. 
*   **Reference**: Kadoya, M., & Masunaga, H. (2018). New Observational Metrics of Convective Self-Aggregation: Methodology and a Case Study. *Journal of the Meteorological Society of Japan. Ser. II*, 96(6), 535-548. DOI: 10.2151/jmsj.2018-054

### 10. Ishape
*   **Description**: A morphological measure evaluating the complexity of the cloud perimeters. It averages the ratio of the square root of area to the perimeter for all objects. Rounder, smoother objects have higher Ishape values, while highly fragmented or jagged objects have lower values.
*   **Reference**: Moseley, C., et al. (2019). A Statistical Model for Isolated Convective Precipitation Events. *Journal of Advances in Modeling Earth Systems*, 11(1), 360-375. DOI: 10.1029/2018ms001383

### 11. OIDRA
*   **Description**: Organization Index based on Distance and Relative Area. A new index developed to fulfill robustness criteria against noise and varying object characteristics.
*   **Reference**: Mandorli, G., & Stubenrauch, C. J. (2024). Assessment of object-based indices to identify convective organization. *Geoscientific Model Development*, 17(21), 7795-7813. DOI: 10.5194/gmd-17-7795-2024

### Not included in this software:

#### A. LWOI (localized wavelet-based organization index)
*   **Description**: A refined version of the wavelet-based organization index (WOI), which is able to characterize the scale, the intensity and anisotropy of convection based on rain rates alone. Exploiting the localization of wavelets both in space and time, we define a localized version of the convective organization index (LWOI). 
*   **Reference**: Brune, S., et al. (2020). Observations and high-resolution simulations of convective precipitation organization over the tropical Atlantic. *Quarterly Journal of the Royal Meteorological Society*, 146(729), 1545-1563. DOI: 10.1002/qj.3751

## Usage

The main entry point is `run_metrics(image)` in `run_metrics.py`. It accepts the 2D binary numpy array and returns a dictionary with the calculated values for all indices.

```python
import numpy as np
from run_metrics import run_metrics

# Example: Generate a random convective mask (size 100x100)
# Replace this with your actual DP-SCREAM or PINACLES 2D thresholded field
convective_mask = np.random.choice([0, 1], size=(100, 100), p=[0.9, 0.1])

# Calculate all indices
organization_results = run_metrics(convective_mask)
print(organization_results)
```

## Performance Optimizations

Significant performance enhancements were introduced to handle high-resolution simulations (e.g., dx=1km with domains featuring 500+ convective objects per timestep) efficiently:

* **Memory Optimization in `Lorg` Metric**: The original Ripley's K / Besag's L function derivation relied on 3-dimensional NumPy arrays (`size_tile`) spanning $O(\text{bins} \times N^2)$. For $N > 500$, this resulted in tens of gigabytes of RAM overhead per process, causing extreme memory exhaustion and Slurm job timeouts during parallel multiprocessing. The metric computation was refactored into a memory-efficient loop over histogram bins, restricting spatial matrices to strictly 2-dimensional structures and saving over 99% of the memory footprint.
* **CPU Optimization for Object Edge Distances**: Computing minimum distances between exterior edges of $N$ irregular polygons previously utilized $O(N^2)$ quadruple-nested loops, which became a severe CPU bottleneck in highly-fragmented convective fields. This was resolved by vectorizing the pairwise boundary searches using `scipy.spatial.cKDTree`, leveraging the natively supported `boxsize` argument to flawlessly handle periodic boundaries while returning minimum nearest-neighbor boundary distances in orders of magnitude less time.

## Pre-processing

### PINACLES
1. `vs_pinacles/make_simlinks_output.sh`
    - Organize output files scattered across subdirectoties into one directory in the collaboration account scratch space
2. `vs_pinacles/python_PINACLES/concat_2d.py`
    - Concatenate hourly outputs to daily files for a specified variable (toa_lw_up)
3. `organization_indices/concat_dailyfiles.py`
    - Further concatenate daily files (with hourly outputs) to multi-day single file covering the analysis period (for the efficinecy of the next script)
4. `organization_indices/compute_orgind_generic.py`
    - calculate 11 indices for convection organization

### DP-SCREAM
