"""Pytest configuration: initialise a headless QGIS application and register
the processing_gflex provider.

Test grid: 30×30 cells at 5 km spacing (UTM-like, EPSG:32633).
Central point load of 1e6 Pa; Te = 10 km (small, to keep FD padding cheap).
"""

import os
import sys

import pytest

# QGIS cleanup segfaults on exit in headless mode.  Bypassing Python teardown
# with os._exit() avoids the segfault propagating as a non-zero exit code in CI.
# trylast=True ensures pytest's terminal reporter prints failure details first.
@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    os._exit(int(exitstatus))

# Fix Anaconda's stale proj.db before any GDAL/QGIS import.
os.environ['PROJ_DATA'] = '/usr/share/proj'
os.environ.setdefault('QGIS_PREFIX_PATH', '/usr')

from pathlib import Path
import numpy as np
import pytest
from osgeo import gdal, osr

sys.path.insert(0, str(Path(__file__).parent.parent))

_NX = _NY = 30
_DX = 5000.0           # m
_TE = 10_000.0         # m — small Te keeps padding to ~19 cells
_LOAD_PA = 1e6         # central point load [Pa]
_EPSG = 32633

_GT = (250_000.0, _DX, 0.0, 4_900_000.0, 0.0, -_DX)

_PROVIDER = None


def pytest_configure(config):
    global _PROVIDER

    from qgis.testing import start_app
    start_app()

    sys.path.insert(0, '/usr/share/qgis/python/plugins')
    from processing.core.Processing import Processing
    Processing.initialize()

    from processing_gflex.provider import GFlexProvider
    from qgis.core import QgsApplication
    _PROVIDER = GFlexProvider()
    QgsApplication.processingRegistry().addProvider(_PROVIDER)


def _write_tif(data: np.ndarray, path, nodata: float = -9999.0) -> str:
    rows, cols = data.shape
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(_EPSG)
    driver = gdal.GetDriverByName('GTiff')
    ds = driver.Create(str(path), cols, rows, 1, gdal.GDT_Float32)
    ds.SetGeoTransform(_GT)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.WriteArray(data.astype(np.float32))
    band.SetNoDataValue(nodata)
    ds.FlushCache()
    ds = None
    return str(path)


@pytest.fixture(scope='session')
def tmp_dir(tmp_path_factory):
    return tmp_path_factory.mktemp('gflex')


@pytest.fixture(scope='session')
def load_tif(tmp_dir):
    """Central point load raster, 30×30, stress [Pa]."""
    qs = np.zeros((_NY, _NX))
    qs[_NY // 2, _NX // 2] = _LOAD_PA
    return _write_tif(qs, tmp_dir / 'load.tif')


@pytest.fixture(scope='session')
def te_tif(tmp_dir):
    """Uniform Te raster, 30×30, values in metres."""
    te = np.full((_NY, _NX), _TE)
    return _write_tif(te, tmp_dir / 'te.tif')


@pytest.fixture(scope='session')
def load_layer(load_tif):
    from qgis.core import QgsRasterLayer
    layer = QgsRasterLayer(load_tif, 'load')
    assert layer.isValid()
    return layer


@pytest.fixture(scope='session')
def te_layer(te_tif):
    from qgis.core import QgsRasterLayer, QgsProject
    layer = QgsRasterLayer(te_tif, 'te')
    assert layer.isValid()
    QgsProject.instance().addMapLayer(layer)
    return layer
