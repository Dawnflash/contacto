"""Support structures and functions.
"""

from enum import IntEnum
import pkgutil
import importlib
from PIL import Image
from urllib.request import urlopen
import io
import sys
import click


class DType(IntEnum):
    """Attribute data types.
    """
    TEXT = 1,
    BIN = 2,
    AXREF = 3,
    EXREF = 4

    def is_xref(self):
        """True if the data type is a reference.
        """
        return self is self.AXREF or self is self.EXREF


class Scope(IntEnum):
    """Level in the contact hierarchy.
    """
    GROUP = 1,
    ENTITY = 2,
    ATTRIBUTE = 3,
    ATTR_VAL = 4

    @classmethod
    def from_str(cls, s):
        """Creates scope from string.
        """
        if s == 'grp':
            return cls.GROUP
        if s == 'ent':
            return cls.ENTITY
        if s == 'attr':
            return cls.ATTRIBUTE
        raise Exception("Unknown scope")


def bytes_to_attrdata(dtype, bin_data):
    """Parses attribute data from its binary-packed form.

    :param dtype: data type
    :type  dtype: class:`contacto.helpers.DType`
    :param bin_data: data in binary form
    :type  bin_data: bytes
    :return: parsed attribute data
    :rtype:  Union[bytes, str, int]
    """
    if dtype is DType.BIN:
        return bin_data
    if dtype is DType.TEXT:
        return bin_data.decode('utf-8')
    return int.from_bytes(bin_data, byteorder='little')


def attrdata_to_bytes(dtype, attr_data):
    """Packs attribute data into a binary form (for database storage).

    :param dtype: data type
    :type  dtype: class:`contacto.helpers.DType`
    :param attr_data: attribute data
    :type  attr_data: Union[bytes, str, int]
    :return: packed attribute data
    :rtype:  bytes
    """
    if dtype is DType.BIN:
        return attr_data
    if dtype is DType.TEXT:
        return attr_data.encode('utf-8')
    return attr_data.id.to_bytes(4, byteorder='little')


def parse_refspec(rspec):
    """Parses a generic text refspec into its tuple form.

    A generic refspec may have any parts omitted as long as it has at most 3.

    Therefore /E/, G//A, //A, G/E/A are all valid refspecs
    Omitted parts are replaced with `None`

    :param rspec: text refspec
    :type  rspec: str
    :return: parsed refspec
    :rtype:  tuple
    """
    if not rspec:
        return None, None, None
    toks = rspec.split('/')
    ln = len(toks)
    if ln > 3:
        raise Exception('REFSPEC: [GROUP][/[ENTITY][/[ATTRIBUTE]]]')
    toks = [None if tok == '' else tok for tok in toks]
    for _ in range(3 - ln):
        toks.append(None)
    return tuple(toks)


# GROUP/ENTITY/ATTR -> [GROUP, ENTITY, ATTR]
# REFSPEC -> REFERENCE
def parse_ref(rspec):
    """Parse a refspec into a reference and its type (entity or attribute).

    Requires a fully-specified refspec: G/E or G/E/A

    :param rspec: text refspec
    :type  rspec: str
    :raises Exception: the refspec is not a valid entity/attribute reference
    :return: reference type and parsed refspec
    :rtype: (class:`contacto.helpers.DType`, tuple)
    """
    p_rspec = parse_refspec(rspec)
    scope = refspec_scope(p_rspec)
    if scope == Scope.ENTITY:
        return DType.EXREF, p_rspec
    if scope == Scope.ATTRIBUTE:
        return DType.AXREF, p_rspec
    raise Exception('Bad REF signature')


def get_plugins():
    """Uses pkgutil to find plugins among top-level modules.

    :return: found plugins
    :rtype:  dict
    """
    def fam_name(name):
        return name.split('contacto_')[1]

    return {
        fam_name(name): importlib.import_module(name)
        for finder, name, ispkg
        in pkgutil.iter_modules()
        if name.startswith('contacto_')
    }


def run_plugins(storage, whitelist=[]):
    """Runs found and selected plugins.

    :param storage: used storage
    :type  storage: class:`contacto.storage.Storage`
    :param whitelist: allowed plugin names
    :type  whitelist: list, optional
    :return: lists of successful and failed run plugins
    :rtype:  (list, list)
    """
    def wl_compliant(name):
        if len(whitelist) == 0:
            return True
        return name in whitelist

    plugins = get_plugins()
    success, fail = [], []

    for name, plugin in plugins.items():
        if not wl_compliant(name):
            continue
        if hasattr(plugin, 'plugin_init'):
            if plugin.plugin_init(storage):
                success.append(name)
            else:
                fail.append(name)
    return success, fail


def fmatch(needle, haystack):
    """A case-insensitive substring search.
    """
    return needle.casefold() in haystack.casefold()


def dump_lscope(index_filters):
    """Leftmost tree scope to apply when dumping contacts.

    This corresponds to the leftmost directly specified element

    :param index_filters: parsed refspec
    :type  index_filters: tuple
    :return: leftmost scope
    :rtype:  class:`contacto.helpers.Scope`
    """
    scope = Scope.GROUP
    for fil in index_filters:
        if fil:
            scope += 1
        else:
            break
    return Scope(scope)


def refspec_scope(p_rspec):
    """The actual tree (depth) scope a refspec directly represents.

    A not-fully-specified scope such as /E/ represents nothing.

    Fully-specified scopes such as G, G/E and G/E/A do.

    :param p_rspec: parsed refspec
    :type  p_rspec: tuple
    :return: refspec scope
    :rtype:  class:`contacto.helpers.Scope`
    """
    g, e, a = p_rspec
    if g and e and a:
        return Scope.ATTRIBUTE
    if g and e:
        return Scope.ENTITY
    if g and not a:
        return Scope.GROUP
    return None


def attr_val_str(attr, direct):
    """A human-readable representation of attribute data.

    :param attr: contact attribute
    :type  attr: class:`contacto.storage.Attribute`
    :param direct: attribute name won't be printed
    :type  direct: bool, optional
    :return: string representation
    :rtype:  str
    """
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
    if attr.type == DType.EXREF and not direct:
        s = ''  # no need to print the spec twice
    return f"{pfx}{s}"


def size_str(blob):
    """Gets binary data size in human-readable units.

    :param blob: binary data
    :type  blob: bytes
    :return: data size with units
    :rtype:  str
    """
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
    """Checks if data are an image.

    :param data: binary data
    :type  blob: bytes
    :return: true if data is an image
    :rtype:  bool
    """
    try:
        bio = io.BytesIO(data)
        img = Image.open(bio)
        img.verify()
    except Exception:
        return False
    return True


def parse_valspec(value):
    """Parses an attribute value specifier (used in data input/import).

    :param value: value specifier
    :type  value: str
    :return: parsed attr value with its type
    :rtype:  (class:`contacto.helpers.DType`, Union[bytes, str, tuple])
    """
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


def print_error(err):
    """Prints a formatted error message to stderr.
    """
    click.echo("{}: {}".format(
        click.style("ERROR", fg='red', bold=True),
        err, file=sys.stderr
    ))


def print_warning(warn):
    """Prints a formatted warning message to stderr.
    """
    click.echo("{}: {}".format(
        click.style("WARN", fg='yellow', bold=True),
        warn, file=sys.stderr
    ))
