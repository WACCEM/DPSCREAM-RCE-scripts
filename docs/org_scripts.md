# Comparison of Organization Indices Python Scripts

This document summarizes the common and different aspects of the two Python projects for computing convective organization indices: 
1. **Giovanni Biagioli's scripts** in `./giobiagioli_organization_indices/`
2. **Laura Paccini's scripts** in `./organization_indices/`

## 1. Common Aspects

*   **Domain & Purpose**: Both projects are designed to analyze 2D binary fields (cloud masks/convective scenes) to compute convective organization metrics.
*   **Core Metrics**: Both codebases compute the $I_{org}$ index (Tompkins and Semie, 2017) and the $L_{org}$ index (Biagioli et al., 2023).
*   **Image Processing Libraries**: Both rely heavily on `numpy`, `scipy.ndimage`, and `skimage.measure` for identifying connected components (cloud clusters), determining centroids, and calculating areas.

## 2. Different Aspects

### Architecture and Design
*   **Giovanni Biagioli's Version**: Follows a **procedural, single-file approach** (`organization_indices.py`). It contains consecutive functions for neighbor counting, domain boundary handling, and theoretical curve generation, culminating in a main `_compute_organization_indices()` wrapper.
*   **Laura Paccini's Version**: Uses a highly **modular, Object-Oriented Design (OOD)**. It splits the logic into multiple files:
    *   `objects.py`: Defines classes like `make_objects` (for bounding boxes and polygons) and `make_pairs` (for precomputing pairwise distances).
    *   `metrics.py`: Contains individual functions for each metric taking the pre-computed object pairs.
    *   `run_metrics.py`: Acts as the main wrapper to extract all metrics into a dictionary.

### Scope of Metrics
*   **Giovanni Biagioli's Version**: Has a narrow but deep focus on Nearest-Neighbor and Ripley's K/Besag's L function derivations. It outputs $I_{org}$, $RI_{org}$, $L_{org}$, and their corresponding theoretical and observed Continuous Distribution Functions (CDFs).
*   **Laura Paccini's Version**: Computes a much **broader suite of 11 indices**. In addition to $I_{org}$ and $L_{org}$, it calculates: ROME, H (Information Entropy), COP, ABCOP, SCAI, MCAI, MICA, Ishape, and OIDRA.

### Boundary Conditions Handling
*   **Giovanni Biagioli's Version**: Explicitly handles complex spatial configurations within the same script via flags: `periodic_BCs`, `periodic_zonal`, `binomial_continuous`, `binomial_discrete`, and specific edge-correction modes (e.g., Besag correction).
*   **Laura Paccini's Version**: Manages periodic boundaries by branching into separate, dedicated files and scripts (e.g., `metrics_periodic.py`, `objects_periodic.py`, `objects_periodic_fixed.py`), alongside Jupyter Notebooks to test the boundary fixes.

### Additional Dependencies
*   **Giovanni Biagioli's Version**: Computes distances purely via standard `numpy` array manipulations and centroids.
*   **Laura Paccini's Version**: Introduces the `shapely.geometry` library to build accurate Polygon representations of the convective clusters. This is necessary to compute edge-to-edge distances required for metrics like ROME and OIDRA.
