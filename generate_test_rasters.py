#!/usr/bin/env python3
"""Generate test GeoTIFF inputs for the processing_gflex plugin.

Creates two files in tests/data/:
  load_ice_thickness.tif   — Gaussian ice cap, 1000 m thick at centre, [m]
  te_35km.tif              — Uniform elastic thickness = 35 000 m

Grid: 100 × 100 cells at 5 km spacing in a UTM-like CRS (EPSG:32633).
Origin placed so the load centre falls on (500000, 4500000).

Run from the repo root:
    python generate_test_rasters.py
"""

import os
import numpy as np

import rasterio
from rasterio.transform import from_origin
from rasterio.crs import CRS

# ── Grid parameters ────────────────────────────────────────────────────────────
nx, ny = 100, 100       # columns, rows
dx = dy = 5000.0        # cell size [m]
origin_x = 250000.0     # top-left corner easting  [m]
origin_y = 4750000.0    # top-left corner northing [m]
epsg = 32633            # UTM zone 33N — any projected CRS works

# ── Cell-centre coordinates ────────────────────────────────────────────────────
cx_all = origin_x + (np.arange(nx) + 0.5) * dx
cy_all = origin_y - (np.arange(ny) + 0.5) * dy   # raster rows go top→bottom
XX, YY = np.meshgrid(cx_all, cy_all)

centre_x = origin_x + nx / 2 * dx
centre_y = origin_y - ny / 2 * dy
r = np.sqrt((XX - centre_x)**2 + (YY - centre_y)**2)

# ── Ice-thickness load: Gaussian cap, peak = 1000 m ───────────────────────────
sigma = 100e3   # 100 km standard deviation → compact ice sheet
h_ice = 1000.0 * np.exp(-0.5 * (r / sigma)**2)   # [m]

# ── Uniform elastic thickness ──────────────────────────────────────────────────
Te_uniform = np.full((ny, nx), 35000.0)   # 35 km in metres

# ── Helper: write a single-band Float32 GeoTIFF ───────────────────────────────
def write_tif(path, array, nodata=-9999.0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    transform = from_origin(origin_x, origin_y, dx, dy)
    crs = CRS.from_wkt(
        'PROJCS["WGS 84 / UTM zone 33N",'
        'GEOGCS["WGS 84",DATUM["WGS_1984",'
        'SPHEROID["WGS 84",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],'
        'PROJECTION["Transverse_Mercator"],'
        'PARAMETER["latitude_of_origin",0],'
        'PARAMETER["central_meridian",15],'
        'PARAMETER["scale_factor",0.9996],'
        'PARAMETER["false_easting",500000],'
        'PARAMETER["false_northing",0],'
        'UNIT["metre",1]]'
    )
    with rasterio.open(
        path, 'w',
        driver='GTiff',
        height=ny, width=nx,
        count=1, dtype='float32',
        crs=crs, transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(array.astype(np.float32), 1)
    print(f'Wrote {path}  ({nx}×{ny} cells, {dx/1e3:.0f} km spacing)')

write_tif('tests/data/load_ice_thickness.tif', h_ice)
write_tif('tests/data/te_35km.tif', Te_uniform)

print()
print('Load range : {:.1f} – {:.1f} m (ice thickness)'.format(h_ice.min(), h_ice.max()))
print('Te          : 35 000 m (uniform)')
print()
print('Suggested plugin inputs:')
print('  Load raster    : load_ice_thickness.tif')
print('  Te             : 35    (or te_35km.tif as a layer)')
print('  Te units       : km')
print('  Load density   : 917   (ice, kg/m³ — set in Advanced)')
print('  Method         : FFT or FD')
print('  Expected result: ~240 m depression, ~10 m forebulge at ~200 km radius')
