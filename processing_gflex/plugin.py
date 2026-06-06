from qgis.core import QgsApplication
from .provider import GFlexProvider


class GFlexPlugin:
    def __init__(self, iface):
        self.provider = None

    def initProcessing(self):
        self.provider = GFlexProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)
