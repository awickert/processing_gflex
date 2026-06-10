"""Tests for Flexure2DAlgorithm.

Runs through the QGIS Processing framework using a headless QGIS app
(initialised in conftest.py).  All tests use a 30×30 grid at 5 km
spacing with a central point load; see conftest.py for grid parameters.
"""

import numpy as np
import pytest

from osgeo import gdal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(load_layer, output_path, **overrides):
    """Run gflex:flexure2d via processing.run() and return the deflection array."""
    import processing
    params = {
        'INPUT_LOAD':    load_layer,
        'LOAD_DENSITY':  0.0,
        'INPUT_TE':      '10000',     # 10 km in metres
        'TE_UNITS':      0,           # m
        'METHOD':        0,           # FD
        'BC_NORTH':      5,           # infinite
        'BC_SOUTH':      5,
        'BC_WEST':       5,
        'BC_EAST':       5,
        'BC_FFT_EW':     0,           # infinite
        'BC_FFT_NS':     0,
        'PARAM_G':       9.8,
        'PARAM_E':       65.0,        # GPa
        'PARAM_NU':      0.25,
        'PARAM_RHO_M':   3300.0,
        'PARAM_RHO_FILL': 0.0,
        'PARAM_SIGMA_XX': 0.0,
        'PARAM_SIGMA_YY': 0.0,
        'PARAM_SIGMA_XY': 0.0,
        'PARAM_FFT_PAD_N': 4.0,
        'OUTPUT':        str(output_path),
    }
    params.update(overrides)
    result = processing.run('gflex:flexure2d', params)
    ds = gdal.Open(result['OUTPUT'])
    w = ds.GetRasterBand(1).ReadAsArray()
    ds = None
    return w


# ---------------------------------------------------------------------------
# checkParameterValues
# ---------------------------------------------------------------------------

class TestCheckParameterValues:

    def test_rho_fill_ge_rho_m_rejected(self, load_layer, tmp_dir):
        """rho_fill >= rho_m must be caught before the solve."""
        import processing
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback
        from processing_gflex.algorithms.flexure_2d import Flexure2DAlgorithm

        alg = Flexure2DAlgorithm()
        alg.initAlgorithm()
        params = {
            'INPUT_LOAD': load_layer,
            'INPUT_TE': '10000', 'TE_UNITS': 0, 'METHOD': 0,
            'PARAM_RHO_M': 3300.0, 'PARAM_RHO_FILL': 3300.0,
            'OUTPUT': str(tmp_dir / 'out.tif'),
        }
        ok, msg = alg.checkParameterValues(params, QgsProcessingContext())
        assert not ok
        assert 'rho_fill' in msg.lower() or 'infill' in msg.lower()

    def test_fft_with_raster_te_rejected(self, load_layer, te_layer, tmp_dir):
        """FFT method with a raster Te string must be caught before the solve."""
        from processing_gflex.algorithms.flexure_2d import Flexure2DAlgorithm
        from qgis.core import QgsProcessingContext

        alg = Flexure2DAlgorithm()
        alg.initAlgorithm()
        params = {
            'INPUT_LOAD': load_layer,
            'INPUT_TE': te_layer.name(),   # layer name, not a number
            'TE_UNITS': 0, 'METHOD': 1,    # FFT
            'PARAM_RHO_M': 3300.0, 'PARAM_RHO_FILL': 0.0,
            'OUTPUT': str(tmp_dir / 'out.tif'),
        }
        ok, msg = alg.checkParameterValues(params, QgsProcessingContext())
        assert not ok
        assert 'scalar' in msg.lower() or 'fft' in msg.lower()

    def test_sas_with_raster_te_rejected(self, load_layer, te_layer, tmp_dir):
        """SAS method with a raster Te string must be caught before the solve."""
        from processing_gflex.algorithms.flexure_2d import Flexure2DAlgorithm
        from qgis.core import QgsProcessingContext

        alg = Flexure2DAlgorithm()
        alg.initAlgorithm()
        params = {
            'INPUT_LOAD': load_layer,
            'INPUT_TE': te_layer.name(),
            'TE_UNITS': 0, 'METHOD': 2,    # SAS
            'PARAM_RHO_M': 3300.0, 'PARAM_RHO_FILL': 0.0,
            'OUTPUT': str(tmp_dir / 'out.tif'),
        }
        ok, msg = alg.checkParameterValues(params, QgsProcessingContext())
        assert not ok
        assert 'scalar' in msg.lower() or 'sas' in msg.lower()


# ---------------------------------------------------------------------------
# Physical correctness
# ---------------------------------------------------------------------------

class TestPhysics:

    def test_fd_scalar_te_subsidence_at_load(self, load_layer, tmp_dir):
        """FD with scalar Te: deflection under the load must be negative (down)."""
        w = _run(load_layer, tmp_dir / 'fd_scalar.tif')
        cy, cx = w.shape[0] // 2, w.shape[1] // 2
        assert w[cy, cx] < 0, "Expected subsidence under load"

    def test_fft_scalar_te_subsidence_at_load(self, load_layer, tmp_dir):
        """FFT with scalar Te: deflection under the load must be negative."""
        w = _run(load_layer, tmp_dir / 'fft_scalar.tif', METHOD=1)
        cy, cx = w.shape[0] // 2, w.shape[1] // 2
        assert w[cy, cx] < 0

    def test_sas_scalar_te_subsidence_at_load(self, load_layer, tmp_dir):
        """SAS with scalar Te: deflection under the load must be negative."""
        w = _run(load_layer, tmp_dir / 'sas_scalar.tif', METHOD=2)
        cy, cx = w.shape[0] // 2, w.shape[1] // 2
        assert w[cy, cx] < 0

    def test_fd_raster_te_subsidence_at_load(self, load_layer, te_layer, tmp_dir):
        """FD with raster Te: deflection under the load must be negative."""
        w = _run(load_layer, tmp_dir / 'fd_raster.tif',
                 INPUT_TE=te_layer.name(), TE_UNITS=0)
        cy, cx = w.shape[0] // 2, w.shape[1] // 2
        assert w[cy, cx] < 0

    def test_output_shape_matches_input(self, load_layer, tmp_dir):
        """Output raster must have the same number of rows and columns as the input."""
        from conftest import _NX, _NY
        w = _run(load_layer, tmp_dir / 'shape_check.tif')
        assert w.shape == (_NY, _NX)

    def test_larger_te_deeper_deflection(self, load_layer, tmp_dir):
        """Stiffer plate (higher Te) should produce shallower deflection."""
        w_soft = _run(load_layer, tmp_dir / 'soft.tif', INPUT_TE='5000',  METHOD=1)
        w_stiff = _run(load_layer, tmp_dir / 'stiff.tif', INPUT_TE='50000', METHOD=1)
        cy, cx = w_soft.shape[0] // 2, w_soft.shape[1] // 2
        assert abs(w_soft[cy, cx]) > abs(w_stiff[cy, cx]), (
            "Softer plate should deflect more under the same load"
        )

    def test_load_density_equivalent_to_prestressed(self, load_layer, tmp_dir):
        """Thickness × density × g should give same deflection as pre-computed stress."""
        from conftest import _LOAD_PA
        import numpy as np
        from osgeo import gdal
        import tempfile, os

        rho = 1000.0    # water
        g   = 9.8
        h   = _LOAD_PA / (rho * g)   # thickness [m] that equals _LOAD_PA stress

        # Write a thickness raster
        from conftest import _NX, _NY, _GT, _EPSG, _write_tif  # noqa: F401
        thickness = np.zeros((_NY, _NX))
        thickness[_NY // 2, _NX // 2] = h
        thickness_path = str(tmp_dir / 'thickness.tif')
        # Need to write with same CRS
        from osgeo import osr
        srs = osr.SpatialReference(); srs.ImportFromEPSG(_EPSG)
        driver = gdal.GetDriverByName('GTiff')
        ds = driver.Create(thickness_path, _NX, _NY, 1, gdal.GDT_Float32)
        ds.SetGeoTransform(_GT); ds.SetProjection(srs.ExportToWkt())
        ds.GetRasterBand(1).WriteArray(thickness.astype(np.float32))
        ds.FlushCache(); ds = None

        from qgis.core import QgsRasterLayer
        thick_layer = QgsRasterLayer(thickness_path, 'thickness')

        w_stress    = _run(load_layer,  tmp_dir / 'stress.tif',    METHOD=1)
        w_thickness = _run(thick_layer, tmp_dir / 'thickness_out.tif',
                           METHOD=1, LOAD_DENSITY=rho, PARAM_G=g)
        cy, cx = w_stress.shape[0] // 2, w_stress.shape[1] // 2
        np.testing.assert_allclose(w_stress[cy, cx], w_thickness[cy, cx], rtol=1e-4)

    def test_te_units_m_vs_km_equivalent(self, load_layer, tmp_dir):
        """Te '10000 m' and '10 km' should produce identical deflection."""
        w_m  = _run(load_layer, tmp_dir / 'te_m.tif',
                    INPUT_TE='10000', TE_UNITS=0, METHOD=1)
        w_km = _run(load_layer, tmp_dir / 'te_km.tif',
                    INPUT_TE='10',    TE_UNITS=1, METHOD=1)
        np.testing.assert_allclose(w_m, w_km, rtol=1e-6)

    def test_output_crs_and_geotransform(self, load_layer, tmp_dir):
        """Output raster must preserve the CRS and geotransform of the input."""
        from conftest import _GT, _EPSG
        from osgeo import osr
        out = tmp_dir / 'crs_check.tif'
        _run(load_layer, out)
        ds = gdal.Open(str(out))
        assert ds.GetGeoTransform() == pytest.approx(_GT)
        assert osr.SpatialReference(wkt=ds.GetProjection()).GetAuthorityCode(None) == str(_EPSG)
        ds = None

    def test_zero_load_zero_deflection(self, tmp_dir):
        """An all-zero load raster must produce an all-zero deflection raster."""
        from conftest import _NX, _NY, _write_tif
        from qgis.core import QgsRasterLayer
        zero_layer = QgsRasterLayer(
            _write_tif(np.zeros((_NY, _NX)), tmp_dir / 'zero_load.tif'),
            'zero_load',
        )
        # Use FD: the FFT solver has a known numerical issue with all-zero input.
        w = _run(zero_layer, tmp_dir / 'zero_deflection.tif', METHOD=0)
        np.testing.assert_allclose(w, 0.0, atol=1e-6)

    def test_rho_fill_increases_deflection(self, load_layer, tmp_dir):
        """Infill reduces the net restoring buoyancy (rho_m - rho_fill), so the plate
        must deflect more with rho_fill > 0 than with rho_fill = 0 (air)."""
        w_air   = _run(load_layer, tmp_dir / 'fill_air.tif',   METHOD=1, PARAM_RHO_FILL=0.0)
        w_water = _run(load_layer, tmp_dir / 'fill_water.tif', METHOD=1, PARAM_RHO_FILL=1000.0)
        cy, cx  = w_air.shape[0] // 2, w_air.shape[1] // 2
        assert abs(w_water[cy, cx]) > abs(w_air[cy, cx])

    def test_inplane_stress_changes_deflection(self, load_layer, tmp_dir):
        """Non-zero sigma_xx must produce a different deflection field."""
        w_0   = _run(load_layer, tmp_dir / 'sigma_0.tif',   METHOD=0, PARAM_SIGMA_XX=0.0)
        w_100 = _run(load_layer, tmp_dir / 'sigma_100.tif', METHOD=0, PARAM_SIGMA_XX=100.0)
        assert not np.allclose(w_0, w_100)

    def test_forebulge_exists(self, load_layer, tmp_dir):
        """Deflection must be positive (forebulge) somewhere in the grid away from the load."""
        w = _run(load_layer, tmp_dir / 'forebulge.tif', METHOD=1)
        assert np.any(w > 0)

    def test_load_linearity(self, load_layer, tmp_dir):
        """Doubling the load must double the deflection at the load centre."""
        from conftest import _NX, _NY, _LOAD_PA, _write_tif
        from qgis.core import QgsRasterLayer
        qs2 = np.zeros((_NY, _NX))
        qs2[_NY // 2, _NX // 2] = 2 * _LOAD_PA
        double_layer = QgsRasterLayer(
            _write_tif(qs2, tmp_dir / 'double_load.tif'), 'double_load'
        )
        w1 = _run(load_layer,   tmp_dir / 'linear_1x.tif', METHOD=1)
        w2 = _run(double_layer, tmp_dir / 'linear_2x.tif', METHOD=1)
        cy, cx = w1.shape[0] // 2, w1.shape[1] // 2
        np.testing.assert_allclose(w2[cy, cx], 2 * w1[cy, cx], rtol=1e-4)
