# processing_gflex

A [QGIS](https://qgis.org) Processing provider plugin that computes
**2-D lithospheric flexural isostasy** using the
[gFlex](https://github.com/awickert/gFlex) library.
Given a surface load raster and an elastic thickness, it returns a raster of
vertical deflections of the lithosphere.

---

## What it does

The plugin adds a **gFlex: Flexure 2D** algorithm to the QGIS Processing
Toolbox.  You supply:

- a **load raster** — either a pre-computed stress field [Pa], or a thickness
  raster [m] with a material density
- an **elastic thickness** — a uniform scalar value *or* a spatially variable
  raster [m or km]

and the algorithm returns a raster of **vertical deflections** [m] (negative
= subsidence).

Typical applications: ice-sheet loading, sediment basin flexure, volcanic
island loading, tectonic wedge problems.

---

## Requirements

| Dependency | Version |
|---|---|
| QGIS | ≥ 3.16 |
| Python | ≥ 3.11 |
| gFlex | ≥ 2.0.0 |

gFlex is installed automatically from PyPI the first time the algorithm runs,
if it is not already present.  To install it manually:

```
pip install gflex
```

---

## Installation

### From the QGIS Plugin Manager (recommended)

1. Open **Plugins → Manage and Install Plugins → All**
2. Search for **gFlex**
3. Click **Install Plugin**

### From a ZIP file / this repository

1. Clone or download this repository.
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**,
   select the `.zip`, click **Install**.
3. Enable the plugin in **Installed** if it is not already ticked.

---

## Parameters

### Load

| Parameter | Description |
|---|---|
| **Load raster** | Stress [Pa] or thickness [m]; same grid/CRS as Te raster |
| **Load density [kg/m³]** | Set to 0 (default) if the raster is already a stress. Set to the material density (e.g. 917 for ice, 1000 for water, 2700 for rock) to convert thickness → stress internally. |

### Elastic thickness

| Parameter | Description |
|---|---|
| **Elastic thickness** | A number (e.g. `35000`) *or* a raster layer name. |
| **Te units** | `m` (default) or `km`. Applies only to a typed scalar value. Rasters must always be in metres. |

A spatially variable Te raster is only supported with the **FD** method.

### Solution method

| Option | Notes |
|---|---|
| **Finite difference (FD)** | Variable or scalar Te; per-edge boundary conditions; supports in-plane stresses |
| **Spectral (FFT)** | Scalar Te only; per-axis-pair boundary conditions; fastest for large uniform-Te problems |
| **Superposition of analytical solutions (SAS)** | Scalar Te only; no boundary conditions needed; exact for point/line loads |

### Boundary conditions — FD

Set independently for each of the four edges (North, South, West, East):

| Option | Physical meaning |
|---|---|
| **Free / broken plate** | Zero moment and shear at the edge |
| **Clamped** | Zero displacement and slope |
| **Pinned (simply supported)** | Zero displacement and moment |
| **Mirror symmetry** | Zero slope and shear (reflect across the edge) |
| **Periodic** | Opposite edges wrap around |
| **Infinite plate (auto-pad)** | gFlex pads this side by one flexural wavelength, solves, and crops back transparently *(default)* |

The default (infinite on all sides) is appropriate for most regional isostasy
problems.

### Boundary conditions — FFT

| Option | Applies to |
|---|---|
| **Infinite plate — zero-pad axis** | West/East pair or North/South pair |
| **Periodic** | Both edges of the pair must be set to periodic for exact wrap-around |

### Advanced parameters

| Parameter | Default | Notes |
|---|---|---|
| Gravitational acceleration [m/s²] | 9.8 | |
| Young's modulus E [GPa] | 65 | Typical lithosphere |
| Poisson's ratio | 0.25 | |
| Mantle density [kg/m³] | 3300 | |
| Infill density [kg/m³] | 0 | 0 = air; ~1000 = water; ~2700 = rock |
| σ_xx, σ_yy, σ_xy [MPa] | 0 | In-plane stresses (FD / FFT only) |
| FFT padding width [× α] | 4 | Padding factor for FFT zero-padding |

---

## Output

**Vertical deflection [m]** — a raster with the same extent, resolution, and
CRS as the input load raster.  Negative values indicate subsidence; positive
values indicate uplift (forebulge).

---

## Headless / scripted use

```python
import processing

result = processing.run('gflex:flexure2d', {
    'INPUT_LOAD':     '/path/to/load.tif',
    'LOAD_DENSITY':   917.0,         # kg/m³ (ice)
    'INPUT_TE':       '35000',       # 35 km in metres
    'TE_UNITS':       0,             # m
    'METHOD':         0,             # FD
    'BC_NORTH':       5,             # infinite
    'BC_SOUTH':       5,
    'BC_WEST':        5,
    'BC_EAST':        5,
    'PARAM_RHO_FILL': 1000.0,        # water infill
    'OUTPUT':         '/tmp/deflection.tif',
})
```

The same call works in the **QGIS Graphical Modeler**.

---

## Memory and performance

The FD solver uses a sparse LU factorisation.  Memory scales roughly as
O(n^1.3) in the number of padded grid cells.  For large domains with infinite
boundary conditions (which auto-pad by ~1 flexural wavelength per side), this
can become substantial.  A warning is printed when the estimated padded domain
exceeds 500 000 cells.  The FFT and SAS methods are far less memory-intensive
for equivalent grids.

---

## Running the tests

Tests require a system QGIS installation with Python bindings and pytest:

```
/usr/bin/python3 -m pytest tests/ -v
```

The test suite uses a headless QGIS app (no display required) and a synthetic
30 × 30 grid at 5 km spacing.

---

## Related projects

- **gFlex** — the core library: https://github.com/awickert/gFlex
- **gFlex documentation**: https://gflex.readthedocs.io
- **r.flexure / v.flexure** — GRASS GIS interfaces: https://github.com/awickert/grass-addons-gflex

---

## License

GNU General Public License v3 — see [LICENSE.md](LICENSE.md).

## Author

Andy Wickert — University of Minnesota  
awickert@umn.edu
