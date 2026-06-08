import os

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .algorithms.flexure_2d import Flexure2DAlgorithm

_ICON = os.path.join(os.path.dirname(__file__), 'icons', 'icon.png')


class GFlexProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(Flexure2DAlgorithm())

    def id(self):
        return 'gflex'

    def name(self):
        return 'gFlex'

    def longName(self):
        return 'gFlex — Lithospheric Flexural Isostasy'

    def icon(self):
        return QIcon(_ICON)
