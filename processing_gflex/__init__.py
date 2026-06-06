def classFactory(iface):
    from .plugin import GFlexPlugin
    return GFlexPlugin(iface)
