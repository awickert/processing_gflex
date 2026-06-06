import warnings

import numpy as np
from osgeo import gdal, osr
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
    QgsProcessingUtils,
)

# gFlex v2 alias strings for boundary conditions
_BC_KEYS = ['free', 'clamped', 'pinned', 'mirror', 'periodic']
_BC_LABELS = [
    'Free / broken plate',
    'Clamped',
    'Pinned (simply supported)',
    'Mirror symmetry',
    'Periodic',
]

_METHOD_KEYS = ['fd', 'fft', 'sas']
_METHOD_LABELS = [
    'Finite difference (FD) — variable or scalar Te, user-specified BCs',
    'Spectral / FFT — scalar Te only, periodic BCs',
    'Superposition of analytical solutions (SAS) — scalar Te only',
]


class Flexure2DAlgorithm(QgsProcessingAlgorithm):

    INPUT_LOAD = 'INPUT_LOAD'
    LOAD_DENSITY = 'LOAD_DENSITY'
    INPUT_TE = 'INPUT_TE'
    TE_UNITS = 'TE_UNITS'
    METHOD = 'METHOD'
    BC_NORTH = 'BC_NORTH'
    BC_SOUTH = 'BC_SOUTH'
    BC_WEST = 'BC_WEST'
    BC_EAST = 'BC_EAST'
    PARAM_G = 'PARAM_G'
    PARAM_E = 'PARAM_E'
    PARAM_NU = 'PARAM_NU'
    PARAM_RHO_M = 'PARAM_RHO_M'
    PARAM_RHO_FILL = 'PARAM_RHO_FILL'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        # ── Load ──────────────────────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_LOAD,
                'Load raster (stress [Pa], or thickness [m] if density is set)',
            )
        )
        p = QgsProcessingParameterNumber(
            self.LOAD_DENSITY,
            'Load density [kg/m³]  (0 = raster is already a stress [Pa])',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=0.0,
            minValue=0.0,
        )
        p.setFlags(p.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(p)

        # ── Elastic thickness ─────────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterString(
                self.INPUT_TE,
                'Elastic thickness — scalar value or raster layer name',
                defaultValue='35000',
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.TE_UNITS,
                'Elastic thickness units',
                options=['m', 'km'],
                defaultValue=0,
            )
        )

        # ── Solution method ───────────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterEnum(
                self.METHOD,
                'Solution method',
                options=_METHOD_LABELS,
                defaultValue=0,
            )
        )

        # ── Boundary conditions (FD only) ─────────────────────────────────────
        for param_key, label in [
            (self.BC_NORTH, 'North BC (FD only)'),
            (self.BC_SOUTH, 'South BC (FD only)'),
            (self.BC_WEST,  'West BC (FD only)'),
            (self.BC_EAST,  'East BC (FD only)'),
        ]:
            self.addParameter(
                QgsProcessingParameterEnum(
                    param_key,
                    label,
                    options=_BC_LABELS,
                    defaultValue=0,  # free
                )
            )

        # ── Material properties (advanced) ────────────────────────────────────
        for param_key, label, default in [
            (self.PARAM_G,       'Gravitational acceleration g [m/s²]',    9.8),
            (self.PARAM_E,       "Young's modulus E [Pa]",                 65e9),
            (self.PARAM_NU,      "Poisson's ratio ν",                      0.25),
            (self.PARAM_RHO_M,   'Mantle density ρ_m [kg/m³]',            3300.0),
            (self.PARAM_RHO_FILL,'Infill density ρ_fill [kg/m³] (0 = air)', 0.0),
        ]:
            p = QgsProcessingParameterNumber(
                param_key,
                label,
                type=QgsProcessingParameterNumber.Double,
                defaultValue=default,
            )
            p.setFlags(p.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
            self.addParameter(p)

        # ── Output ────────────────────────────────────────────────────────────
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                'Flexural deflection [m]',
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # ── Check gFlex ───────────────────────────────────────────────────────
        try:
            import gflex
        except ImportError:
            raise QgsProcessingException(
                'Cannot import gFlex. Install with:\n'
                '  pip install gflex\n'
                'or see https://github.com/awickert/gFlex'
            )

        _ver = tuple(
            int(x.split('a')[0].split('b')[0].split('rc')[0])
            for x in gflex.__version__.split('.')[:3]
        )
        if _ver < (2, 0, 0):
            raise QgsProcessingException(
                f'Requires gFlex >= 2.0.0; installed: {gflex.__version__}'
            )

        # ── Read load raster ──────────────────────────────────────────────────
        load_layer = self.parameterAsRasterLayer(parameters, self.INPUT_LOAD, context)
        load_ds = gdal.Open(load_layer.source())
        if load_ds is None:
            raise QgsProcessingException(
                f'Cannot open load raster: {load_layer.source()}'
            )

        geotransform = load_ds.GetGeoTransform()
        projection   = load_ds.GetProjection()
        cols = load_ds.RasterXSize
        rows = load_ds.RasterYSize

        load_band  = load_ds.GetRasterBand(1)
        load_array = load_band.ReadAsArray().astype(float)
        load_nodata = load_band.GetNoDataValue()
        if load_nodata is not None:
            load_array[np.isclose(load_array, load_nodata)] = 0.0
        load_ds = None

        # ── Surface load stress qs [Pa] ───────────────────────────────────────
        g            = self.parameterAsDouble(parameters, self.PARAM_G, context)
        load_density = self.parameterAsDouble(parameters, self.LOAD_DENSITY, context)
        qs = load_density * g * load_array if load_density > 0.0 else load_array

        # ── Elastic thickness ─────────────────────────────────────────────────
        te_units_idx = self.parameterAsEnum(parameters, self.TE_UNITS, context)
        te_scale     = 1000.0 if te_units_idx == 1 else 1.0  # km → m

        te_str = self.parameterAsString(parameters, self.INPUT_TE, context).strip()
        try:
            T_e = float(te_str) * te_scale
        except ValueError:
            # Not a number — try to resolve as a raster layer name or path
            te_layer = QgsProcessingUtils.mapLayerFromString(te_str, context)
            if te_layer is None:
                raise QgsProcessingException(
                    f'Elastic thickness "{te_str}" is neither a valid number '
                    'nor a recognised raster layer name.'
                )
            te_ds   = gdal.Open(te_layer.source())
            te_band = te_ds.GetRasterBand(1)
            te_raw  = te_band.ReadAsArray().astype(float)
            te_nodata = te_band.GetNoDataValue()
            T_e = te_raw * te_scale
            if te_nodata is not None:
                T_e[np.isclose(te_raw, te_nodata)] = 0.0
            te_ds = None

        # ── Grid spacing [m] ──────────────────────────────────────────────────
        # geotransform: (x_min, dx, 0, y_max, 0, -dy)  (dy is negative)
        dx_raw = abs(geotransform[1])
        dy_raw = abs(geotransform[5])

        srs = osr.SpatialReference(wkt=projection)
        if srs.IsGeographic():
            y_max   = geotransform[3]
            y_min   = y_max + rows * geotransform[5]
            lat_mid = (y_max + y_min) / 2.0
            dy = dy_raw * 111195.0
            dx = dx_raw * (np.pi / 180.0) * 6_371_000.0 * np.cos(np.deg2rad(lat_mid))
            feedback.pushWarning(
                f'Geographic CRS detected. Approximating metric grid spacing at '
                f'mid-latitude {lat_mid:.2f}°: dx ≈ {dx:.0f} m, dy ≈ {dy:.0f} m. '
                'Results will be approximate; consider reprojecting to a metric CRS.'
            )
        else:
            dx, dy = dx_raw, dy_raw

        # ── Method ───────────────────────────────────────────────────────────
        method_idx = self.parameterAsEnum(parameters, self.METHOD, context)
        method     = _METHOD_KEYS[method_idx]

        if method in ('fft', 'sas') and not np.isscalar(T_e):
            raise QgsProcessingException(
                f'Method "{method}" requires a scalar elastic thickness. '
                'Either switch to FD or remove the Te raster and set a scalar value.'
            )

        # ── Assemble gFlex object ────────────────────────────────────────────
        flex = gflex.F2D()
        flex.quiet  = True
        flex.method = method
        flex.qs     = qs
        flex.T_e    = T_e
        flex.dx     = dx
        flex.dy     = dy
        flex.g      = g
        flex.E      = self.parameterAsDouble(parameters, self.PARAM_E,       context)
        flex.nu     = self.parameterAsDouble(parameters, self.PARAM_NU,      context)
        flex.rho_m  = self.parameterAsDouble(parameters, self.PARAM_RHO_M,   context)
        flex.rho_fill = self.parameterAsDouble(parameters, self.PARAM_RHO_FILL, context)

        if method == 'fd':
            flex.bc_north = _BC_KEYS[self.parameterAsEnum(parameters, self.BC_NORTH, context)]
            flex.bc_south = _BC_KEYS[self.parameterAsEnum(parameters, self.BC_SOUTH, context)]
            flex.bc_west  = _BC_KEYS[self.parameterAsEnum(parameters, self.BC_WEST,  context)]
            flex.bc_east  = _BC_KEYS[self.parameterAsEnum(parameters, self.BC_EAST,  context)]
        elif method == 'fft':
            flex.bc_north = flex.bc_south = flex.bc_west = flex.bc_east = 'periodic'
        # SAS: no BCs needed (gFlex uses no_outside_loads implicitly)

        # ── Solve ─────────────────────────────────────────────────────────────
        feedback.pushInfo('Computing flexural deflections…')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            flex.initialize()
            flex.run()
            w = flex.w.copy()   # copy before finalize() deletes flex.w
            flex.finalize()
        for warninfo in caught:
            feedback.pushWarning(str(warninfo.message))
        feedback.pushInfo('Done.')

        # ── Write output raster ───────────────────────────────────────────────
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(output_path, cols, rows, 1, gdal.GDT_Float64)
        out_ds.SetGeoTransform(geotransform)
        out_ds.SetProjection(projection)
        out_band = out_ds.GetRasterBand(1)
        out_band.WriteArray(w)
        out_band.SetNoDataValue(float('nan'))
        out_ds.FlushCache()
        out_ds = None

        return {self.OUTPUT: output_path}

    # ── Algorithm metadata ────────────────────────────────────────────────────

    def name(self):
        return 'flexure2d'

    def displayName(self):
        return '2D Flexural Isostasy'

    def group(self):
        return 'gFlex'

    def groupId(self):
        return 'gflex'

    def shortHelpString(self):
        return (
            '<p>Computes 2-D lithospheric flexural isostasy using the '
            '<a href="https://github.com/awickert/gFlex">gFlex</a> library.</p>'
            '<h3>Load input</h3>'
            '<p>The load raster is interpreted as surface stress [Pa] by default '
            '(<i>rho_load · g · h</i>). Set <b>Load density</b> &gt; 0 to have the '
            'plugin compute the stress from a thickness raster [m].</p>'
            '<h3>Elastic thickness</h3>'
            '<p>Enter a <b>number</b> (e.g. <code>35000</code>) for uniform Te, '
            'or a <b>raster layer name</b> for spatially variable Te (FD only). '
            'Select units (m or km).</p>'
            '<h3>Methods</h3>'
            '<ul>'
            '<li><b>FD</b> — finite difference; supports variable Te and all '
            'boundary conditions.</li>'
            '<li><b>FFT</b> — spectral; scalar Te only, periodic boundary.</li>'
            '<li><b>SAS</b> — superposition of analytical solutions; scalar Te only.</li>'
            '</ul>'
            '<h3>Boundary conditions (FD only)</h3>'
            '<p>Free (broken plate), Clamped, Pinned, Mirror, or Periodic '
            'for each of the four edges.</p>'
            '<h3>Requirements</h3>'
            '<p>gFlex &ge; 2.0.0: <code>pip install gflex</code></p>'
        )

    def createInstance(self):
        return Flexure2DAlgorithm()
