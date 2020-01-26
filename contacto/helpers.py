from enum import IntEnum
import pkgutil
import importlib


class DType(IntEnum):
    TEXT  = 1,
    BIN   = 2,
    AXREF = 3,
    EXREF = 4

    def is_xref(self):
        return self is self.AXREF or self is self.EXREF


def bytes_to_attrdata(dtype, bin_data):
    if dtype is DType.BIN:
        return bin_data
    if dtype is DType.TEXT:
        return bin_data.decode('utf-8')
    return int.from_bytes(bin_data, byteorder='little')


def attrdata_to_bytes(dtype, attr_data):
    if dtype is DType.BIN:
        return attr_data
    if dtype is DType.TEXT:
        return attr_data.encode('utf-8')
    return attr_data.id.to_bytes(4, byteorder='little')


# /GROUP/ENTITY/ATTR -> [GROUP, ENTITY, ATTR]
def parse_ref(ref):
    if ref.startswith('/'):
        lref = ref[1:].split('/')
        if len(lref) == 2:
            return DType.EXREF, lref
        if len(lref) == 3:
            return DType.AXREF, lref
    raise Exception('Bad REF signature')


def run_plugins(storage, whitelist=[]):
    def wl_compliant(name):
        if len(whitelist) == 0:
            return True
        _name = name.split('contacto_')[1]
        return _name in whitelist

    plugins = {
        name: importlib.import_module(name)
        for finder, name, ispkg
        in pkgutil.iter_modules()
        if name.startswith('contacto_') and wl_compliant(name)
    }

    for plugin in plugins.values():
        if hasattr(plugin, 'plugin_init'):
            plugin.plugin_init(storage)
