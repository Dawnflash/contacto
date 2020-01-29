from enum import IntEnum
import pkgutil
import importlib
from PIL import Image
from urllib.request import urlopen
import io


class DType(IntEnum):
    TEXT  = 1,
    BIN   = 2,
    AXREF = 3,
    EXREF = 4

    def is_xref(self):
        return self is self.AXREF or self is self.EXREF


class Scope(IntEnum):
    GROUP     = 1,
    ENTITY    = 2,
    ATTRIBUTE = 3,
    ATTR_VAL  = 4

    @classmethod
    def from_str(cls, s):
        if s == 'grp':
            return cls.GROUP
        if s == 'ent':
            return cls.ENTITY
        if s == 'attr':
            return cls.ATTRIBUTE
        raise Exception("Unknown scope")


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


# rspec is a string here
def parse_refspec(rspec):
    if not rspec:
        return [None, None, None]
    toks = rspec.split('/')
    ln = len(toks)
    if ln > 3:
        raise Exception('REFSPEC: [GROUP][/[ENTITY][/[ATTRIBUTE]]]')
    toks = [None if tok == '' else tok for tok in toks]
    for _ in range(3 - ln):
        toks.append(None)
    return toks


# GROUP/ENTITY/ATTR -> [GROUP, ENTITY, ATTR]
# REFSPEC -> REFERENCE
def parse_ref(rspec):
    p_rspec = parse_refspec(rspec)
    scope = refspec_scope(p_rspec)
    if scope == Scope.ENTITY:
        return DType.EXREF, p_rspec
    if scope == Scope.ATTRIBUTE:
        return DType.AXREF, p_rspec
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


def fmatch(needle, haystack):
    return needle.casefold() in haystack.casefold()


def dump_lscope(index_filters):
    scope = Scope.GROUP
    for fil in index_filters:
        if fil:
            scope += 1
        else:
            break
    return Scope(scope)


def refspec_scope(p_rspec):
    g, e, a = p_rspec
    if g and e and a:
        return Scope.ATTRIBUTE
    if g and e:
        return Scope.ENTITY
    if g and not a:
        return Scope.GROUP
    return None


def attr_val_str(attr, direct):
    vtype, val = attr.get()
    if direct:
        return val
    s, pfx = '', ''
    if vtype == DType.TEXT:
        s = val
    if vtype == DType.BIN:
        s = f"<BINARY, {size_str(val)}>"
    if attr.type.is_xref():
        pfx = f'[-> {attr.data}] '
    return f"{pfx}{s}"


def size_str(blob):
    size = len(blob)
    sfx = 'B'
    if size > 1024:
        size /= 1024
        sfx = 'kB'
    if size > 1024:
        size /= 1024
        sfx = 'MB'
    return f"{int(size)}{sfx}"


def validate_img(data):
    try:
        bio = io.BytesIO(data)
        img = Image.open(bio)
        img.verify()
    except:
        return False
    return True


def parse_valspec(value):
    if not value:
        return None, None
    if value.startswith('FILE:'):
        fname = value.split('FILE:')[1]
        with open(fname, 'rb') as f:
            return DType.BIN, f.read()
    if value.startswith('URL:'):
        url = value.split('URL:')[1]
        with urlopen(url) as f:
            return DType.BIN, f.read()
    if value.startswith('REF:'):
        # return parsed reference
        return parse_ref(value.split('REF:')[1])
    return DType.TEXT, value
