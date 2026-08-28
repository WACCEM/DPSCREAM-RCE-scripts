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
*   **Reference**: Tompkins, A. M., & Semie, A. G. (2017). Organization of tropical convection in low vertical wind shears: Role of updraft entrainment. *Journal of Advances in Modeling Earth Systems*, 9(2), 1046-1068.

### 2. $L_{org}$ 
*   **Description**: Derived from Ripley's K-function and Besag's L-function, this index computes the neighbor density as a function of radius/box size from each cloud centroid. It provides a multi-scale measure of spatial clustering compared to complete spatial randomness (CSR).
*   **Reference**: Biagioli, G., et al. (2023). A new index for measuring the spatial organization of convection. (A more general implementation by Giovanni Biagioli is often used alongside this).

### 3. ROME (Radar Organization MEtric)
*   **Description**: An area-based metric that accounts for both the size of convective objects and the nearest-edge distance between them (rather than just centroids). It heavily weights larger cloud clusters that are close together.
*   **Reference**: Retsch, M. H., et al. (2020). Radar Organization Metric (ROME): A new morphological measure for organized convection. *Geophysical Research Letters*, 47(4), e2019GL086208.

### 4. H (Information Entropy)
*   **Description**: Calculates the Shannon information entropy of the 2D binary image. A lower entropy value corresponds to a more structured, aggregated, and less fragmented cloud field.
*   **Reference**: Sullivan, S. C., et al. (2019). The effect of secondary ice production on the aggregation of deep convection. *Journal of Advances in Modeling Earth Systems*, 11(12), 4059-4074.

### 5. COP (Convective Organization Potential)
*   **Description**: Measures the potential of clouds to interact based on their equivalent diameters and the centroid-to-centroid distances of all possible pairs of objects in the scene. 
*   **Reference**: White, B. A., et al. (2018). The convective organization potential (COP): A new metric for measuring the spatial pattern of convection. *Journal of the Atmospheric Sciences*, 75(3), 859-873.

### 6. ABCOP (Area Based Convective Organization Potential)
*   **Description**: An extension of COP that uses the areas of the objects and the distance between their edges, providing a more robust measure for irregularly shaped and large squall lines compared to assuming circular objects (which COP implicitly does by using equivalent diameter).
*   **Reference**: Jin, X., et al. (2022). Area-based convective organization potential (ABCOP). *Geophysical Research Letters*, 49(14).

### 7. SCAI (Simple Convective Aggregation Metric)
*   **Description**: Combines the number of convective objects with the geometric mean distance between all pairs of objects. Note: The code in this repository returns the *negative* SCAI so that higher values correlate with higher aggregation.
*   **Reference**: Tobin, I., et al. (2013). Does convective aggregation decrease the clear-sky infrared cooling? *Journal of Climate*, 26(20), 8089-8100.

### 8. MCAI (Modified Convective Aggregation Metric)
*   **Description**: Modifies SCAI by factoring in the size of the objects (using equivalent diameter) to calculate the mean edge-to-edge distance, addressing SCAI's sensitivity to small, unresolved clouds. Note: Returns negative MCAI.
*   **Reference**: Xu, W., et al. (2018). Modified Convective Aggregation Index (MCAI). 

### 9. MICA (Morphological Index of Convective Aggregation)
*   **Description**: Computes the ratio of the total area of convective objects to the area of the smallest bounding box containing all convective objects in the domain. 
*   **Reference**: Kadoya, M., & Masunaga, H. (2018). A morphological index of convective aggregation. *Journal of Climate*, 31(21), 8961-8975.

### 10. Ishape
*   **Description**: A morphological measure evaluating the complexity of the cloud perimeters. It averages the ratio of the square root of area to the perimeter for all objects. Rounder, smoother objects have higher Ishape values, while highly fragmented or jagged objects have lower values.
*   **Reference**: Pscheidt, I., et al. (2019). The lifecycle of tropical deep convective systems. *Quarterly Journal of the Royal Meteorological Society*.

### 11. OIDRA
*   **Description**: Organization Index based on Diagonally Restrained Areas. An additional index based on distance weighting and normalized areas of objects.
*   **Reference**: Biagioli, G., et al. (2024). A new organization index based on diagonally restrained areas (OIDRA) for characterizing convective organization. *Geoscientific Model Development*, 17, 7795-7814. [https://gmd.copernicus.org/articles/17/7795/2024/](https://gmd.copernicus.org/articles/17/7795/2024/)

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
