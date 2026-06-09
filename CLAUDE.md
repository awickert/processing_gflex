# processing_gflex — project context for Claude

## What this is

A QGIS Processing provider plugin that exposes gFlex (lithospheric flexural
isostasy) as algorithms in the QGIS Processing Toolbox. Users supply load and
elastic-thickness rasters; the plugin returns a deflection raster. The plugin
should also be usable headlessly via `processing.run("gflex:flexure", {...})`
and in the QGIS Graphical Modeler.

**gFlex repository:** https://github.com/awickert/gFlex
**gFlex docs:** https://gflex.readthedocs.io
**This repo:** https://github.com/awickert/processing_gflex

---

## gFlex API (v2.0.0b1+, what this plugin calls)

### Minimal 2-D FD workflow

```python
import numpy as np
import gflex

flex = gflex.F2D()

flex.method = 'fd'          # 'fd', 'fft', 'sas', 'sas_ng'
flex.quiet = True           # now the default; explicit here for clarity

flex.g = 9.8
flex.E = 65e9
flex.nu = 0.25
flex.rho_m = 3300.
flex.rho_fill = 0.          # 0 = air, ~1000 = water, ~2700 = rock

flex.T_e = Te_array         # float (scalar) or 2-D numpy array [m]
flex.qs = load_array        # 2-D numpy array of surface load stress [Pa]
flex.dx = 5000.             # grid cell size x [m]
flex.dy = 5000.             # grid cell size y [m]

flex.bc_west  = 'zero_moment_zero_shear'
flex.bc_east  = 'zero_moment_zero_shear'
flex.bc_north = 'zero_moment_zero_shear'
flex.bc_south = 'zero_moment_zero_shear'

flex.initialize()
flex.run()

w = flex.w                  # read BEFORE finalize — finalize deletes w
flex.finalize()
```

### Key attributes

| Attribute | Type | Notes |
|-----------|------|-------|
| `flex.method` | str | `'fd'`, `'fft'`, `'sas'`, `'sas_ng'` |
| `flex.T_e` | float or ndarray | elastic thickness [m]; scalar or 2-D array |
| `flex.qs` | ndarray | surface load stress [Pa]; rho * g * h |
| `flex.dx`, `flex.dy` | float | grid spacing [m] |
| `flex.bc_west/east/north/south` | str | see BC strings below |
| `flex.rho_m` | float | mantle density [kg/m³], default 3300 |
| `flex.rho_fill` | float | infill density [kg/m³], default 0 |
| `flex.E` | float | Young's modulus [Pa], default 65e9 |
| `flex.nu` | float | Poisson's ratio, default 0.25 |
| `flex.g` | float | gravitational acceleration [m/s²], default 9.8 |
| `flex.cache_factorization` | bool or `"no_check"` | LU cache for repeated runs |

**Critical:** `finalize()` deletes `flex.w`. Always read `w` before calling it.

### BC strings (v2.0 — all lowercase)

| String | Alias | Methods | Physical meaning |
|--------|-------|---------|-----------------|
| `"zero_displacement_zero_slope"` | `"clamped"` | FD | Clamped end |
| `"zero_displacement_zero_moment"` | `"pinned"` | FD | Simply supported (pinned) |
| `"zero_moment_zero_shear"` | `"free"` | FD | Broken plate / free end |
| `"zero_slope_zero_shear"` | `"mirror"` | FD | Mirror symmetry plane |
| `"periodic"` | — | FD, FFT | Wrap-around |
| `"no_outside_loads"` | `"infinite"` | FD, FFT, SAS | Infinite plate, no far-field loads |

**`no_outside_loads` behaviour by method:**
- **FD**: set on any subset of edges; gFlex auto-pads those sides by one flexural wavelength, applies clamped BC at the new outer edge, solves, and crops `w` back to the original shape. Output shape is transparent to the caller. Mixed BCs are supported (e.g. `no_outside_loads` on two sides, `free` on the others).
- **FFT**: any non-`periodic` value (including `no_outside_loads` or unset) causes gFlex to zero-pad that axis. West/East and North/South pairs are controlled independently — mixed-axis configs (e.g. x-periodic, y-padded) are valid.
- **SAS**: the default; leave BCs unset or set explicitly.

**FFT per-axis BC rule**: set *both* sides of a pair to `"periodic"` for exact periodicity on that axis; if only one side is `"periodic"` gFlex warns and falls back to zero-padding.

Old v1.x PascalCase strings (`"0Displacement0Slope"`, `"0Moment0Shear"`, etc.)
now raise `ValueError`. Do not use them.

`gflex.VALID_BC_STRINGS_2D` now includes both `"no_outside_loads"` and `"infinite"`
(added post-2.0.0b1).

### Load array convention

`flex.qs` is a **stress** [Pa], not a force. For a load layer of thickness `h`
[m] and density `rho_load` [kg/m³]:

```python
flex.qs = rho_load * flex.g * h   # [Pa]
```

QGIS users will likely provide either:
- An ice/rock/water thickness raster → multiply by density and g in the plugin
- A pre-computed stress raster → pass directly

Expose both options (or a density parameter with a `None` / "already stress"
option).

---

## Plugin architecture

- **Provider class** registers with QGIS Processing and appears in the Toolbox
  under a "gFlex" group.
- **Algorithm class(es)** define inputs/outputs. Start with one algorithm:
  `FlexureAlgorithm` (2-D FD, the common case).
- The algorithm takes raster inputs (load, Te), scalar parameters, BC dropdowns,
  and returns a deflection raster.
- Add a 1-D algorithm later if there is demand.

Suggested initial algorithm inputs:
- Load raster (or thickness raster + density)
- Elastic thickness raster or scalar
- BC for each edge (dropdown, default `"zero_moment_zero_shear"`)
- Physical parameters (E, nu, rho_m, rho_fill, g) with sensible defaults
- Method dropdown (fd / fft — sas needs scalar Te, so conditionally enable)

---

## Repository conventions

- Python ≥ 3.11 (matches gFlex requirement)
- Follow QGIS Processing provider structure:
  - `processing_gflex/__init__.py` — plugin entry point
  - `processing_gflex/provider.py` — `GFlexProvider(QgsProcessingProvider)`
  - `processing_gflex/algorithms/flexure_2d.py` — `Flexure2DAlgorithm`
  - `processing_gflex/metadata.txt` — QGIS plugin metadata (display name: `gFlex`; must live beside `__init__.py`)
- Display name in `metadata.txt`: `gFlex` (preserves branding)
- Repo name is all-lowercase (`processing_gflex`) — Pythonic, consistent with
  import and eventual PyPI package name.

---

## Related projects

- **gFlex** (`~/models/gFlex`) — the core library; v2.0.0b1 is the current beta
- **GRASS GIS addons** (`~/models/grass-addons-gflex`) — r.flexure, v.flexure;
  update in progress on branch `update-flexure-modules`
- **Landlab** — gFlex component; update pending v2.0.0 final release

## Author

Andy Wickert (awickert), University of Minnesota.
