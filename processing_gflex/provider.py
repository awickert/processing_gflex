from qgis.core import QgsProcessingProvider
from .algorithms.flexure_2d import Flexure2DAlgorithm


class GFlexProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(Flexure2DAlgorithm())

    def id(self):
        return 'gflex'

    def name(self):
        return 'gFlex'

    def longName(self):
        return 'gFlex — Lithospheric Flexural Isostasy'
